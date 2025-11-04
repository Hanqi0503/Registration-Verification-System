from flask import Blueprint, request, jsonify
from app.services import jotform_service
import json
jotform_bp = Blueprint("jotform", __name__)

@jotform_bp.route("/jotform-webhook", methods=["POST"])
def jotform_webhook():
    """
    Endpoint for JotForm submissions.
    
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
        data = None
        if request.is_json:
            data = request.get_json(silent=True)
        if data is None and request.form:
            # form-encoded (application/x-www-form-urlencoded or multipart/form-data)
            raw_request = request.form.get('rawRequest')
            if raw_request:
                data = json.loads(raw_request)
            else:
                data = request.get_json(force=True)
        if not data:
            return jsonify({"error": "Missing JSON payload"}), 400

        # Get optional pricing from URL params
        pr_amount = float(request.args.get("pr_amount"))
        normal_amount = float(request.args.get("normal_amount"))

        if not pr_amount and not normal_amount:
            return jsonify({"error": "Missing pricing parameters"}), 400
        
        result = jotform_service(data, pr_amount, normal_amount)
        return jsonify({"message": "Processed successfully", "result": result}), 200
    
    except Exception as e:
        print(f"Error processing JotForm webhook: {e}")
        return jsonify({"error": str(e)}), 500
