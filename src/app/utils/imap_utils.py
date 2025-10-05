import imaplib
import email
from email.header import decode_header

def connect_gmail(username: str, app_password: str):
    """
    Connect to Gmail using IMAP and login.
    """
    imap = imaplib.IMAP4_SSL("imap.gmail.com")
    imap.login(username, app_password)
    return imap

def search_emails(imap, from_email=None, subject_keyword=None):
    """Search Gmail inbox for specific sender and/or subject."""
    imap.select("inbox")

    # Build search query
    criteria = []
    if from_email:
        criteria.append(f'FROM "{from_email}"')
    if subject_keyword:
        criteria.append(f'SUBJECT "{subject_keyword}"')

    search_query = " ".join(criteria) if criteria else "ALL"

    status, messages = imap.search(None, search_query)
    email_ids = messages[0].split()
    return email_ids

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