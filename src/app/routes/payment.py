from flask import Blueprint, request, jsonify
from app.services import payment_service
from app.config.config import Config
payment_bp = Blueprint("payment", __name__)

@payment_bp.route("/check-payments", methods=["GET"])
def check_payments():
    """Check for payments by scanning emails.
    Query parameters:
      - from: email address to filter by (default: Config.ZEFFY_EMAIL)
      - subject: subject line to filter by (default: Config.ZEFFY_SUBJECT)
    Returns:
      - JSON object with count and results list.
    """
    from_email = request.args.get("from", Config.ZEFFY_EMAIL)
    subject = request.args.get("subject", Config.ZEFFY_SUBJECT)
    results = payment_service(from_email, subject)

    return jsonify({"count": len(results), "results": results}), 200
