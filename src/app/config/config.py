import os
from dotenv import load_dotenv

# Load environment variables from the .env file
load_dotenv()

class Config:
    """
    App configuration loaded from environment variables.

    Required:
      - AWS_ACCESS_KEY
      - AWS_SECRET_KEY
      - S3_BUCKET_NAME
      - S3_FILE_KEY
      - ADMIN_EMAIL_USER: admin email address
      - ADMIN_EMAIL_PASSWORD: admin email password

    Optional:
      (defaults)
      - FLASK_HOST: host to run the Flask app on (default: 0.0.0.0)
      - FLASK_PORT: port to run the Flask app on (default: 5000)
      - FLASK_DEBUG: enable/disable debug mode (default: true)
      - REGION_NAME: AWS region (default: us-east-1)

      (only required if using MongoDB)
      - MONGO_USERNAME: MongoDB username
      - MONGO_PASSWORD: MongoDB password
      - MONGO_CLUSTER: MongoDB cluster URI or identifier

      (only required if using Zeffy payment notification)
      - CHECK_ZEFFY_EMAIL_TIME_BY_MINUTES: Interval in minutes to check for Zeffy payment emails (default: 60)
      - ZEFFY_EMAIL: Email address to monitor for Zeffy payment notifications
      - ZEFFY_SUBJECT: Subject line to filter Zeffy payment notification emails

      (only required if using JotForm image URLs)
      - JOTFORM_API_KEY: API key for JotForm

      (only required if using Ninja Image to Text API)
      - NINJA_API_KEY: API key for Image to Text API (api-ninjas.com). See https://api-ninjas.com/api/imagetotext
        to sign up for a free API key.

    Copy .env.example -> .env and fill the required values.
    """
    # Flask
    FLASK_HOST = os.getenv('FLASK_HOST', '0.0.0.0')
    FLASK_PORT = int(os.getenv("FLASK_PORT", 5000))
    FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'true').lower() == 'true'

    # MongoDB
    MONGO_USERNAME = os.getenv('MONGO_USERNAME')
    MONGO_PASSWORD = os.getenv('MONGO_PASSWORD')
    MONGO_CLUSTER = os.getenv('MONGO_CLUSTER')

    # AWS 
    AWS_ACCESS_KEY = os.getenv('AWS_ACCESS_KEY')
    AWS_SECRET_KEY = os.getenv('AWS_SECRET_KEY')
    S3_BUCKET_NAME = os.getenv('S3_BUCKET_NAME')
    S3_FILE_KEY = os.getenv('S3_FILE_KEY')
    REGION_NAME = os.getenv('REGION_NAME', 'us-east-1')

    # Admin email credentials
    ADMIN_EMAIL_PASSWORD = os.getenv('ADMIN_EMAIL_PASSWORD')
    ADMIN_EMAIL_USER = os.getenv('ADMIN_EMAIL_USER')

    # Zeffy payment notification
    CHECK_ZEFFY_EMAIL_TIME_BY_MINUTES = os.getenv('CHECK_ZEFFY_EMAIL_TIME_BY_MINUTES', 60)
    ZEFFY_EMAIL= os.getenv('ZEFFY_EMAIL')
    ZEFFY_SUBJECT = os.getenv('ZEFFY_SUBJECT')

    # Jotform
    JOTFORM_API_KEY = os.getenv('JOTFORM_API_KEY')

    # Image to Text API
    NINJA_API_URL = 'https://api.api-ninjas.com/v1/imagetotext'
    NINJA_API_KEY = os.getenv('NINJA_API_KEY')

    # Opt-in flags to avoid accidental use of paid/third-party services
    # Set these to 'true' in your .env to enable the corresponding features.
    USE_EXTERNAL_OCR = os.getenv('USE_EXTERNAL_OCR', 'false').lower() == 'true'
    USE_S3 = os.getenv('USE_S3', 'false').lower() == 'true'
    USE_MONGO = os.getenv('USE_MONGO', 'false').lower() == 'true'
    # Model-based detector opt-in (TorchScript / ONNX)
    USE_MODEL_DETECTOR = os.getenv('USE_MODEL_DETECTOR', 'false').lower() == 'true'
    # Path to the exported model (TorchScript or ONNX). Default points to the training output.
    MODEL_DETECTOR_PATH = os.getenv('MODEL_DETECTOR_PATH', 'models/model_epoch_2.ts')
    # Confidence threshold to accept a model detection as a positive card match
    # Raise default detector threshold to reduce false positives on printed/handwritten spoofs.
    # Projects can still override via the MODEL_DETECTOR_THRESHOLD env var.
    MODEL_DETECTOR_THRESHOLD = float(os.getenv('MODEL_DETECTOR_THRESHOLD', 0.96))
    # Opt-in: use an external/local model service (HTTP) instead of in-process model
    USE_MODEL_SERVICE = os.getenv('USE_MODEL_SERVICE', 'false').lower() == 'true'
    MODEL_SERVICE_URL = os.getenv('MODEL_SERVICE_URL', 'http://localhost:8000/infer')

    @classmethod
    def validate_required(cls) -> None:
        """
        Validates that all required environment variables are set as class attributes.

        Checks for the presence of the following required environment variables

        Raises:
            RuntimeError: If any of the required environment variables are missing, 
            listing the names of the missing variables.
        """
        required_vars = [
            'AWS_ACCESS_KEY',
            'AWS_SECRET_KEY',
            'S3_BUCKET_NAME',
            'S3_FILE_KEY',
            'ADMIN_EMAIL_USER',
            'ADMIN_EMAIL_PASSWORD'
        ]
        missing = [name for name in required_vars if not getattr(cls, name)]
        if missing:
            raise RuntimeError(f"Missing required config env vars: {', '.join(missing)}")