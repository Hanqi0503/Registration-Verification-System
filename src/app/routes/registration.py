# src/app/routes/registration.py
from flask import Blueprint, request, jsonify
from app.services.registration_service import registration_service

registration_bp = Blueprint("registration", __name__)

@registration_bp.route("/jotform-webhook", methods=["POST"])
def jotform_webhook():
    """
    Accepts JotForm submissions as JSON or form-data.
    Optional query params to override pricing:
      ?pr_amount=150&normal_amount=200
    """
    try:
        # accept JSON or form-data
        payload = request.get_json(silent=True)
        if not payload:
            payload = request.form.to_dict(flat=True)

        if not payload:
            return jsonify({"error": "Missing payload (JSON or form-data)"}), 400

        # pricing with safe defaults
        pr_amount = float(request.args.get("pr_amount", 150))
        normal_amount = float(request.args.get("normal_amount", 200))

        result = registration_service(payload, pr_amount, normal_amount)
        return jsonify({"message": "Processed successfully", "result": result}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
