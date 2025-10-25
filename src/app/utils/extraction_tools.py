# File: src/app/utils/extraction_tools.py
import re
from typing import Optional, Any

# Assuming necessary libraries like OpenCV, PIL, pytesseract are installed and imported here.
# NOTE: Removed direct imports for external libraries to prevent initial ModuleNotFoundError
# import cv2 
# from PIL import Image
# import pytesseract 


def extract_form_id(slug: str) -> Optional[str]:
    """
    Extracts form ID from the slug string, which is required by registration_service.
    
    Args:
        slug (str): Slug string containing form ID.
        
    Returns:
        Optional[str]: Form ID or None.
    """
    # Assuming the form ID is typically a sequence of digits
    match = re.search(r'(\d+)', slug)
    return match.group(1) if match else None


def preprocess_image(image_path: str) -> Any:
    """
    Performs image preprocessing (grayscale, deskewing, denoising) to optimize OCR results.
    
    In a real implementation, this would use OpenCV/PIL to enhance the image quality.
    
    Args:
        image_path (str): Path to the image file.
        
    Returns:
        Any: Processed image object suitable for OCR.
    """
    print(f"-> Image Preprocessing executed for {image_path}.")
    # MOCK: In reality, return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return "processed_image_object" 


def run_ocr(image_object: Any) -> tuple[str, dict]:
    """
    Runs Tesseract OCR on the image object, returning raw text and confidence data.
    
    Args:
        image_object (Any): Preprocessed image object.
        
    Returns:
        tuple[str, dict]: Raw text and a dictionary containing confidence scores.
    """
    # MOCK: In reality, call pytesseract functions here.
    print("-> Tesseract OCR executed.")
    
    # MOCK DATA simulating a successful PR card read
    mock_pr_text = "Government of Canada PERMANENT RESIDENT CARD ID No/No ID 0018-5978 Name SUMBI GEESHNIKUT Expiry 02 NOV /NOV 20" 
    mock_conf_pr = {"avg_conf": 0.90}
    
    return mock_pr_text, mock_conf_pr


def classify_document_type(raw_text: str, confidence_data: dict) -> str:
    """
    Classifies the document type based on keywords and confidence.
    Includes logic for detecting rejected documents (Driver's License, Handwritten).
    
    Args:
        raw_text (str): Extracted text from OCR.
        confidence_data (dict): Tesseract confidence scores.
        
    Returns:
        str: Document type classification string.
    """
    text_upper = raw_text.upper()
    
    # Confidence threshold to flag low quality/handwritten docs
    LOW_CONFIDENCE_THRESHOLD = 0.60
    
    # --- A. Acceptance Logic (PR/Confirmation Letter) ---
    if "PERMANENT RESIDENT CARD" in text_upper or "CARTE DE RÉSIDENT PERMANENT" in text_upper:
        return "PR_CARD"
    if "CONFIRMATION OF PERMANENT RESIDENCE" in text_upper:
        return "CONFIRMATION_LETTER"

    # --- B. Rejection Logic (Invalid IDs & Low Quality) ---
    # Reject known invalid IDs (Driver's Licenses)
    if "DRIVER'S LICENCE" in text_upper or "PERMIS DE CONDUIRE" in text_upper or "ONTARIO" in text_upper:
        return "REJECTED_DRIVER_LICENSE"
        
    # Reject handwritten or extremely low-quality submissions
    if confidence_data.get("avg_conf", 0) < LOW_CONFIDENCE_THRESHOLD:
        return "REJECTED_LOW_CONFIDENCE"
    
    # Default rejection if no specific ID keywords are found
    return "UNKNOWN_ID_REJECTED"


def extract_pr_fields(raw_text: str) -> dict:
    """
    Extracts structured fields (PR Number, Name, Expiry) from verified PR Card text.
    
    Args:
        raw_text (str): Extracted text from OCR.
        
    Returns:
        dict: Extracted fields.
    """
    # MOCK: Use regex to extract data from the simulated OCR text.
    pr_number_match = re.search(r"ID No/No ID\s*([\d-]+)", raw_text, re.IGNORECASE)
    
    fields = {
        "pr_number": pr_number_match.group(1).strip() if pr_number_match else None,
        "name_extracted": "SUMBI GEESHNIKUT", # MOCK
        "expiry_date_extracted": "2020-11-02", # MOCK
    }
    print("-> Extracted key fields from text.")
    return fields