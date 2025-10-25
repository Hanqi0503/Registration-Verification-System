from app.utils.extraction_tools import extract_form_id, extract_submission_id
from app.utils.database_utils import add_to_csv
from app.utils.file_utils import process_file_uploads

def registration_service(data, pr_amount, normal_amount):
    """
    Processes the request data and returns structured information.

    Args:
        data (dict): Parsed JSON data from the request.
        pr_amount (float): Payment amount for PR status.
        normal_amount (float): Payment amount for normal status.

    Returns:
        dict: Extracted and processed data.
    """

    # Define constants for keys
    FORM_ID = "slug"
    NAME = "q6_legalName"
    FIRST = "first"
    LAST = "last"
    EMAIL = "q8_email"
    PHONE = "q9_phoneNumber"
    FULL = "full"
    PAYER_NAME = "q26_payersName"
    TYPE_OF_STATUS = "q29_areYou"
    PR_CARD_NUMBER = "q11_prCard"
    PR_CARD_URL = "clearFront"
    E_TRANSFER_URL = "uploadEtransfer"

    # Extract form ID from slug
    form_id = extract_form_id(data.get(FORM_ID, ""))

    # Extract personal information
    full_name = f"{data[NAME][FIRST]} {data[NAME][LAST]}"
    email = data.get(EMAIL)
    phone_number = data.get(PHONE, {}).get(FULL)
    payer_full_name = f"{data[PAYER_NAME][FIRST]} {data[PAYER_NAME][LAST]}"
    type_of_status = data.get(TYPE_OF_STATUS)

    if "Yes I am" in type_of_status:
        pr_file_upload_urls = data.get(PR_CARD_URL) \
                                if isinstance(data.get(PR_CARD_URL), list) \
                                else []
        pr_status = True
        pr_card_number = data.get(PR_CARD_NUMBER)
        amount_of_payment = pr_amount
    else:
        pr_status = False
        amount_of_payment = normal_amount

    registration_data = {
        'Form_ID': form_id,
        'Full_Name': full_name,
        'Email': email,
        'Phone_Number': phone_number,
        'PR_Status': pr_status,
        'PR_Card_Number': pr_card_number if pr_status else None,
        'Amount_of_Payment': amount_of_payment,
        'PR_File_Upload_URLs': pr_file_upload_urls if pr_status else None,
        'Payer_Full_Name': payer_full_name,
    }

    if E_TRANSFER_URL in data:
        e_transfer_file_upload_urls = process_file_uploads(data, E_TRANSFER_URL)
        submission_id = extract_submission_id(e_transfer_file_upload_urls)
        registration_data['E_Transfer_File_Upload_URLs'] = e_transfer_file_upload_urls
        registration_data['Submission_ID'] = submission_id
    
    # Store extracted data into app database
    if not add_to_csv(registration_data):
        print("❌ Failed to save registration data to CSV")
        return {"status": "error", "message": "Failed to save registration data"}

    return registration_data

