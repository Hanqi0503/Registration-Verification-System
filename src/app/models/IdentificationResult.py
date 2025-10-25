from dataclasses import dataclass, asdict, field
from typing import Dict, List

''' 
Result Model 
It is used to store the result of the document service identification result.  
 '''
@dataclass
class IdentificationResult:
    doc_type: List[str] = field(default_factory=list)  # PR_CARD | PR_CONF_LETTER | DRIVERS_LICENSE | PHOTO_ID | HANDWRITTEN | UNKNOWN
    is_valid: bool = False
    confidence: float = 0.0
    reasons: List[str] = field(default_factory=list)
    raw_text: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict: return asdict(self)
