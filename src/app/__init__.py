from flask import Flask
from app.config.config import Config
from app.services.database import init_csv
from app.routes import register_blueprints
from app.background import start_payment_job
from typing import Optional
def create_app(config_object: Optional[str] = None):
    """App factory: load config, init extensions, register blueprints."""
    app = Flask(__name__)
    app.config.from_object(config_object or Config)
    

    # optional: fail fast if required env vars missing
    Config.validate_required()

    app.db = init_csv()
    start_payment_job()
    register_blueprints(app)
    return app