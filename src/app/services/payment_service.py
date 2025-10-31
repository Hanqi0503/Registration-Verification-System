from app.config.config import Config
from app.utils.imap_utils import connect_gmail, search_emails, fetch_email
from app.utils.database_utils import update_to_csv
import re

def payment_service(from_email: str, subject_keyword: str) -> dict:
    '''
    Fetch Zeffy payment-related emails using IMAP and store them in DB.

    Args:
        from_email (str): Zeffy email
        subject_keyword (str): Keyword to search in email subjects

    Returns:
        dict: data including updated form_id, payment status, payer_full_name, amount_of_payment, unique_id.
    '''

    # Get Gmail credentials from config
    gmail_user = Config.ADMIN_EMAIL_USER
    gmail_pass = Config.ADMIN_EMAIL_PASSWORD

    try:
        # Step 1: Connect to Gmail
        print(f"Connecting to Gmail as {gmail_user}...")
        imap = connect_gmail(gmail_user, gmail_pass)
        print("✅ Connected to Gmail successfully!")

        # Step 2: Search for Zeffy payment emails
        print(f"Searching for emails from {from_email} with subject '{subject_keyword}'...")
        email_ids = search_emails(imap, from_email=from_email, subject_keyword=subject_keyword)
        print(f"✅ Found {len(email_ids)} email(s)")

        if not email_ids:
            print("⚠️ No Zeffy payment emails found")
            return {
                "status": "no_emails_found",
                "message": "No payment notification emails found"
            }

        # Step 3: Process the most recent email (last one in the list)
        latest_email_id = email_ids[-1]
        print(f"Fetching email ID: {latest_email_id}...")
        email_data = fetch_email(imap, latest_email_id)
        
        print(f"Email Subject: {email_data['subject']}")
        print(f"Email From: {email_data['from']}")
        print(f"Email Body Preview: {email_data['body'][:200]}...")

        # Step 4: Extract payment information from email body
        payment_info = extract_payment_info(email_data['body'])
        
        if not payment_info:
            print("⚠️ Could not extract payment information from email")
            return {
                "status": "extraction_failed",
                "message": "Failed to extract payment details from email",
                "email_subject": email_data['subject']
            }

        print(f"✅ Extracted payment info: {payment_info}")

        # Step 5: Update CSV database
        print("Updating database...")
        update_success = update_to_csv(payment_info)
        
        if update_success:
            print("✅ Database updated successfully!")
        else:
            print("⚠️ Database update failed")

        # Step 6: Close Gmail connection
        imap.close()
        imap.logout()
        print("✅ Disconnected from Gmail")

        # Step 7: Return result
        return {
            "status": "success",
            "message": "Payment processed successfully",
            "payer_full_name": payment_info.get('payer_full_name'),
            "amount_of_payment": payment_info.get('amount_of_payment'),
            "unique_id": payment_info.get('unique_id'),
            "payment_status": payment_info.get('payment_status', 'Paid'),
            "form_id": payment_info.get('form_id', 'N/A')
        }

    except Exception as e:
        print(f"❌ Error in payment_service: {str(e)}")
        return {
            "status": "error",
            "message": f"Error processing payment: {str(e)}"
        }


def extract_payment_info(email_body: str) -> dict:
    """
    Extract payment information from REAL Zeffy email format.
    
    Based on actual Zeffy template:
    - Name of participant: Share, Admin
    - Total Amount Received: $125.00
    - Purchase date: October 9, 2025
    
    Args:
        email_body (str): The email body text
        
    Returns:
        dict: Extracted payment information with keys matching database columns
    """
    payment_info = {}
    
    # Extract payer name - Real Zeffy format: "Name of participant: Last, First"
    name_patterns = [
        r"Name of participant:\s*([A-Za-z\s,]+?)(?:\r|\n|$)",
        r"Buyer details\s+([A-Za-z\s]+)",
    ]
    
    for pattern in name_patterns:
        match = re.search(pattern, email_body, re.IGNORECASE)
        if match:
            # Zeffy format is "Last, First" - keep as is
            payment_info['Payer_Full_Name'] = match.group(1).strip()
            break

    # Extract amount - Real Zeffy format: "Total Amount Received" or "Paid amount"
    amount_patterns = [
        r"Total Amount Received\s+\$?([\d,]+\.?\d*)",
        r"Paid amount:\s*CA?\$?\s*([\d,]+\.?\d*)",
        r"Purchase amount:\s*CA?\$?\s*([\d,]+\.?\d*)",
    ]
    
    for pattern in amount_patterns:
        match = re.search(pattern, email_body, re.IGNORECASE)
        if match:
            amount_str = match.group(1).replace(',', '')
            try:
                payment_info['Actual_Paid_Amount'] = float(amount_str)
                break
            except ValueError:
                continue
    
    # Extract purchase date - Real Zeffy format: "Purchase date: October 9, 2025"
    date_pattern = r"Purchase date:\s*([A-Za-z]+\s+\d{1,2},\s+\d{4})"
    match = re.search(date_pattern, email_body, re.IGNORECASE)
    if match:
        payment_info['Purchase_Date'] = match.group(1).strip()
    
    # Extract course name from subject line
    course_pattern = r"\[CFSO\]\s*(.+?)\s+Payment Confirmation"
    match = re.search(course_pattern, email_body)
    if match:
        payment_info['Course_Name'] = match.group(1).strip()
    
    # Extract transaction/confirmation details if available
    transaction_patterns = [
        r"Transaction Receipt",
        r"Payment method:\s*(.+)",
    ]

    # Set payment status to True (paid) if we found key info
    if 'Payer_Full_Name' in payment_info and 'Actual_Paid_Amount' in payment_info:
        payment_info['Payment_Status'] = False  # Will be set to True after amount verification
        payment_info['Paid'] = True
        return payment_info
    else:
        return None


def create_mock_zeffy_email():
    """
    MOCK FUNCTION: Creates a realistic Zeffy payment notification email for testing.
    
    Based on actual Zeffy email template received from sponsor.
    Use this to test your payment_service function!
    
    Returns:
        str: Mock email body matching real Zeffy format
    """
    mock_email = """
    [CFSO] Standard First Aid Course Payment Confirmation 標準急救證書課程付款確認通知
    
    Thank you for your purchase!
    Purchase details:

    1 x General Admission
    
    OFFICIAL RECEIPT                                                                                     CAD

    Standard First Aid (SFA) Course Fees                                                $125.00

    - Name of participant: Smith, John 

    - Date of course: November 9, 2025 at 4:00 PM EST 

    HST (Tax Free)                                                                                                -        

    Total Amount Received                                                                         $125.00                       

    Hi John,

    Thank you for registering for our Standard First Aid (SFA) Course!
    
    Transaction Receipt

    Buyer details
    John Smith
    Ontario, CA

    Purchase date: October 9, 2025
    Payment method:  ••• ••• •••

    Purchase amount: CA$125.00
    
    Paid amount: CA$125.00
    """
    
    return mock_email