from __future__ import annotations
import re
from dataclasses import dataclass, asdict
from typing import Dict, List
from app.services.ocr_service import ocr_image_from_url, OCRResult

# ------------------------------------------------------------
# ✅ Result Model
# ------------------------------------------------------------
@dataclass
class ValidationResult:
    doc_type: str            # PR_CARD | PR_CONF_LETTER | DRIVERS_LICENSE | PHOTO_ID | HANDWRITTEN | UNKNOWN
    is_valid: bool
    confidence: float
    reasons: List[str]
    extracted: Dict[str, str]
    raw_text: str
    ocr_variants: int
    def to_dict(self) -> Dict: return asdict(self)

# ------------------------------------------------------------
# ✅ Keyword sets
# ------------------------------------------------------------
PR_CARD_KEYWORDS = [
    r"\bpermanent\s+resident\s+card\b",
    r"\bcarte\s+de\s+r[ée]sident\s+permanent\b",
    r"\bircc\b",
    r"\bimmigration,\s*refugees?\s+and\s+citizenship\s+canada\b",
    r"\bpr\s*card\b",
    r"\bpr\s*number\b",
]
PR_CONF_LETTER_KEYWORDS = [
    r"\bconfirmation\s+of\s+permanent\s+residence\b",
    r"\bimm\s*(5292|5688)\b",
    r"\bclient\s*id\b",
    r"\buci\b",
]
DRIVERS_LICENSE_KEYWORDS = [
    r"\bdriver'?s?\s+licen[sc]e\b",
    r"\bdl\s*#?\b",
    r"\bclass\s*[a-z0-9]+\b",
    r"\bministry\b",
    r"\bprovince\b|\bontario\b|\bbc\b|\balberta\b|\bqu[eé]bec\b|\bmanitoba\b|\bnew\s+brunswick\b|\bns\b|\bnl\b|\bpe\b|\bsaskatchewan\b|\byukon\b|\bnunavut\b|\bnwt\b",
    r"\bdate\s+of\s+issue\b|\bissue\s+date\b",
]
PHOTO_ID_KEYWORDS = [
    r"\bphoto\s+id\b|\bid\s+card\b|\bidentification\b|\bstate\s+id\b|\bhealth\s+card\b|\bnational\s+id\b",
]

UCI_PAT   = re.compile(r"\b(uci|client\s*id)\s*[:#]?\s*([0-9]{8,10})\b", re.I)
DOCNO_PAT = re.compile(r"\b(document|id)\s*(no|number)?\s*[:#]?\s*([A-Z0-9\-]{6,})\b", re.I)
DATE_PAT  = re.compile(r"\b(\d{4}[-/]\d{2}[-/]\d{2}|\d{2}\s*[A-Za-z]{3}\s*\d{4})\b", re.I)
NAME_FIELDS = [r"\bsurname\b|\bnom\b", r"\bgiven\s*name(?:s)?\b|\bpr[ée]noms?\b"]
DL_NUM_PAT = re.compile(r"\b([A-Z]\d{4}[- ]?\d{5}[- ]?\d{5})\b")

# ------------------------------------------------------------
# ✅ Helper functions
# ------------------------------------------------------------
def _normalize(t: str) -> str:
    return re.sub(r"[ \t\r\n]+", " ", (t or "")).strip().lower()

def _score(text: str, pats: List[str]) -> int:
    return sum(1 for p in pats if re.search(p, text, re.I))

def _extract(text: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    if m := UCI_PAT.search(text):   out["uci"] = m.group(2)
    if m := DOCNO_PAT.search(text): out["doc_number"] = m.group(3)
    dates = DATE_PAT.findall(text)
    if dates: out["dates_found"] = ", ".join(d if isinstance(d, str) else d[0] for d in dates[:3])
    for nf in NAME_FIELDS:
        if re.search(nf, text, re.I): out["name_fields_present"] = "true"
    if m := DL_NUM_PAT.search(text): out["dl_number_like"] = m.group(1)
    return out

def _looks_handwritten(text: str) -> bool:
    words = re.findall(r"[A-Za-z0-9]+", text)
    return len(words) <= 12 and len(" ".join(words)) < 60

# ------------------------------------------------------------
# ✅ Main validator
# ------------------------------------------------------------
def validate_identity_document(image_url: str) -> ValidationResult:
    ocr: OCRResult = ocr_image_from_url(image_url)
    norm = _normalize(ocr.text)
    fields = _extract(norm)
    reasons: List[str] = []
    doc = "UNKNOWN"; valid = False; conf = 0.35

    pr_card = _score(norm, PR_CARD_KEYWORDS)
    copr    = _score(norm, PR_CONF_LETTER_KEYWORDS)
    dl      = _score(norm, DRIVERS_LICENSE_KEYWORDS)
    pid     = _score(norm, PHOTO_ID_KEYWORDS)

    # 🚫 Driver’s License
    if dl >= 2 or ("dl_number_like" in fields and dl >= 1):
        doc, valid = "DRIVERS_LICENSE", False
        conf = min(1.0, 0.5 + 0.1*dl)
        reasons += [f"Driver’s licence cues (score={dl})"]
        if "dl_number_like" in fields: reasons.append("DL-like number present")
        return ValidationResult(doc, valid, conf, reasons, fields, norm, ocr.tried_variants)

    # 🚫 Generic Photo ID
    if pid >= 2 and pr_card == 0 and copr == 0:
        doc, valid = "PHOTO_ID", False
        conf = min(1.0, 0.45 + 0.1*pid)
        reasons += [f"Generic photo ID cues (score={pid})"]
        return ValidationResult(doc, valid, conf, reasons, fields, norm, ocr.tried_variants)

    # ✅ Confirmation of PR
    if copr >= 2:
        doc, valid = "PR_CONF_LETTER", True
        conf = min(0.95, 0.6 + 0.1*copr)
        reasons += [f"CoPR cues (score={copr})"]
        if "uci" in fields: conf += 0.1; reasons.append("UCI/Client ID found")
        if "doc_number" in fields: conf += 0.05; reasons.append("Document number found")
        return ValidationResult(doc, valid, min(conf, 0.98), reasons, fields, norm, ocr.tried_variants)

    # ✅ PR Card
    if pr_card >= 2:
        doc, valid = "PR_CARD", True
        conf = min(0.95, 0.6 + 0.1*pr_card)
        reasons += [f"PR card cues (score={pr_card})"]
        if "uci" in fields: conf += 0.1; reasons.append("UCI/Client ID found")
        if "doc_number" in fields: conf += 0.05; reasons.append("Document number found")
        if "name_fields_present" in fields: conf += 0.05; reasons.append("Surname/Given names fields present")
        return ValidationResult(doc, valid, min(conf, 0.98), reasons, fields, norm, ocr.tried_variants)

    # 🚫 Handwritten
    if _looks_handwritten(norm):
        doc, valid, conf = "HANDWRITTEN", False, 0.6
        reasons += ["Very little structured text; likely hand-written note"]
        return ValidationResult(doc, valid, conf, reasons, fields, norm, ocr.tried_variants)

    # ❓ Unknown
    reasons += ["No strong matches for PR/CoPR or non-PR IDs"]
    return ValidationResult(doc, valid, conf, reasons, fields, norm, ocr.tried_variants)

