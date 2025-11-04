from app.utils.imap_utils import connect_gmail, send_email, search_emails, fetch_email, \
        create_inform_client_payment_error_email_body, \
        create_inform_staff_error_email_body
from app.utils.database_utils import update_to_csv, get_from_csv
import re
from datetime import date
from typing import Optional
from flask import current_app

def payment_service_by_email(user: str, pwd: str, from_email: str, subject_keyword: str, since_date: Optional[date] = None) -> list[dict]:
    '''
    Fetch Zeffy payment-related emails using IMAP and store them in DB.
    Args:
    
        user (str): Gmail username
        pwd (str): Gmail app password
        from_email (str): Zeffy email
        subject_keyword (str): Keyword to search in email subjects
        since_date (date): Only search for emails since this date
    Returns: 
        A list of dictionaries containing payment information extracted from the emails.
    '''
    notify_manually_check = False
    error_messages = []
    try:
        # Step 1: Connect to Gmail
        imap = connect_gmail(user, pwd)

        # Step 2: Search for Zeffy payment emails
        email_ids = search_emails(imap, from_email=from_email, subject_keyword=subject_keyword, since_date=since_date)

        if not email_ids:
            return []   

        results = []
        # Step 3: Process all the emails in the set time frame
        for email_id in email_ids:
            email_data = fetch_email(imap, email_id)

            # Step 4: Extract payment information from email body
            payment_info = extract_payment_info(email_data['body'])

            # Could not extract payment information
            if not payment_info:
                notify_manually_check = True
                error_messages.append({
                    "update_success": False,
                    "message": "Failed to extract payment details from email",
                    "email_subject": email_data['subject']
                })

                continue

            # Step 5: Update CSV database

            actual_amount = payment_info.get("Actual_Paid_Amount")

            if actual_amount is None:
                notify_manually_check = True
                error_messages.append({
                    "update_success": False,
                    "message": "Cannot determine actual paid amount, manual review needed",
                    "email_subject": email_data['subject'],
                    "full_name": payment_info.get("Payer_Full_Name")
                })

                continue

            payer_full_name = payment_info.get("Payer_Full_Name")

            if payer_full_name is None:
                notify_manually_check = True
                error_messages.append({
                    "update_success": False,
                    "message": "Payer full name missing, manual review needed",
                    "email_subject": email_data['subject']
                })

                continue

            # Fetch with the payer full name and not yet marked as paid
            rows = get_from_csv(match_column=["Full_Name", "Course", "Paid"], match_value=[payment_info.get("Full_Name"), rows[0].get("Course"), ""])
            
            if len(rows) != 1:
                notify_manually_check = True
                error_messages.append({
                    "update_success": False,
                    "message": f"Total {len(rows)} records found for payer name, manual review needed",
                    "email_subject": email_data['subject'],
                    "full_name": payment_info.get("Payer_Full_Name")
                })

                continue

            target_amount = rows[0].get("Amount_of_Payment")

            if float(target_amount) == actual_amount:
                payment_info['Payment_Status'] = True

            update_success = update_to_csv(payment_info, match_column=["Payer_Full_Name", "Course", "Paid"], match_value=[payment_info.get("Payer_Full_Name"),rows[0].get("Course"), ""])

            results.append({**payment_info, "update_success": update_success})

            # Step 6: Notify the staff and the client when the payment amount is not correct
            if not payment_info['Payment_Status']:
                notify_manually_check = True
                error_messages.append({
                    "update_success": update_success,
                    "message": "The payment amount does not match the expected amount, manual review needed. Already inform the payer we will cancel the payment.",
                    "expected Amount": target_amount,
                    "actual Paid Amount": actual_amount,
                    "email_subject": email_data['subject'],
                    "full_name": payment_info.get("Payer_Full_Name")
                })

                if not rows[0].get("Email"):
                    error_messages.append({
                    "update_success": update_success,
                    "message": "The payment amount does not match but not able to notify payer, email missing in database.",
                    "email_subject": email_data['subject'],
                    "full_name": payment_info.get("Payer_Full_Name")
                })
                else:
                    info = {
                        "Expected Amount": target_amount,
                        "Actual Paid Amount": actual_amount,
                        "Full_name": payment_info.get("Payer_Full_Name", ""),
                        "Course": rows[0].get("Course"),
                        "Support Contact": current_app.config.get("CFSO_ADMIN_EMAIL_USER") if rows[0].get("PR_Status") else current_app.config.get("UNIC_ADMIN_EMAIL_USER")
                    }
                    send_email(
                        subject="Course Payment Amount Mismatch - Action Required",
                        recipients=[rows[0].get("Email")],
                        body=create_inform_client_payment_error_email_body(info)
                    )

            if not update_success:
                notify_manually_check = True
                error_messages.append({
                    "update_success": update_success,
                    "message": "Failed to update database record, manual review needed, it may be a missing or multiple full name match in database.",
                    "email_subject": email_data['subject'],
                    "full_name": payment_info.get("Payer_Full_Name")
                })

        # Step 7: Close Gmail connection
        imap.close()
        imap.logout()

        # Step 8: Notify staff for manual review if needed
        if notify_manually_check:
            formatted_reasons = "\n".join([error['message'] for error in error_messages])
            error_message = f"The error happened because Zeffy payment email search failed with the following reasons:\n{formatted_reasons}"
            
            info = {
                "Form_ID": "",
                "Submission_ID": "",
                "Full_Name": "",
                "Email": "",
                "Phone_Number": "",
                "Error_Message": error_message
            }

            send_email(
                subject="Manual Review Required for Zeffy Payment Checking",
                recipients=current_app.config.get("ERROR_NOTIFICATION_EMAIL"),
                body= create_inform_staff_error_email_body(info)
            )

        # Step 9: Only return successful updated to database results
        return results
    except Exception as e:

        info = {
                "Form_ID": "",
                "Submission_ID": "",
                "Full_Name": "",
                "Email": "",
                "Phone_Number": "",
                "Error_Message": f"Error in payment_service: {str(e)}"
            }

        send_email(
            subject="Manual Review Required for Zeffy Payment Checking",
            recipients=current_app.config.get("ERROR_NOTIFICATION_EMAIL"),
            body=create_inform_staff_error_email_body(info)
        )
        
        return {
            "status": "error",
            "message": f"Error processing payment: {str(e)}"
        }

