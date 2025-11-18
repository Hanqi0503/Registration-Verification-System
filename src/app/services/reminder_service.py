from app.utils.database_utils import get_from_sheet
from app.utils.imap_utils import create_inform_client_payment_reminder_email_body, create_inform_staff_reminder_report_email_body, send_email
from flask import current_app
from datetime import datetime, timedelta

def reminder_nonpaid_email() -> str:
    yesterday = (datetime.utcnow() - timedelta(days=1)).strftime('%Y-%m-%d')
    rows = get_from_sheet(match_column=["Paid", "Created_At"], match_value=["",yesterday])
    detail = []
    try:
        for row in rows:
            email = row.get("Email")
            full_name = row.get("Full_Name")
            course = row.get("Course")
            course_date = row.get("Course_Date")
            payment_link = row.get("Payment_Link")
            support_contact = current_app.config.get("CFSO_ADMIN_EMAIL_USER") if row.get("PR_Status") else current_app.config.get("UNIC_ADMIN_EMAIL_USER")
            info = {
                "Course": course,
                "Course Date": course_date,
                "Full_name": full_name,
                "Payment Link": payment_link,
                "Support Contact": support_contact,
                "Notified": False
            }

            detail.append(info)

            send_email(
                subject=f"CFSO X UNIC Payment Reminder: {course} on {course_date}",
                recipients=[email],
                body=create_inform_client_payment_reminder_email_body(info)
            )
            
            last_info = detail[-1]
            last_info["Notified"] = True
            detail[-1] = last_info

    except Exception as e:
        pass
    finally:
        if rows and len(rows) > 0:
            success_count = len([d for d in detail if d["Notified"]])
            fail_count = len(detail) - success_count
            info = {
                "Details": detail,
                "Success": success_count,
                "Fail": fail_count
            }

            send_email(
                subject=f"Reminder Report",
                recipients=current_app.config.get("ERROR_NOTIFICATION_EMAIL"),
                body=create_inform_staff_reminder_report_email_body(info)
            )
    
    return detail