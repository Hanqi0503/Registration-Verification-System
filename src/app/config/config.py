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

      (only required if using MongoDB)
      - MONGO_USERNAME: MongoDB username
      - MONGO_PASSWORD: MongoDB password
      - MONGO_CLUSTER: MongoDB cluster URI or identifier

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

    # Admin email credentials
    ADMIN_EMAIL_PASSWORD = os.getenv('ADMIN_EMAIL_PASSWORD')
    ADMIN_EMAIL_USER = os.getenv('ADMIN_EMAIL_USER')

    # Zeffy payment notification
    CHECK_ZEFFY_EMAIL_TIME_BY_MINUTES = os.getenv('CHECK_ZEFFY_EMAIL_TIME_BY_MINUTES')
    ZEFFY_EMAIL= os.getenv('ZEFFY_EMAIL')
    ZEFFY_SUBJECT = os.getenv('ZEFFY_SUBJECT')

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
            'ADMIN_EMAIL_PASSWORD',
            'ZEFFY_EMAIL',
            'ZEFFY_SUBJECT'
        ]
        missing = [name for name in required_vars if not getattr(cls, name)]
        if missing:
            raise RuntimeError(f"Missing required config env vars: {', '.join(missing)}")