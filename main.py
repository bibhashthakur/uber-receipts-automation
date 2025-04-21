import os
import base64
import re
import pdfkit
from bs4 import BeautifulSoup
from PyPDF2 import PdfMerger
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# ----- CONFIGURATION -----
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
CREDENTIALS_FILE = 'credentials.json'
TOKEN_FILE = 'token.json'
PDF_FOLDER = 'receipts_pdf'

# Ensure the folder for PDFs exists
os.makedirs(PDF_FOLDER, exist_ok=True)

# Authenticate with Gmail using OAuth2
def gmail_authenticate():
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
        creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
    return build('gmail', 'v1', credentials=creds)

# Get all messages in a Gmail thread
def get_thread_messages(service, thread_id):
    thread = service.users().threads().get(userId='me', id=thread_id, format='full').execute()
    return thread.get('messages', [])

# Get the last (most recent) message in a thread based on internalDate
def get_last_message(service, thread_id):
    messages = get_thread_messages(service, thread_id)
    if not messages:
        return None
    # internalDate is returned as a string of epoch milliseconds.
    last_message = max(messages, key=lambda m: int(m.get('internalDate', '0')))
    return last_message

# Extract email content from a single message (preferring HTML over plain text)
def get_email_content(message):
    payload = message.get('payload', {})
    # Try top-level body data first
    if 'data' in payload.get('body', {}):
        return base64.urlsafe_b64decode(payload['body']['data']).decode(errors='replace')
    # Otherwise, look into the parts (prefer HTML)
    if 'parts' in payload:
        for part in payload['parts']:
            if part.get('mimeType') == 'text/html' and 'data' in part.get('body', {}):
                return base64.urlsafe_b64decode(part['body']['data']).decode(errors='replace')
        for part in payload['parts']:
            if part.get('mimeType') == 'text/plain' and 'data' in part.get('body', {}):
                return base64.urlsafe_b64decode(part['body']['data']).decode(errors='replace')
    return None

# Extract receipt amounts from the HTML content using BeautifulSoup
def extract_amounts(html_content):
    from bs4 import BeautifulSoup
    import re

    soup = BeautifulSoup(html_content, 'html.parser')

    def find_amount(label):
        # Compile a regex pattern for the label as a whole word (case-insensitive)
        pattern = re.compile(r'\b' + re.escape(label) + r'\b', re.IGNORECASE)
        # Search for the <td> element whose text matches the pattern
        label_td = soup.find('td', string=pattern)
        if label_td:
            amount_td = label_td.find_next_sibling('td')
            if amount_td:
                # Get the text, remove $ or ₹ symbols and commas, then convert to float
                amount_text = amount_td.get_text(strip=True)
                # Remove both $ and ₹ using regex
                amount_text = re.sub(r'[\$,₹]', '', amount_text).replace(',', '')
                try:
                    return float(amount_text)
                except ValueError:
                    print(f"Couldn't parse amount for {label}: {amount_text}")
                    return 0.0
            else:
                print(f"Amount cell not found for {label}")
                return 0.0
        else:
            print(f"Label not found: {label}")
            return 0.0

    # For our example receipts, we assume Total and Tip are explicitly provided.
    total = find_amount('Total')
    tip = find_amount('Tip')
    # If you want subtotal to be calculated as (Total - Tip), use that:
    subtotal = total - tip

    return subtotal, tip, total


# Save HTML content as a PDF using pdfkit
def save_as_pdf(html_content, pdf_path):
    try:
        pdfkit.from_string(html_content, pdf_path)
        print(f"Saved PDF: {pdf_path}")
        return True
    except Exception as e:
        print(f"Error saving PDF {pdf_path}: {e}")
        return False

# Combine multiple PDFs into a single PDF using PyPDF2
def combine_pdfs(pdf_paths, output_path):
    merger = PdfMerger()
    for pdf in pdf_paths:
        merger.append(pdf)
    merger.write(output_path)
    merger.close()
    print(f"Combined PDF saved to: {output_path}")

def main():
    service = gmail_authenticate()
    
    # Define the date range (you can change these as needed)
    start_date = input("Start date (YYYY-MM-DD): ")
    end_date = input("End date (YYYY-MM-DD): ")
    
    # Refined query:
    # - From noreply@uber.com
    # - Subject containing "[Personal] Your"
    # - Within the date range
    query = (
        'from:noreply@uber.com '
        'subject:"[Personal] Your" '
        f'after:{start_date} before:{end_date}'
    )
    
    threads_result = service.users().threads().list(userId='me', q=query).execute()
    threads = threads_result.get('threads', [])
    print(f"\nFound {len(threads)} email threads matching Uber receipts.\n")
    
    total_subtotal = total_tip = total_amount = 0.0
    processed_receipts = 0
    pdf_files = []
    
    # We'll determine the currency symbol from the first receipt we process.
    global_currency = None
    
    for thread_idx, thread in enumerate(threads, 1):
        last_message = get_last_message(service, thread['id'])
        if last_message:
            content = get_email_content(last_message)
            if content:
                # Determine currency symbol from the content if not already set.
                if global_currency is None:
                    if "₹" in content:
                        global_currency = "₹"
                    elif "$" in content:
                        global_currency = "$"
                    else:
                        global_currency = "$"  # default to USD if none found.
                        
                subtotal, tip, total = extract_amounts(content)
                if subtotal > 0 or total > 0:
                    total_subtotal += subtotal
                    total_tip += tip
                    total_amount += total
                    processed_receipts += 1
                    print(f"[Thread {thread_idx}] Receipt processed: Subtotal={global_currency}{subtotal:.2f}, Tip={global_currency}{tip:.2f}, Total={global_currency}{total:.2f}")
                    
                    # Save this receipt as a PDF.
                    pdf_filename = os.path.join(PDF_FOLDER, f"receipt_{thread_idx}.pdf")
                    if save_as_pdf(content, pdf_filename):
                        pdf_files.append(pdf_filename)
                else:
                    print(f"[Thread {thread_idx}] No valid receipt data found in last message.")
            else:
                print(f"[Thread {thread_idx}] No content found in last message.")
        else:
            print(f"[Thread {thread_idx}] No messages found.")
    
    print("\n--- Summary of Uber Receipts ---")
    print(f"Receipts processed: {processed_receipts} / {len(threads)}")
    print(f"Total excluding tips: {global_currency}{total_subtotal:.2f}")
    print(f"Total tips: {global_currency}{total_tip:.2f}")
    print(f"Total including tips: {global_currency}{total_amount:.2f}")
    
    if pdf_files:
        combined_pdf_path = os.path.join(PDF_FOLDER, "combined_receipts.pdf")
        combine_pdfs(pdf_files, combined_pdf_path)
    else:
        print("No PDF files to combine.")

        
if __name__ == '__main__':
    main()
