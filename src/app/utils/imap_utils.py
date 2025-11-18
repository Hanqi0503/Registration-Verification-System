from flask import render_template
from flask_mail import Message

from app.extensions.mail import mail

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