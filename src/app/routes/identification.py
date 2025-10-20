from flask import Blueprint, request, jsonify
from app.services import identification_service
from app.config.config import Config
from datetime import datetime

identification_bp = Blueprint("identification", __name__)

@identification_bp.route("/check-identification", methods=["POST"])
def check_identification():
    """
    Check for identification by scanning images.
    Args:
        None (data comes from request)
    Returns:
        JSON response with status and processed data.
    """
    try:
        data = request.get_json()
        image_url = data.get("image_url")
        if not data:
            return jsonify({"error": "Missing JSON payload"}), 400

        result = identification_service(image_url)

        return jsonify(getattr(result, "to_dict", lambda: {"result": result})())
    
    except Exception as e:
        return jsonify({"error": str(e)}), 400