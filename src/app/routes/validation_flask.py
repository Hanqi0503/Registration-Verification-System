from flask import Blueprint, request, jsonify
from app.services.document_validator import validate_identity_document

validation_bp = Blueprint("validation", __name__, url_prefix="/validate")


@validation_bp.post("/id")
def validate_id():
    data = request.get_json(silent=True) or {}
    image_url = data.get("image_url")

    if not image_url:
        return jsonify({"error": "image_url is required"}), 400

    try:
        result = validate_identity_document(image_url)

        # ✅ Safely handle both dicts and objects
        if isinstance(result, dict):
            return jsonify(result)
        return jsonify(getattr(result, "to_dict", lambda: {"result": result})())

    except Exception as e:
        return jsonify({"error": str(e)}), 400


