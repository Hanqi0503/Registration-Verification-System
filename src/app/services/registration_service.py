from datetime import datetime
from app.utils.extraction_tools import extract_form_id
from app.utils.database_utils import save_to_csv

def registration_service(data, pr_amount, normal_amount):
    form_id = (
        extract_form_id(data.get("slug", "")) or
        data.get("id") or data.get("submission_id") or
        datetime.utcnow().strftime("%Y%m%d%H%M%S")
    )

    NAME = "q6_legalName"; PAYER_NAME = "q26_payersName"
    EMAIL = "q8_email";    PHONE = "q9_phoneNumber"
    STATUS = "q29_areYou"; PR_CARD = "q11_prCard"; PR_FILES = "clearFront"

    def _fullname(blob):
        try:
            return f"{(blob.get('first') or '').strip()} {(blob.get('last') or '').strip()}".strip()
        except Exception:
            return ""

    full_name       = _fullname(data.get(NAME, {}) or {})
    payer_full_name = _fullname(data.get(PAYER_NAME, {}) or {})
    email           = (data.get(EMAIL) or "").strip()
    phone_number    = ((data.get(PHONE) or {}).get("full") or "").strip()

    raw_status = (data.get(STATUS) or "").strip().lower()
    is_pr = ("permanent resident" in raw_status) or ("yes i am" in raw_status) or (raw_status == "pr")

    pr_card_number = data.get(PR_CARD) if is_pr else ""
    pr_file_urls   = data.get(PR_FILES) if (is_pr and isinstance(data.get(PR_FILES), list)) else ""

    amount = int(float(pr_amount if is_pr else normal_amount))

    row = {
        "Form_ID":             form_id,
        "Full_Name":           full_name,
        "Email":               email,
        "Phone_Number":        phone_number,
        "PR_Status":           "PR" if is_pr else "No PR",
        "PR_Card_Number":      pr_card_number,
        "PR_File_Upload_URLs": pr_file_urls,
        "Amount_of_Payment":   amount,
        "Payer_Full_Name":     payer_full_name or full_name,
        "Zeffy_Unique_ID":     "",
        "Paid":                "No",
    }

    print("about to save:", row)
    inserted = save_to_csv(row)
    print("save_to_csv returned:", inserted)

    return {"inserted": inserted, "data": row}
