from app.routes.registration import registration_bp
from app.routes.payment import payment_bp
from app.routes.identification import identification_bp
from app.routes.jotform import jotform_bp
from app.routes.chatbot import chatbot_bp

def register_blueprints(app):
    """Register all app routes."""
    app.register_blueprint(registration_bp, url_prefix="/api")
    app.register_blueprint(payment_bp, url_prefix="/api")
    app.register_blueprint(identification_bp, url_prefix="/api")
    app.register_blueprint(jotform_bp, url_prefix="/api")
    app.register_blueprint(chatbot_bp, url_prefix="/api")