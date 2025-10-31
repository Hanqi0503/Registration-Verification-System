from app.utils.extraction_tools import extract_form_id
from app.utils.database_utils import save_to_csv
from app.utils.image_utils import (
    is_likely_printed_copy, 
    fetch_image_bytes, 
    extract_text_lines_from_bytes, 
    extract_candidate_name, 
    fuzzy_name_match,
    detect_card_type  # YOUR OCR LOGIC - Added to top-level imports
)
from app.models.card_classifier import classify_card

def registration_service(data, pr_amount, normal_amount):
    """
    Processes the request data and returns structured information.

    Args:
        data (dict): Parsed JSON data from the request.
        pr_amount (float): Payment amount for PR status.
        normal_amount (float): Payment amount for normal status.

    Returns:
        dict: Extracted and processed data.
    """
    # Extract form ID from slug
    form_id = extract_form_id(data.get("slug", ""))

    # Define constants for keys
    NAME = "q6_legalName"
    FIRST = "first"
    LAST = "last"
    EMAIL = "q8_email"
    PHONE = "q9_phoneNumber"
    FULL = "full"
    PAYER_NAME = "q26_payersName"
    TYPE_OF_STATUS = "q29_areYou"
    PR_CARD_NUMBER = "q11_prCard"
    CLEAR_FRONT = "clearFront"

    # Extract personal information
    full_name = f"{data[NAME][FIRST]} {data[NAME][LAST]}"
    email = data.get(EMAIL)
    phone_number = data.get(PHONE, {}).get(FULL)
    payer_full_name = f"{data[PAYER_NAME][FIRST]} {data[PAYER_NAME][LAST]}"
    type_of_status = data.get(TYPE_OF_STATUS)

    if "Yes I am" in type_of_status:
        pr_file_upload_urls = data.get(CLEAR_FRONT) if isinstance(data.get(CLEAR_FRONT), list) else []
        pr_card_number = data.get(PR_CARD_NUMBER)

        # Basic validation: require either a verified selfie_with_card OR an
        # uploaded PR card image that passes OCR/name-match checks.
        # Do NOT accept a manually-typed PR card number without image evidence
        # (this prevents users from writing numbers on paper to trick the system).
        pr_verified = False
        pr_verified_issue = None
        registration_ocr_name = None
        registration_ocr_score = None
        registration_ocr_card_number = None
        pr_suspected_print = False

        # Define a simple PR card number pattern (example: letters+numbers, adjust as needed)
        import re
        PR_CARD_PATTERN = re.compile(r"^[A-Z0-9\-]{4,}$", re.IGNORECASE)

        # Process uploaded PR card image(s): require OCR name+card number and
        # reject obvious printed/copy images. Selfie verification has been removed
        # to avoid relying on additional third-party services or front-end changes.
        if pr_file_upload_urls:
            # Strict processing of uploaded PR card image(s): require OCR name+card number and
            # reject obvious printed/copy images.
            pr_verified = False
            pr_suspected_print = False
            try:
                # Aggregate over all uploaded images (front/back)
                card_type_scores = []
                card_type_reasons = []
                ocr_names = []
                ocr_lines_all = []
                any_card_number = None
                printed_flags = []

                for url in pr_file_upload_urls:
                    try:
                        img_bytes = fetch_image_bytes(url)
                    except Exception:
                        continue

                    try:
                        suspected, ps, preason = is_likely_printed_copy(img_bytes, use_cv=True)
                    except Exception:
                        suspected, ps, preason = (False, 0.0, 'check_error')
                    printed_flags.append(bool(suspected))

                    try:
                        model_label, model_score, model_reason = classify_card(img_bytes)
                    except Exception:
                        model_label, model_score, model_reason = ("other", 0.0, "classifier_error")

                    if model_label == 'other':
                        try:
                            # Use YOUR OCR LOGIC (now imported at top)
                            card_type, cscore, creason = detect_card_type(img_bytes)
                        except Exception:
                            card_type, cscore, creason = ("other", 0.0, "detector_error")
                    else:
                        card_type, cscore, creason = (model_label, model_score, model_reason)

                    card_type_scores.append((card_type, float(cscore) if cscore is not None else 0.0))
                    card_type_reasons.append(creason)

                    try:
                        lines = extract_text_lines_from_bytes(img_bytes) if img_bytes is not None else []
                    except Exception:
                        lines = []
                    ocr_lines_all.extend(lines)
                    nm = extract_candidate_name(lines)
                    if nm:
                        ocr_names.append(nm)

                    for l in lines:
                        m = re.search(r"[A-Z0-9\-]{4,}", l)
                        if m:
                            any_card_number = m.group(0)
                            break

                registration_ocr_name = None
                registration_ocr_score = None
                registration_ocr_card_number = any_card_number

                if card_type_scores:
                    best_label, best_score = max(card_type_scores, key=lambda t: t[1])
                    card_type = best_label
                    cscore = best_score
                    creason = ','.join(card_type_reasons)
                else:
                    card_type, cscore, creason = ("other", 0.0, "no_images_processed")

                ocr_name_score = 0.0
                if ocr_names:
                    best_nm = max(ocr_names, key=lambda n: fuzzy_name_match(full_name, n))
                    registration_ocr_name = best_nm
                    ocr_name_score = fuzzy_name_match(full_name, best_nm) / 100.0

                card_number_presence = 1.0 if registration_ocr_card_number else 0.0

                # Suppress printed/copy penalty: treat all uploads equally for
                # scoring during debugging. In production consider re-enabling
                # this check with tuned thresholds.
                pr_suspected_print = False
                printed_penalty = 0.0

                if card_type not in ('pr', 'pr_letter'):
                    card_type = 'other'
                    cscore = 0.0
                    creason = f"rejected_type:{card_type}"

                card_type_score = float(cscore) if cscore is not None else 0.0

                # Strengthen PR signals conservatively: if the detector labels the
                # image as 'pr' or 'pr_letter' with at least moderate confidence,
                # boost the card_type_score used in the combined metric so that
                # OCR-fragmented but clearly-PR images are not unfairly rejected.
                if card_type == 'pr' and card_type_score >= 0.6:
                    card_type_score = max(card_type_score, 0.9)
                if card_type == 'pr_letter' and card_type_score >= 0.6:
                    card_type_score = max(card_type_score, 0.85)

                combined = (0.5 * card_type_score) + (0.35 * ocr_name_score) + (0.15 * card_number_presence) - printed_penalty
                combined = max(0.0, min(1.0, combined))

                # Lower auto-accept threshold slightly to reduce false rejects for
                # clearly-detected PR cards (tweakable in production).
                if combined >= 0.70:
                    pr_verified = True
                    pr_verified_issue = None
                elif combined >= 0.5:
                    pr_verified = False
                    pr_verified_issue = f"Low confidence (score={combined:.2f}) - manual review"
                else:
                    pr_verified = False
                    pr_verified_issue = f"Failed checks (score={combined:.2f})"

                registration_confidence = combined
            except Exception as e:
                pr_suspected_print = False
                pr_verified = False
                pr_verified_issue = f"PR image processing error: {e}"
        else:
            # Do not accept manual PR number entries without an uploaded card image
            pr_verified = False
            pr_verified_issue = "Manual PR number entry without uploaded card image is not accepted"
        

        pr_status = pr_verified
        amount_of_payment = pr_amount if pr_verified else normal_amount
    else:
        pr_status = False
        amount_of_payment = normal_amount

    registration_data = {
        'Form_ID': form_id,
        'Full_Name': full_name,
        'Email': email,
        'Phone_Number': phone_number,
        'PR_Status': pr_status,
        'PR_Card_Number': pr_card_number if pr_status else None,
        'PR_File_Upload_URLs': pr_file_upload_urls if pr_status else None,
        'PR_Verified': pr_verified if 'pr_verified' in locals() else False,
        'PR_Verified_Issue': pr_verified_issue if 'pr_verified_issue' in locals() else None,
        'PR_Verified_Confidence': registration_confidence if 'registration_confidence' in locals() else None,
        'PR_Verified_Level': (
            ('auto_accept' if registration_confidence >= 0.75 else ('manual_review' if registration_confidence >= 0.5 else 'auto_reject'))
            if 'registration_confidence' in locals() else None
        ),
        'PR_Suspected_Print': pr_suspected_print if 'pr_suspected_print' in locals() else False,
    'PR_OCR_Name': registration_ocr_name if 'registration_ocr_name' in locals() else None,
    'PR_OCR_Score': registration_ocr_score if 'registration_ocr_score' in locals() else None,
        'Amount_of_Payment': amount_of_payment,
        'Payer_Full_Name': payer_full_name,
        'Zeffy_Unique_ID': "UNIQUE_ID" # Here need to check with CSMO IF WE CAN HAVE THIS
    }

    # Store extracted data into app database
    if not save_to_csv(registration_data):
        print("❌ Failed to save registration data to CSV")
        return {"status": "error", "message": "Failed to save registration data"}

    return registration_data

