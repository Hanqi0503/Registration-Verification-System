# File: src/app/services/workflow_orchestrator.py

# Import necessary dependencies and services
from .registration_service import registration_service
from .payment_service import payment_service
from .processing_pr_card import processing_pr_card_service

def handle_full_workflow(jotform_data: dict, pr_amount: float, normal_amount: float):
    """
    Handles the full end-to-end workflow: Registration -> PR Check -> Payment Check -> Notification.
    This function orchestrates all services and performs the final conditional logic.
    """
    
    # --- 1. Process and Save Registration Data (using original service) ---
    print("\n[ORCHESTRATOR] Starting initial registration processing...")
    reg_result = registration_service(jotform_data, pr_amount, normal_amount)
    
    if reg_result.get("status") == "error":
        print("[ORCHESTRATOR] ERROR: Initial registration failed.")
        return {"status": "error", "message": "Initial registration failed"}
    
    registration_id = reg_result.get("Form_ID")
    uploaded_pr_number = reg_result.get("PR_Card_Number")
    
    # --- 2. Start PR Card Verification ---
    print(f"[ORCHESTRATOR] Starting PR Card Check for {registration_id}...")
    pr_check_result = processing_pr_card_service(
        registration_id=registration_id, 
        uploaded_pr_number=uploaded_pr_number
    )
    
    pr_status = pr_check_result.get("pr_status")
    
    # --- 3. Start Payment Check (Mocked for Now) ---
    # NOTE: In a final system, payment check is often a daily scheduled job.
    # For demonstration, we assume we can query the payment status by name or ID.
    print("[ORCHESTRATOR] Starting Payment Check (Requires Integration with payment_service queries)...")
    
    # MOCK: Assume payment service successfully checked payment for this user
    payment_is_verified = True  # MOCK SUCCESS
    payment_amount_ok = True    # MOCK CORRECT AMOUNT

    # --- 4. Final Conditional Logic (Business Decision) ---
    
    if pr_status == "VERIFIED" and payment_is_verified and payment_amount_ok:
        final_message = "SUCCESS: Full verification passed. Sending confirmation email."
        # TODO: Trigger successful email generation
    
    elif pr_status == "FLAGGED_MANUAL_REVIEW" and payment_is_verified:
        final_message = "PENDING: PR requires manual staff review. Payment OK."
        # TODO: Trigger staff notification email
        
    elif payment_is_verified and not payment_amount_ok:
        final_message = "FLAGGED: Payment received, but amount is incorrect. Requires manual review."
        # TODO: Trigger 'Paid but wrong amount' email
        
    elif not payment_is_verified:
        final_message = "FLAGGED: Registration received, but no payment found. Sending reminder."
        # TODO: Trigger 'Remember to Pay' email (Time-based check logic needs to be implemented here)
        
    else:
        final_message = "UNKNOWN STATUS. Requires manual review."

    print(f"\n[ORCHESTRATOR] Final Decision: {final_message}")
    return {"status": "completed", "message": final_message, "pr_result": pr_check_result}