from app.config.config import Config
from app.utils.imap_utils import connect_gmail, search_emails, fetch_email
from app.utils.database_utils import update_to_csv
import re
from datetime import date
from typing import Optional

def payment_service(from_email: str, subject_keyword: str, since_date: Optional[date] = None) -> dict:
    '''
    Fetch Zeffy payment-related emails using IMAP and store them in DB.

    Args:
        from_email (str): Zeffy email
        subject_keyword (str): Keyword to search in email subjects
        since_date (date): Only search for emails since this date

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
        email_ids = search_emails(imap, from_email=from_email, subject_keyword=subject_keyword, since_date=since_date)
        print(f"✅ Found {len(email_ids)} email(s)")

        if not email_ids:
            print("⚠️ No Zeffy payment emails found")
            return []   

        results = []
        # Step 3: Process the most recent email
        for email_id in email_ids:
            print(f"Fetching email ID: {email_id}...")
            email_data = fetch_email(imap, email_id)

            print(f"Email Subject: {email_data['subject']}")
            print(f"Email From: {email_data['from']}")
            print(f"Email Body Preview: {email_data['body'][:200]}...")

            # Step 4: Extract payment information from email body
            payment_info = extract_payment_info(email_data['body'])
            
            if not payment_info:
                print("⚠️ Could not extract payment information from email")
                results.append( {
                    "update_success": False,
                    "message": "Failed to extract payment details from email",
                    "email_subject": email_data['subject']
                })

                continue

            print(f"✅ Extracted payment info: {payment_info}")

            # Step 5: Update CSV database
            print("Updating database...")
            update_success = update_to_csv(payment_info, match_column="Payer_Full_Name", match_value=payment_info.get("payer_full_name"))

            results.append({**payment_info, "update_success": update_success})

            if update_success:
                print("✅ Database updated successfully!")
            else:
                print("⚠️ Database update failed")

        # Step 6: Close Gmail connection
        imap.close()
        imap.logout()
        print("✅ Disconnected from Gmail")

        # Step 7: Return result
        return results

    except Exception as e:
        print(f"❌ Error in payment_service: {str(e)}")
        return {
            "status": "error",
            "message": f"Error processing payment: {str(e)}"
        }


def extract_payment_info(email_body: str) -> dict:
    """
    Extract payment information from Zeffy email body.
    
    Since we don't have real Zeffy emails yet, this function looks for
    common payment notification patterns.
    
    Args:
        email_body (str): The email body text
        
    Returns:
        dict: Extracted payment information
    """
    payment_info = {}
    
    # Extract payer name (common patterns)
    # Pattern 1: "Name: John Doe" or "Donor: John Doe"
    name_patterns = [
        r"Name:\s*([A-Za-z\s]+)(?=\r|\n|$)",
        r"Donor:\s*([A-Za-z\s]+)(?=\r|\n|$)",
        r"From:\s*([A-Za-z\s]+)(?=\r|\n|$)",
        r"Payer:\s*([A-Za-z\s]+)(?=\r|\n|$)"
    ]
    
    for pattern in name_patterns:
        match = re.search(pattern, email_body, re.IGNORECASE)
        if match:
            payment_info['payer_full_name'] = match.group(1).strip()
            break
    
    # Extract amount (common patterns)
    # Pattern: "$50.00" or "Amount: $50.00" or "50.00 CAD"
    amount_patterns = [
        r"\$\s?([\d,]+\.?\d*)",
        r"Amount:\s*\$?\s?([\d,]+\.?\d*)",
        r"([\d,]+\.?\d*)\s*CAD",
        r"Total:\s*\$?\s?([\d,]+\.?\d*)"
    ]
    
    for pattern in amount_patterns:
        match = re.search(pattern, email_body)
        if match:
            amount_str = match.group(1).replace(',', '')
            payment_info['amount_of_payment'] = float(amount_str)
            break
    
    # Extract unique ID / Transaction ID / Reference number
    id_patterns = [
        r"Transaction ID:\s*([A-Z0-9\-]+)",
        r"Reference:\s*([A-Z0-9\-]+)",
        r"ID:\s*([A-Z0-9\-]+)",
        r"Confirmation:\s*([A-Z0-9\-]+)"
    ]
    
    for pattern in id_patterns:
        match = re.search(pattern, email_body, re.IGNORECASE)
        if match:
            payment_info['unique_id'] = match.group(1).strip()
            break

    # Set payment status to True (paid) if we found key info
    if 'payer_full_name' in payment_info and 'amount_of_payment' in payment_info:
        payment_info['payment_status'] = True
        payment_info['paid'] = True
        return payment_info
    else:
        return None


def create_mock_zeffy_email():
    """
    MOCK FUNCTION: Creates a fake Zeffy payment notification email for testing.
    
    This is what a real Zeffy email might look like.
    Use this to test your payment_service function!
    
    Returns:
        str: Mock email body
    """
    mock_email = """
    Payment Notification - Zeffy
    
    Dear Administrator,
    
    A new payment has been received:
    
    Donor: John Smith
    Amount: $150.00 CAD
    Transaction ID: ZFY-2025-10-07-12345
    Date: October 7, 2025
    
    Course: Introduction to Python Programming
    
    Thank you for using Zeffy!
    
    Best regards,
    The Zeffy Team
    """
    
    return mock_email