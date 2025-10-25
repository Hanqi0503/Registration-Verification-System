import re
from typing import Dict, List, Any

from app.models import IdentificationResult
from app.utils.image_utils import ninja_image_to_text, local_image_to_text,get_image,normalize
from app.utils.aws_utils import AWSService
from app.utils.database_utils import update_to_csv
# ------------------------------------------------------------
# Thresholds
# ------------------------------------------------------------

PR_CARD_KEYWORD_THRESHOLD = 0.5
PR_CARD_POSITION_THRESHOLD = 0.5
PR_CARD_DRIVERS_LICENSE_THRESHOLD = 0.5

# ------------------------------------------------------------
# Keyword sets
# ------------------------------------------------------------

PR_CONF_LETTER_KEYWORDS = [
    r"\bconfirmation\s+of\s+permanent\s+residence\b",
    r"\bimm\s*(5292|5688)\b",
    r"\bclient\s*id\b",
    r"\buci\b",
]

# ------------------------------------------------------------
# Helper functions
# ------------------------------------------------------------
def _relative_position_rules(normalized_results) -> float:
    gov_items = [b for b in normalized_results if b["text"] in ["govemment", "gouvemement", "government","gouvernement","goverment"]]
    canada_boxes = [b for b in normalized_results if "canada" in b["text"]]
    perm_boxes = [b for b in normalized_results if "permanent" in b["text"]]

     # --- 1️⃣ Find all "govemment" and "canada" entries ---
    gov_valid = False
    gov_ref_y = None
    for g in gov_items:
        if g["center_y"] < 0.15 and g["center_x"] < 0.4:
            gov_valid = True
            gov_ref_y = g["center_y"]
            break
    # -- Debug --
    print("All gov items:")
    print(gov_items)
    # --- 2️⃣ Check bottom-right Canada position ---
    bottom_canada = max(canada_boxes, key=lambda b: b["center_y"], default=None)
    canada_valid = False
    if bottom_canada:
        if bottom_canada["center_y"] > 0.8 and bottom_canada["center_x"] > 0.7:
            canada_valid = True
    # -- Debug --
    print("All canada items:")
    print(canada_boxes)
    # --- 3️⃣ Check "permanent" below govemment ---
    perm_valid = False
    if gov_ref_y and perm_boxes:
        tolerance = 0.03  # allow small vertical variation (~3% of image height)
        for p in perm_boxes:
            if abs(p["center_y"] - gov_ref_y) < tolerance:
                perm_valid = True
                break
    # -- Debug --
    print("All permanent items:")
    print(perm_boxes)

    score = 0

    if gov_valid:
        score += 1
    if canada_valid:
        score += 1
    if perm_valid:
        score += 1
    confidence = round(score / 3, 2)
    return confidence

def _keyword_in_ocr(texts) -> float:
    score = 0

    checks = {
        "gov_gouv": ["government", "gouvernement"],
        "perm_res_card": ["permanent", "resident", "card"],
        "id_number": [r"\d{4}-\d{4}"],
        "name_label": ["name", "nom"],
        "id_label": ["id no","no id"],
        "nationality_label": ["nationality","nationalité"],
        "canada": ["canada"],
        "dob": ["date of birth", "date de naissance"],
        "expiry": ["expiry", "expiration"],
    }

    for key, keywords in checks.items():
        pattern = r"\b(" + "|".join(re.escape(k) for k in keywords) + r")\b"
        if any(re.search(pattern, t, re.IGNORECASE) for t in texts):
            score += 1
        
    confidence = round(score / len(checks), 2)

    return confidence

def _keyword_in_drivers_license(texts) -> float:
    score = 0

    pattern =  r"\b(" + "|".join(re.escape(k) for k in ["driver", "licence", "license", "dl"]) + r")\b"

    checks = {
        "dl_number_like": any(re.search(r"[A-Z]{1}\d{4}-\d{5}-\d{5}", t) for t in texts),
        "dl_label": any(re.search(pattern, t, re.IGNORECASE) for t in texts),
    }

    for k, v in checks.items():
        if v:
           score += 1

    confidence = round(score / len(checks), 2)

    return confidence

def _get_id_info(texts,full_name: str,id_number: str) -> str:
    id_pattern  = r"\d{4}-\d{4}"
    if id_number:
        id_pattern = id_number
    name_pattern = full_name
    info = {}
    for t in texts:
        if re.search(id_pattern, t, re.IGNORECASE):
            info["id_number"] = re.search(id_pattern, t).group(0)
        if name_pattern and re.search(name_pattern, t, re.IGNORECASE):
            info["full_name"] = re.search(name_pattern, t).group(0)
    return info

def _get_pr_card_verified_info(valid, confidence: float, details: str) -> Dict[str, Any]:
    pr_card_verified_info  = {}
    pr_card_verified_info['PR_Card_Valid'] = valid
    pr_card_verified_info['PR_Card_Valid_Confidence'] = confidence
    pr_card_verified_info['PR_Card_Details'] = details
    return pr_card_verified_info

