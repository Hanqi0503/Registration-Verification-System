from datetime import date, datetime
import imaplib
import email
from email.header import decode_header
from flask import render_template

from flask_mail import Message

from app.extensions.mail import mail
from app.config.config import Config

def connect_gmail(username: str, app_password: str):
    """
    Connect to Gmail using IMAP and login.
    """
    imap = imaplib.IMAP4_SSL("imap.gmail.com")
    imap.login(username, app_password)
    return imap

def search_emails(imap, from_email=None, subject_keyword=None, since_date=None):
    """Search Gmail inbox for specific sender and/or subject."""
    imap.select("inbox")

    # Build search query
    criteria = []
    if from_email:
        criteria.append(f'FROM "{from_email}"')
    if subject_keyword:
        criteria.append(f'SUBJECT "{subject_keyword}"')

    # Optional date filter (SINCE)
    if since_date:
        # Allow either a string like "07-Oct-2025" or datetime object
        if isinstance(since_date, datetime):
            since_str = since_date.strftime("%d-%b-%Y")
        elif isinstance(since_date, date):
            since_str = since_date.strftime("%d-%b-%Y")
        elif isinstance(since_date, str):
            # Expecting "DD-Mon-YYYY" format already
            since_str = since_date
        else:
            raise TypeError("since_date must be datetime, date, or IMAP-formatted string")
        criteria.append(f'SINCE {since_str}')

    search_query = " ".join(criteria) if criteria else "ALL"

    status, messages = imap.search(None, search_query)
    if status != "OK":
        print("❌ IMAP search failed:", status)
        return []

    return messages[0].split()

def fetch_email(imap, email_id):
    """Fetch and decode an email by ID."""
    status, msg_data = imap.fetch(email_id, "(RFC822)")
    msg = email.message_from_bytes(msg_data[0][1])

    # Decode subject
    subject, encoding = decode_header(msg["Subject"])[0]
    if isinstance(subject, bytes):
        subject = subject.decode(encoding or "utf-8", errors="ignore")

    # Extract plain text body
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain":
                body = part.get_payload(decode=True).decode(errors="ignore")
                break
    else:
        body = msg.get_payload(decode=True).decode(errors="ignore")

    return {"subject": subject, "body": body, "from": msg.get("From")}

def send_email(subject: str, recipients: list, body: str) -> bool:

    msg = Message(
        subject=subject,
        recipients=recipients,
        html=body
    )

    mail.send(msg)

    return True

def create_inform_client_success_email_body(info: dict) -> str:
    client_email_body = render_template(
        'inform_client_success.html',
        form_id=info['Form_ID'],
        submission_id=info['Submission_ID'],
        full_name=info['Full_Name'],
        email=info['Email'],
        phone_number=info['Phone_Number'],
        course=info['Course'],
        support_contact=info['Support Contact']
    )

    return client_email_body
    
def create_inform_staff_success_email_body(info: dict) -> str:

    staff_email_body = render_template(
        'inform_staff_success.html',
        form_id=info['Form_ID'],
        submission_id=info['Submission_ID'],
        full_name=info['Full_Name'],
        email=info['Email'],
        phone_number=info['Phone_Number']
    )

    return staff_email_body

def create_inform_staff_ocr_success_email_body(info: dict) -> str:

    staff_email_body = render_template(
        'inform_staff_register_success.html',
        form_id=info['Form_ID'],
        submission_id=info['Submission_ID'],
        full_name=info['Full_Name'],
        email=info['Email'],
        phone_number=info['Phone_Number']
    )

    return staff_email_body

def create_inform_staff_error_email_body(info: dict) -> str:

    staff_email_body = render_template(
        'inform_staff_error.html',
        form_id=info['Form_ID'],
        submission_id=info['Submission_ID'],
        full_name=info['Full_Name'],
        email=info['Email'],
        phone_number=info['Phone_Number'],
        error_message=info['Error_Message']
    )

    return staff_email_body

def create_inform_client_payment_error_email_body(info: dict) -> str:
    
    client_email_body = render_template(
        'inform_client_payment_error.html',
        course = info['Course'],
        full_name=info['Full_name'],
        expected_amount=info['Expected Amount'],
        actual_amount=info['Actual Paid Amount'],
        support_contact=info['Support Contact'],
    )

    return client_email_body

def create_inform_client_payment_reminder_email_body(info: dict) -> str:

    client_email_body = render_template(
        'inform_client_payment_reminder.html',
        course = info['Course'],
        full_name=info['Full_name'],
        course_date=info['Course Date'],
        payment_link=info['Payment Link'],
        support_contact=info['Support Contact'],
    )

    return client_email_body

def create_inform_staff_reminder_report_email_body(info: dict) -> str:

    client_email_body = render_template(
        'inform_staff_reminder_report.html',
        details = info['Details'],
        success= info['Success'],
        fail= info["Fail"]
    )

    return client_email_body