def payment_service(from_email: str, subject_keyword: str, since_date: Optional[date] = None) -> list[dict]:
    '''
    Fetch CFSO and UNIC mail box Zeffy payment.

    Args:
        from_email (str): Zeffy email
        subject_keyword (str): Keyword to search in email subjects
        since_date (date): Only search for emails since this date

    Returns:
        dict: data including updated form_id, payment status, payer_full_name, amount_of_payment, unique_id.
    '''

    # Get Gmail credentials from config
    cfso_gmail_user = current_app.config.get("CFSO_ADMIN_EMAIL_USER")
    cfso_gmail_pass = current_app.config.get("CFSO_ADMIN_EMAIL_PASSWORD")

    unic_gmail_user = current_app.config.get("UNIC_ADMIN_EMAIL_USER")
    unic_gmail_pass = current_app.config.get("UNIC_ADMIN_EMAIL_PASSWORD")

    results = []
    if cfso_gmail_user and cfso_gmail_pass:
        results.extend(payment_service_by_email(cfso_gmail_user, cfso_gmail_pass, from_email, subject_keyword, since_date))
    if unic_gmail_user and unic_gmail_pass:
        results.extend(payment_service_by_email(unic_gmail_user, unic_gmail_pass, from_email, subject_keyword, since_date))

    return results

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
            payment_info['Full_Name'] = match.group(1).strip()
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
            payment_info['Actual_Paid_Amount'] = float(amount_str)
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
            payment_info['Unique_ID'] = match.group(1).strip()
            break

    # Set payment status to True (paid) if we found key info
    if 'Payer_Full_Name' in payment_info and 'Actual_Paid_Amount' in payment_info:
        payment_info['Payment_Status'] = False
        payment_info['Paid'] = True
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