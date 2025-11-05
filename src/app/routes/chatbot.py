from flask import Blueprint, request, jsonify
from app.services import chatbot_service

chatbot_bp = Blueprint("chatbot", __name__)

@chatbot_bp.route("/qa-chatbot", methods=["POST"])
def ask_chatbot():
    """Ask a question to the chatbot.
    Args:
        None (data comes from request)
    Returns:
        JSON response with status and processed data.
    """
    data = request.get_json()
    question = data.get("question")
    answer = chatbot_service(question)
    return jsonify({"answer": answer}), 200
