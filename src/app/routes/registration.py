from flask import Blueprint, request, jsonify
from app.services.registration_service import registration_service

registration_bp = Blueprint("registration", __name__)

@registration_bp.route("/jotform-webhook", methods=["POST"])
def jotform_webhook():
    """
    Endpoint for JotForm submissions.
    JotForm will POST form data here.
    Args:
        None (data comes from request)
    Parameters:
        example: /jotform-webhook?pr_amount=150&normal_amount=100
        pr_amount (float): Payment amount for PR status, from URL param.
        normal_amount (float): Payment amount for normal status, from URL param.
    Returns:
        JSON response with status and processed data.
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON payload"}), 400

        # Get optional pricing from URL params
        pr_amount = float(request.args.get("pr_amount"))
        normal_amount = float(request.args.get("normal_amount"))

        if not pr_amount and not normal_amount:
            return jsonify({"error": "Missing pricing parameters"}), 400
        
        result = registration_service(data, pr_amount, normal_amount)
        return jsonify({"message": "Processed successfully", "result": result}), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500
