# File: src/app/services/processing_pr_card.py (FINAL, CLEAN CODE)

import re
from typing import Optional, Any
# --- Use correct relative imports to access sibling packages and utilities ---
# NOTE: '..' means go up one directory (from services to app), then look inside 'utils'.
from ..utils import database_utils
from ..utils import image_utils 
from ..utils.extraction_tools import preprocess_image, run_ocr, classify_document_type, extract_pr_fields
# -----------------------------------------------------------------------------------

def processing_pr_card_service(registration_id: str, uploaded_pr_number: Optional[str]) -> dict:
    """
    Processes the PR Card image, runs OCR, performs fraud and consistency validation,
    and updates the database.
    
    Args:
        registration_id (str): Unique ID for the registration record (e.g., Form ID).
        uploaded_pr_number (Optional[str]): PR number manually entered by the client.
        
    Returns:
        dict: Result of the validation and status for database update.
    """
    print(f"--- Starting PR Card Processing for ID: {registration_id} ---")
    
    # 1. FETCH IMAGE URL from Database
    image_url = "http://mock.prcard.jpg" 

    # 2. Download and Preprocess Image
    image_path = "/tmp/image.jpg"
    processed_image = preprocess_image(image_path) 
    
    # 3. Run OCR and Classification
    raw_text, confidence_data = run_ocr(processed_image)
    doc_type = classify_document_type(raw_text, confidence_data)
    
    result = {
        "registration_id": registration_id,
        "document_type": doc_type,
        "pr_status": "FLAGGED", 
        "pr_verified_number": None,
        "message": f"Processed document classified as: {doc_type}"
    }

    # 4. Core Validation Logic (Authenticity & Consistency Check)
    if doc_type in ["PR_CARD", "CONFIRMATION_LETTER"]:
        pr_fields = extract_pr_fields(raw_text)
        extracted_number = pr_fields.get("pr_number")
        
        # Validation A: Basic Authenticity Check (Check confidence/quality)
        if confidence_data.get("avg_conf", 0) < 0.85:
            result["message"] = "FLAGGED: Low OCR confidence or potential non-standard document."
        
        # Validation B: Consistency Check (Does extracted number match user input?)
        elif extracted_number and extracted_number != uploaded_pr_number:
            result["message"] = "VERIFICATION FAILED: Extracted PR No. does not match user input."
        
        # Validation C: High-Confidence Pass
        elif doc_type == "PR_CARD" and confidence_data.get("avg_conf", 0) >= 0.85:
            result["pr_status"] = "VERIFIED"
            result["pr_verified_number"] = extracted_number
            result["message"] = "SUCCESS: PR Card verified with high confidence."
        
        # Fallback for Confirmation Letter or unconfirmed status
        else:
            result["status"] = "FLAGGED_MANUAL_REVIEW"
            result["message"] = f"PENDING: {doc_type} detected. Requires manual review."
    
    elif doc_type.startswith("REJECTED"):
        result["message"] = f"REJECTED: Invalid document type or low quality."

    # 5. Update Database (e.g., update the CSV file)
    database_utils.update_pr_status(result.get("registration_id"), result) 
    
    return result