import re
from typing import Dict, List, Any

from app.models import IdentificationResult
from app.utils.image_utils import ninja_image_to_text, local_image_to_text,get_image,normalize

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

    # --- 2️⃣ Check bottom-right Canada position ---
    bottom_canada = max(canada_boxes, key=lambda b: b["center_y"], default=None)
    canada_valid = False
    if bottom_canada:
        if bottom_canada["center_y"] > 0.8 and bottom_canada["center_x"] > 0.7:
            canada_valid = True

    # --- 3️⃣ Check "permanent" below govemment ---
    perm_valid = False
    if gov_ref_y and perm_boxes:
        tolerance = 0.03  # allow small vertical variation (~3% of image height)
        for p in perm_boxes:
            if abs(p["center_y"] - gov_ref_y) < tolerance:
                perm_valid = True
                break
    score = 0
    if gov_valid:
        score += 1
    if canada_valid:
        score += 1
    if perm_valid:
        score += 1
    confidence = round(score / 3, 2)
    return confidence

def _contains_any(texts,keywords) -> bool:
    return any(k.lower() in t for t in texts for k in keywords)

def _keyword_in_ocr(normalized_results) -> float:
    texts = [item["text"] for item in normalized_results]
    score = 0
    checks = {
        "gov_gouv": _contains_any(texts, ["govemment", "gouvemement", "government","gouvernement","goverment"]),
        "perm_res_card": _contains_any(texts, ["permanent", "resident", "card"]),
        "id_number": any(re.search(r"\d{4}-\d{4}", t) for t in texts),
        "name_label": _contains_any(texts, ["name", "nom"]),
        "canada": _contains_any(texts, ["canada"]),
        "dob": _contains_any(texts, ["date of birth", "naissance"]),
        "expiry": _contains_any(texts, ["expiry", "expiration"]),
    }

    for k, v in checks.items():
        if v:
           score += 1
    confidence = round(score / len(checks), 2)
    return confidence

def _keyword_in_drivers_license(normalized_results) -> float:
    texts = [item["text"] for item in normalized_results]
    score = 0
    checks = {
        "dl_number_like": any(re.search(r"[A-Z]{1}\d{4}-\d{5}-\d{5}", t) for t in texts),
        "dl_label": _contains_any(texts, ["driver", "licence", "license", "dl"]),
    }

    for k, v in checks.items():
        if v:
           score += 1
    confidence = round(score / len(checks), 2)
    return confidence

# ------------------------------------------------------------
# Main validator
# ------------------------------------------------------------
def identification_service(image_url: str) -> IdentificationResult:
    image = get_image(source='URL', imgURL=image_url)
    ocr:  List[Dict[str, Any]] = ninja_image_to_text(image)
    norm: List[Dict[str, Any]] = normalize(ocr,image.shape[1], image.shape[0])
    reasons: List[str] = []
    doc: List[str] = []
    valid = False
    try:
        relative_position_confidence = _relative_position_rules(norm)
        keyword_confidence = _keyword_in_ocr(norm)
        drive_license_confidence = _keyword_in_drivers_license(norm)
        # ✅ PR Card
        mixed_score = (keyword_confidence + relative_position_confidence) / 2
        print("Mixed Score:", mixed_score)
        if mixed_score >= 0.55 and drive_license_confidence < 0.5:
            reasons.append(f"PR Card Check confidence is higher than the threshold.")
            doc.append("PR_CARD")
            valid = True
            
            return IdentificationResult(reasons=reasons, doc_type=doc, is_valid=valid, confidence=mixed_score, raw_text=[item["text"] for item in norm])
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

            conf = max(keyword_confidence, relative_position_confidence, drive_license_confidence)
            return IdentificationResult(reasons=reasons, doc_type=doc, is_valid=valid, confidence=conf, raw_text=[item["text"] for item in norm])
    except Exception as e:
        # ❓ Unknown
        reasons += [str(e)]
        return IdentificationResult(reasons=reasons, doc_type=doc, is_valid=valid, confidence=mixed_score, raw_text=[item["text"] for item in norm])

    # ✅ Confirmation of PR
    '''if copr >= 2:
        doc, valid = "PR_CONF_LETTER", True
        conf = min(0.95, 0.6 + 0.1*copr)
        reasons += [f"CoPR cues (score={copr})"]
        if "uci" in fields: conf += 0.1; reasons.append("UCI/Client ID found")
        if "doc_number" in fields: conf += 0.05; reasons.append("Document number found")
        return IdentificationResult(doc, valid, min(conf, 0.98), reasons, fields, norm, ocr.tried_variants)'''