# ------------------------------------------------------------
# Main validator
# ------------------------------------------------------------
def identification_service(image_url: str, full_name: str = "", card_number: str = "") -> IdentificationResult:
    image = get_image(source='URL', imgURL=image_url)
    aws = AWSService()
    ocr:  List[Dict[str, Any]] = aws.extract_text_from_image(image)
    norm: List[Dict[str, Any]] = normalize(ocr,image.shape[1], image.shape[0])
    reasons: List[str] = []
    doc: List[str] = []
    valid = False
    mixed_score = 0.0
    notify_manually_check = False
    try:
        texts = [item["text"] for item in norm]
        keyword_confidence = _keyword_in_ocr(texts)
        drive_license_confidence = _keyword_in_drivers_license(texts)

        relative_position_confidence = _relative_position_rules(norm)
         
        # ✅ PR Card
        mixed_score = (keyword_confidence + relative_position_confidence) / 2
        print("Mixed Score:", mixed_score)

        if mixed_score >= 0.55 and drive_license_confidence < 0.5:
            # ! In the future, we will also verify the PR Card number is corresponding to jotform input.
            reasons.append(f"PR Card Check confidence is higher than the threshold.")
            doc.append("PR_CARD")
            valid = True
        else:
            valid = False
            # 🚫 Generic Photo ID
            if keyword_confidence < PR_CARD_KEYWORD_THRESHOLD:
                reasons.append(f"PR Card Keyword found confidence is lower than the threshold.")
                doc.append("Generic_Photo_ID")
            # 🚫 Handwritten
            if relative_position_confidence < PR_CARD_POSITION_THRESHOLD:
                doc.append("HANDWRITTEN")
                reasons += ["Very little structured text; likely hand-written note"]
            # 🚫 Driver’s License
            if drive_license_confidence >= PR_CARD_DRIVERS_LICENSE_THRESHOLD:
                doc = "DRIVERS_LICENSE"
                reasons += [f"Driver’s licence cues (score={drive_license_confidence})"]

        # 1. Get ID Info and Name if give full_name and card_number, making card_number not null if there is fullname
        # 1.1 Return both name and number, correct
        # 1.2 If return name but no number, number is wrong
        # 1.3 If return number but no name, name is wrong
        # 1.4 If return nothing, both wrong
        # 2. Get Extract ID, so only Id number is return
        # 2.1 Check if the extracted ID is in the database and update status
        # 2.2 If not in database, notify the staff to manually check
        # 3. Cannot get extract ID, notify staff to manually check
        find_id_number = True
        id_info = {}
        if full_name and card_number:
            id_info = _get_id_info(texts, full_name, card_number)
            if "full_name" not in id_info or "id_number" not in id_info:
                reasons.append(f"Full name or ID number does not match the input.")
                valid = False
        else:
            id_info = _get_id_info(texts, full_name="", id_number="")
            if "id_number" not in id_info:  
                notify_manually_check = True
                find_id_number = False
                reasons.append(f"Cannot extract ID number from the image; manual review required.")
                valid = False

        identification_result = IdentificationResult(reasons=reasons, doc_type=doc, is_valid=valid, confidence=mixed_score, raw_text=texts)
        
        update_success = False

        card_info = _get_pr_card_verified_info(valid, mixed_score, reasons)

        if find_id_number:
            pr_card_id = id_info.get("id_number", card_number)
            update_success = update_to_csv(card_info, match_column="PR_Card_Number", match_value=pr_card_id)
        else:
            if "full_name" in id_info:
                pr_card_full_name = id_info.get("full_name")
                update_success = update_to_csv(card_info, match_column="Full_Name", match_value=pr_card_full_name)
        
        if not update_success:
            notify_manually_check = True
            reasons.append("Failed to update the database; manual review required.")

        if notify_manually_check:
            # later implement notification to staff
            pass

        result = {**identification_result.__dict__, "update_success": update_success, "PR_Card_INFO": id_info}
        return result
    except Exception as e:
        # ❓ Unknown
        reasons += [str(e)]
        identification_result = IdentificationResult(reasons=reasons, doc_type=doc, is_valid=valid, confidence=mixed_score, raw_text=[item["text"] for item in norm])
        result = {**identification_result.__dict__, "update_success": False}
        if notify_manually_check:
            # later implement notification to staff
            pass
        return result

    # ✅ Confirmation of PR
    '''if copr >= 2:
        doc, valid = "PR_CONF_LETTER", True
        conf = min(0.95, 0.6 + 0.1*copr)
        reasons += [f"CoPR cues (score={copr})"]
        if "uci" in fields: conf += 0.1; reasons.append("UCI/Client ID found")
        if "doc_number" in fields: conf += 0.05; reasons.append("Document number found")
        return IdentificationResult(doc, valid, min(conf, 0.98), reasons, fields, norm, ocr.tried_variants)'''

