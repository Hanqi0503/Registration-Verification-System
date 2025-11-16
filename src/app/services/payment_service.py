from app.utils.imap_utils import connect_gmail, create_inform_client_success_email_body, send_email, search_emails, fetch_email, \
        create_inform_client_payment_error_email_body, \
        create_inform_staff_error_email_body, \
        create_inform_staff_success_email_body
from app.utils.database_utils import update_to_csv, get_from_csv
from flask import current_app
import re
from datetime import date
from typing import Optional
from datetime import datetime

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
                    "full_name": payment_info.get("Full_Name")
                })

                continue

            full_name = payment_info.get("Full_Name")

            if full_name is None:
                notify_manually_check = True
                error_messages.append({
                    "update_success": False,
                    "message": "Payer full name missing, manual review needed",
                    "email_subject": email_data['subject']
                })

                continue

            # Fetch with the payer full name and not yet marked as paid
            rows = get_from_csv(match_column=["Full_Name", "Course", "Course_Date", "Paid"], match_value=[full_name, payment_info.get("Course"), payment_info.get("Course_Date"), ""])
            
            if not rows:
                rows = get_from_csv(match_column=["Full_Name", "Course", "Course_Date", "Paid", "Payment_Status"], match_value=[full_name, payment_info.get("Course"), payment_info.get("Course_Date"), True,False])

            if not rows or len(rows) != 1:
                notify_manually_check = True
                error_messages.append({
                    "update_success": False,
                    "message": f"Total {len(rows) if rows else 0} records found for payer name, manual review needed",
                    "email_subject": email_data['subject'],
                    "full_name": full_name
                })

                continue

            target_amount = rows[0].get("Amount_of_Payment")

            if float(target_amount) == actual_amount:
                payment_info['Payment_Status'] = True

            update_success = update_to_csv(payment_info, match_column=["Full_Name", "Course","Course_Date", "Paid"], match_value=[full_name,rows[0].get("Course"), rows[0].get("Course_Date"), ""])
            if not update_success:
                update_success = update_to_csv(payment_info,match_column=["Full_Name", "Course", "Course_Date", "Paid", "Payment_Status"], match_value=[full_name, rows[0].get("Course"), rows[0].get("Course_Date"), True,False])

            results.append({**payment_info, "update_success": update_success})
            print("Payment processing result:", {**payment_info, "update_success": update_success})
            # Step 6: Notify the staff and the client when the payment amount is not correct
            if not payment_info['Payment_Status']:
                notify_manually_check = True
                error_messages.append({
                    "update_success": update_success,
                    "message": "The payment amount does not match the expected amount, manual review needed. Already inform the payer we will cancel the payment.",
                    "expected Amount": target_amount,
                    "actual Paid Amount": actual_amount,
                    "email_subject": email_data['subject'],
                    "full_name": full_name
                })

                if not rows[0].get("Email"):
                    error_messages.append({
                    "update_success": update_success,
                    "message": "The payment amount does not match but not able to notify payer, email missing in database.",
                    "email_subject": email_data['subject'],
                    "full_name": full_name
                })
                else:
                    info = {
                        "Expected Amount": target_amount,
                        "Actual Paid Amount": actual_amount,
                        "Full_name": full_name,
                        "Course": rows[0].get("Course"),
                        "Support Contact": current_app.config.get("CFSO_ADMIN_EMAIL_USER") if rows[0].get("PR_Status") else current_app.config.get("UNIC_ADMIN_EMAIL_USER")
                    }
                    send_email(
                        subject="Course Payment Amount Mismatch - Action Required",
                        recipients=[rows[0].get("Email")],
                        body=create_inform_client_payment_error_email_body(info)
                    )
            else:
                # Step 9: Send notification email to client if all info validated
                print("Payment Status is True, amount match")
                final_rows = get_from_csv(match_column=["Full_Name", "Course","Course_Date", "Paid","Payment_Status","Created_At"], match_value=[full_name, rows[0].get("Course"), rows[0].get("Course_Date"), True,True, rows[0].get("Created_At")])

                if len(final_rows) == 1:
                    if (final_rows[0].get("PR_Status") and final_rows[0].get("PR_Card_Valid")) \
                        or (not final_rows[0].get("PR_Status")):
                        info = {
                            "Form_ID": final_rows[0].get("Form_ID", ""),
                            "Submission_ID": final_rows[0].get("Submission_ID", ""),
                            "Full_Name": final_rows[0].get("Full_Name", ""),
                            "Email": final_rows[0].get("Email", ""),
                            "Phone_Number": final_rows[0].get("Phone_Number", ""),
                            "Course": final_rows[0].get("Course", ""),
                            "Support Contact": current_app.config.get("CFSO_ADMIN_EMAIL_USER") if final_rows[0].get("PR_Status") else current_app.config.get("UNIC_ADMIN_EMAIL_USER"),
                        }
                        send_email(
                            subject=f"{final_rows[0].get('Course')} Registration Confirmation: ALL Validation Passed Successfully!",
                            recipients=[final_rows[0].get("Email", "")],
                            body= create_inform_client_success_email_body(info)
                        )
                        send_email(
                            subject=f"{final_rows[0].get('Course')} Registration Confirmation: ALL Validation Passed Successfully!",
                            recipients=current_app.config.get("ERROR_NOTIFICATION_EMAIL"),
                            body= create_inform_staff_success_email_body(info)
                        )

            if not update_success:
                notify_manually_check = True
                error_messages.append({
                    "update_success": update_success,
                    "message": "Failed to update database record, manual review needed, it may be a missing or multiple full name match in database.",
                    "email_subject": email_data['subject'],
                    "full_name": full_name
                })

        # Step 8: Close Gmail connection
        imap.close()
        imap.logout()

        # Step 9: Notify staff for manual review if needed
        if notify_manually_check:
            formatted_reasons = "\n".join([str(error) for error in error_messages])
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
        
        # Step 10: Only return successful updated to database results
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
        dict: data including updated form_id, payment status, full_name, amount_of_payment, unique_id.
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
    Extract payment information from REAL Zeffy email format.
    
    Based on actual Zeffy template:
    - Full_Name: Participant's Name (First & Last Name) 參加者的姓名（名字和姓氏） :
    - Actual_Paid_Amount: TNew CA$125.00 payment received!
    - Course: Standard First Aid with CPR Level C & AED Certification
    - Course_Date: November 9, 2025 at 9:30 AM EST
    - Payment_Status: False (updated after amount verification)
    - Paid: True if (indicates if full name and payment amount matched)
    
    Args:
        email_body (str): The email body text
        
    Returns:
        dict: Extracted payment information with keys matching database columns
    """
    payment_info = {}
    
    # Extract payer name - Participant's Name (First & Last Name) 參加者的姓名（名字和姓氏） : hiu man suen
    name_patterns = [
        r"Participant's Name.*?:\s*(.+?)\s*I have reviewed"
    ]
    
    for pattern in name_patterns:
        match = re.search(pattern, email_body, re.DOTALL)
        if match:
            # Zeffy format is "Last, First" - keep as is
            payment_info['Full_Name'] = match.group(1).strip().replace(',', '')
            break
    # Extract amount - Real Zeffy format: "Total Amount Received" or "Paid amount"
    amount_patterns = [
        r"New\s*CA\$(\d+\.\d{2})"
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
    # Extract course date - Real Zeffy format: "November 9, 2025 at 4:00 PM EST"
    date_pattern = r"\s*([A-Za-z]+\s+\d{1,2},\s+\d{4}\s+at\s+\d{1,2}:\d{2}\s+[AP]M\s+[A-Z]{3})"
    match = re.search(date_pattern, email_body, re.IGNORECASE)
    if match:
        date_str = match.group(1).strip()
        parsed_date = datetime.strptime(date_str, "%B %d, %Y at %I:%M %p %Z")
        payment_info['Course_Date'] = parsed_date.strftime("%Y-%m-%d")
    # Extract course name: Standard First Aid with CPR Level C & AED Certification @ UNI-Commons x CFSO
    course_pattern = r"^((?!.*New purchase).+?)\s*@ UNI-Commons x CFSO"
    match = re.search(course_pattern, email_body, re.MULTILINE)
    if match:
        payment_info['Course'] = match.group(1).strip()
    # Set payment status to True (paid) if we found key info
    if 'Full_Name' in payment_info and 'Actual_Paid_Amount' in payment_info:
        payment_info['Payment_Status'] = False  # Will be set to True after amount verification
        payment_info['Paid'] = True
        return payment_info
    else:
        return None