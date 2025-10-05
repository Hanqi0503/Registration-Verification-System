from app.routes.registration import registration_bp
from app.routes.payment import payment_bp

def register_blueprints(app):
    """Register all app routes."""
    app.register_blueprint(registration_bp, url_prefix="/api")
    app.register_blueprint(payment_bp, url_prefix="/api")