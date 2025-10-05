from app.config.config import Config
def payment_service(from_email: str, subject_keyword: str) -> dict :
    '''
    Fetch Zeffy payment-related emails using IMAP and store them in DB.

    Args:
        from_email (str): Zeffy email
        subject_keyword (str): Keyword to search in email subjects

    Returns:
        dict: data including updated form_id, payment status, payer_full_name, amount_of_payment, unique_id.
    '''

    """
    Hint: How to use IMAP
    Turn on IMAP in Gmail:
    Settings → See all settings → Forwarding and POP/IMAP → Enable IMAP
    """

    gmail_user = Config.ADMIN_EMAIL_USER

    """
    Hint: How to create an App Password:
    Google Account → Security → App passwords → Select app "Mail" → Device "Other (Flask)" → Generate

    Use that 16-character password instead of your actual Gmail password.
    """
    gmail_pass = Config.ADMIN_EMAIL_PASSWORD

    # using functions in app.utils.imap_utils to connect with gmail and search Zeffy mail and then extract body
    # Check mail body to find payer_full_name, amount_of_payment and unique_id
    # Since we haven't had Zeffy notification mail, please mock one by yourself
    # Update Record for db using update_to_csv in app.utils.database_utils.py, should use payer_name and unique_id to do search record and update Paid column to True or False.