from flask import current_app
from app.services import identification_service, registration_service
from app.utils.database_utils import get_from_csv
from app.utils.imap_utils import create_inform_staff_ocr_success_email_body, send_email, create_inform_client_success_email_body, create_inform_staff_success_email_body

def jotform_service(data, pr_amount, normal_amount):
    """
    Main service to process JotForm submission data.

    Args:
        data (dict): Parsed JSON data from the JotForm submission.
        pr_amount (float): Payment amount for PR status.
        normal_amount (float): Payment amount for normal status.

    Returns:
        dict: Processed registration information and OCR processing results.
    """
    registration_data = registration_service(data, pr_amount, normal_amount)
    if registration_data.get("PR_Status"):
        try:
            identification_data = identification_service(registration_data.get("PR_File_Upload_URLs")[0], registration_data)

        except Exception as e:
            identification_data = {"status": "error", "message": str(e)}

        if not registration_data.get("status") == "error" and identification_data.get("is_valid") == True :
            info = {
                "Form_ID": registration_data.get("Form_ID", ""),
                "Submission_ID": registration_data.get("Submission_ID", ""),
                "Full_Name": registration_data.get("Full_Name", ""),
                "Email": registration_data.get("Email", ""),
                "Phone_Number": registration_data.get("Phone_Number", ""),
                "Course": registration_data.get("Course", ""),
                "Support Contact": current_app.config.get("CFSO_ADMIN_EMAIL_USER") if registration_data.get("PR_Status") else current_app.config.get("UNIC_ADMIN_EMAIL_USER"),
            }
            send_email(
                subject=f"{registration_data.get('Course')} Registration Confirmation: OCR Validation Passed Successfully!",
                recipients=current_app.config.get("ERROR_NOTIFICATION_EMAIL"),
                body= create_inform_staff_ocr_success_email_body(info)
            )

        result = {
            "registration": registration_data,
            "identification": identification_data
        }
    else:
        info = {
            "Form_ID": registration_data.get("Form_ID", ""),
            "Submission_ID": registration_data.get("Submission_ID", ""),
            "Full_Name": registration_data.get("Full_Name", ""),
            "Email": registration_data.get("Email", ""),
            "Phone_Number": registration_data.get("Phone_Number", ""),
            "Course": registration_data.get("Course", ""),
            "Support Contact": current_app.config.get("CFSO_ADMIN_EMAIL_USER") if registration_data.get("PR_Status") else current_app.config.get("UNIC_ADMIN_EMAIL_USER"),
        }
        send_email(
            subject=f"{registration_data.get('Course')} Registration Confirmation: No OCR Validation Needed!",
            recipients=current_app.config.get("ERROR_NOTIFICATION_EMAIL"),
            body= create_inform_staff_ocr_success_email_body(info)
        )
        
        result = {
            "registration": registration_data
        }

    rows = get_from_csv(match_column=["Full_Name", "Course", "Paid","Payment_Status","Created_At"], match_value=[registration_data.get("Full_Name"), registration_data.get("Course"), True,True, registration_data.get("Created_At")])

    if rows == 1:
        if (rows[0].get("PR_Status") and rows[0].get("PR_Card_Valid")) \
            or (not rows[0].get("PR_Status")):
            info = {
                "Form_ID": registration_data.get("Form_ID", ""),
                "Submission_ID": registration_data.get("Submission_ID", ""),
                "Full_Name": registration_data.get("Full_Name", ""),
                "Email": registration_data.get("Email", ""),
                "Phone_Number": registration_data.get("Phone_Number", ""),
                "Course": registration_data.get("Course", ""),
                "Support Contact": current_app.config.get("CFSO_ADMIN_EMAIL_USER") if registration_data.get("PR_Status") else current_app.config.get("UNIC_ADMIN_EMAIL_USER"),
            }
            send_email(
                subject=f"{registration_data.get('Course')} Registration Confirmation: Registration Confirmation: ALL Validation Passed Successfully!",
                recipients=[registration_data.get("Email", "")],
                body= create_inform_client_success_email_body(info)
            )
            send_email(
                subject=f"{registration_data.get('Course')} Registration Confirmation: Registration Confirmation: ALL Validation Passed Successfully!",
                recipients=current_app.config.get("ERROR_NOTIFICATION_EMAIL"),
                body= create_inform_staff_success_email_body(info)
            )
    
    return result