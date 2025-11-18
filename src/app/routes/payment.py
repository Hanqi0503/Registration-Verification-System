from flask import Blueprint, request, jsonify
from app.services import payment_service
from app.config.config import Config
from datetime import datetime

payment_bp = Blueprint("payment", __name__)

@payment_bp.route("/check-payment", methods=["POST"])
def check_payments():
    """Check for payments by extracting from email body.
    Args:
        None (data comes from request)
    Returns:
      - JSON response with status and detailed message.
    """

    data = request.get_json()
    if not data:
      return jsonify({"error": "Missing JSON payload"}), 400
    
    id = data.get("id")
    subject = data.get("subject")
    body = data.get("body")

    if not body:
      return jsonify({"error": "Missing email body"}), 400

    result = payment_service(id, subject, body)

    return jsonify(result), 200
