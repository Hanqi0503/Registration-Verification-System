from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.document_validator import validate_identity_document

router = APIRouter(prefix="/validate", tags=["validation"])

class ValidateRequest(BaseModel):
    image_url: str

@router.post("/id")
def validate_id(req: ValidateRequest):
    try:
        result = validate_identity_document(req.image_url)
        return result.to_dict()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
