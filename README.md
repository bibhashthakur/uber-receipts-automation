

# Uber Receipt Parser & PDF Exporter

This script automatically extracts and compiles Uber trip receipt data from your Gmail account. It reads all receipt emails from `noreply@uber.com`, parses details like subtotal, tip, and total, and saves each as a PDF. All PDFs are then combined into a single file for easy viewing or expense tracking.

## Features

- Parses Uber receipt emails (USD or INR)
- Extracts Subtotal, Tip, and Total
- Saves each email as a PDF
- Combines all receipts into a single PDF
- Supports Gmail authentication via OAuth2

## Setup

### 1. Clone this repository

```
git clone https://github.com/bibhashthakur/uber-receipts-automation.git
cd uber-receipts-automation
```

### 2. Install dependencies
```
pip install -r requirements.txt
```

### 3. Install wkhtmltopdf

Required by pdfkit to generate PDFs.

* Download wkhtmltopdf
* Ensure it's available in your system PATH.

### 4. Set up Gmail API credentials
* Go to Google Cloud Console
* Enable the Gmail API
* Create OAuth client credentials (Desktop App)
* Download the credentials.json file and place it in this directory

### 5. Run the script
```
python main.py
```
You will be prompted to authenticate with your Google account on first run.

### Output
* Individual receipt PDFs are saved to the receipts_pdf/ folder
* A merged file called combined_receipts.pdf is also generated in that folder

### License

MIT License