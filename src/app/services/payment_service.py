from app.utils.imap_utils import send_email, \
        create_inform_client_success_email_body, \
        create_inform_client_payment_error_email_body, \
        create_inform_staff_error_email_body, \
        create_inform_staff_success_email_body
from app.utils.database_utils import update_to_csv, get_from_csv

from flask import current_app

import re
from datetime import datetime
from dateutil import parser

def payment_service(id, subject, body) -> dict:
    '''
    Extract Zeffy payment-related email and store it in DB.
    Args:
        id (str): Email ID to of Zeffy payment notifications.
        subject (str): Subject line of Zeffy payment notifications.
        body (date): Date to of emails received since this date.
    Returns: 
       A dictionary containing payment information extracted from the email.
    '''
    notify_manually_check = False
    error_messages = []
    try:
        
        # Step 1: Extract payment information from email body
        payment_info = extract_payment_info(body)

        # Scenario 1: Could not extract payment information
        if not payment_info or not payment_info.get("Actual_Paid_Amount") or not payment_info.get("Full_Name"):
            info = {
                "Form_ID": "",
                "Submission_ID": "",
                "Full_Name": payment_info.get("Full_Name"),
                "Email": subject,
                "Phone_Number": "",
                "Error_Message": f"Failed to extract payment details."
            }

            send_email(
                subject="Manual Review Required for Zeffy Payment Checking: Extraction Failed",
                recipients=current_app.config.get("ERROR_NOTIFICATION_EMAIL"),
                body= create_inform_staff_error_email_body(info)
            )

            return {
                "status": "error",
                "message": f"Failed to extract payment details from email with subject: {subject}"
            }
        
        # Step 2: Extract user's info from the database  

        full_name = payment_info.get("Full_Name")

        # Fetch with the payer full name and not yet marked as paid -> Never paid before
        rows = get_from_csv(
            match_column=[
                "Full_Name", 
                "Course", 
                "Course_Date",
                "Paid"
            ], 
            match_value=[
                full_name, 
                payment_info.get("Course"), 
                payment_info.get("Course_Date"), 
                ""
            ]
        )
        
        if not rows:
            # Fetch with the payer full name and marked as paid but payment status is False -> Paid before but need to correct the amount and repaid again
            rows = get_from_csv(
                match_column=[
                    "Full_Name", 
                    "Course", 
                    "Course_Date", 
                    "Paid", 
                    "Payment_Status"
                ], 
                match_value=[
                    full_name, 
                    payment_info.get("Course"), 
                    payment_info.get("Course_Date"), 
                    True,
                    False
                ]
            )

        if not rows or len(rows) != 1:

            info = {
                "Form_ID": "",
                "Submission_ID": "",
                "Full_Name": full_name,
                "Email": subject,
                "Phone_Number": "",
                "Error_Message": f"There are total {len(rows) if rows else 0} records found for {full_name}, manual review needed."
            }

            send_email(
                subject="Manual Review Required for Zeffy Payment Checking: Multiple or No Records Found",
                recipients=current_app.config.get("ERROR_NOTIFICATION_EMAIL"),
                body= create_inform_staff_error_email_body(info)
            )

            return {
                "status": "error",
                "message": f"Failed to extract payment details from email with subject: {subject}"
            }

        # Step 3: Verify the payment amount
        actual_amount = payment_info.get("Actual_Paid_Amount")
        target_amount = rows[0].get("Amount_of_Payment")

        if float(target_amount) <= actual_amount:
            payment_info['Payment_Status'] = True
        else:
            # Step 4: Notify the staff and the client when the payment amount is not correct
            payment_info['Payment_Status'] = False

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

            info = {
                "Form_ID": "",
                "Submission_ID": "",
                "Full_Name": full_name,
                "Email": subject,
                "Phone_Number": "",
                "Error_Message": f"The payment amount ${actual_amount} does not match the expected amount ${target_amount} , manual review needed. Already inform the payer we will cancel the payment."
            }

            send_email(
                subject="Manual Review Required for Zeffy Payment Checking: Payment Amount Mismatch",
                recipients=current_app.config.get("ERROR_NOTIFICATION_EMAIL"),
                body= create_inform_staff_error_email_body(info)
            )

        # Step 5: Update the database record
        update_success = update_to_csv(
            payment_info, 
            match_column=[
                "Full_Name", 
                "Course",
                "Course_Date", 
                "Paid"
            ], 
            match_value=[
                full_name,
                rows[0].get("Course"), 
                rows[0].get("Course_Date"), 
                ""
            ]
        ) or update_to_csv(
                payment_info,
                match_column=[
                    "Full_Name", 
                    "Course", 
                    "Course_Date", 
                    "Paid", 
                    "Payment_Status"
                ], 
                match_value=[
                    full_name, 
                    rows[0].get("Course"), 
                    rows[0].get("Course_Date"), 
                    True,
                    False
                ]
            )

        if not update_success:

            info = {
                "Form_ID": "",
                "Submission_ID": "",
                "Full_Name": full_name,
                "Email": subject,
                "Phone_Number": "",
                "Error_Message": f"Failed to update database record, manual review needed, it may be a missing or multiple full name match in database."
            }

            send_email(
                subject="Manual Review Required for Zeffy Payment Checking: Update Database Failed",
                recipients=current_app.config.get("ERROR_NOTIFICATION_EMAIL"),
                body= create_inform_staff_error_email_body(info)
            )

 
        # Step 6: Send notification email to client if all info validated

        final_rows = get_from_csv(
            match_column=[
                "Full_Name", 
                "Course",
                "Course_Date", 
                "Paid",
                "Payment_Status",
                "Created_At",
                "PR_Status",
                "PR_Card_Valid"
            ],
            match_value=[
                full_name, 
                rows[0].get("Course"), 
                rows[0].get("Course_Date"), 
                True,
                True, 
                rows[0].get("Created_At"),
                rows[0].get("PR_Status"),
                True if rows[0].get("PR_Status") else ""
            ]
        )
        print(f"Final rows: {final_rows}")

        if final_rows and len(final_rows) == 1:
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

        return {
            "status": "success",
            "message": "Payment processed successfully."
        }
    except Exception as e:

        info = {
                "Form_ID": "",
                "Submission_ID": "",
                "Full_Name": "",
                "Email": subject,
                "Phone_Number": "",
                "Error_Message": f"Error in payment_service: {str(e)}"
            }

        send_email(
            subject="Manual Review Required for Zeffy Payment Checking: Exception Occurred",
            recipients=current_app.config.get("ERROR_NOTIFICATION_EMAIL"),
            body=create_inform_staff_error_email_body(info)
        )
        
        return {
            "status": "error",
            "message": f"Unexpected Error happens during processing payment: {str(e)}"
        }

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
        try:
            # prefer dateutil (handles many TZ formats)
            parsed_date = parser.parse(date_str)
        except Exception:
            # fallback: remove trailing timezone token and parse
            no_tz = date_str.rsplit(' ', 1)[0]  # "November 16, 2025 at 9:30 AM"
            parsed_date = datetime.strptime(no_tz, "%B %d, %Y at %I:%M %p")
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