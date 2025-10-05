from flask import Blueprint, request, jsonify
from app.services.payment_service import payment_service
from app.config.config import Config
payment_bp = Blueprint("payment", __name__)

@payment_bp.route("/check-payments", methods=["GET"])
def check_payments():
    from_email = request.args.get("from", Config.ZEFFY_EMAIL)
    subject = request.args.get("subject", Config.ZEFFY_SUBJECT)
    results = payment_service(from_email, subject)
    return jsonify({"count": len(results), "results": results})
