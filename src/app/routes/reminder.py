from flask import Blueprint, request, jsonify
from app.services import reminder_nonpaid_email
from app.config.config import Config
from datetime import datetime

reminder_bp = Blueprint("reminder", __name__)

@reminder_bp.route("/payment-reminders", methods=["GET"])
def check_reminders():
    """Check for reminders by scanning emails.
    Query parameters:
      - None
    Returns:
      - JSON object with count and results list.
    """

    results = reminder_nonpaid_email()

    return jsonify({"count": len(results), "results": results}), 200
