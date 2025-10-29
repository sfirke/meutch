import os
from dotenv import load_dotenv
import logging

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        if os.environ.get('FLASK_ENV') == 'development':
            SECRET_KEY = 'dev-key-change-this'
        else:
            raise ValueError(
                "SECRET_KEY environment variable must be set for production. "
                "Please set it in your deployment platform's environment variables. "
                "You can generate one with: python -c 'import secrets; print(secrets.token_hex(32))'"
            )
    
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # DigitalOcean Spaces configuration (optional for local development)
    # If all credentials are provided, DO Spaces will be used for file storage.
    # Otherwise, local file storage is used automatically.
    DO_SPACES_REGION = os.environ.get('DO_SPACES_REGION')
    DO_SPACES_KEY = os.environ.get('DO_SPACES_KEY')
    DO_SPACES_SECRET = os.environ.get('DO_SPACES_SECRET')
    DO_SPACES_BUCKET = os.environ.get('DO_SPACES_BUCKET')
    
    # Mailgun configuration
    MAILGUN_API_KEY = os.environ.get('MAILGUN_API_KEY')
    MAILGUN_DOMAIN = os.environ.get('MAILGUN_DOMAIN')
    MAILGUN_API_URL = f"https://api.mailgun.net/v3/{os.environ.get('MAILGUN_DOMAIN')}/messages" if os.environ.get('MAILGUN_DOMAIN') else None

    # Environment-based configuration
    DEBUG = os.environ.get('FLASK_ENV') == 'development'
    LOG_LEVEL = logging.DEBUG if DEBUG else logging.INFO
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    LOG_FILE = 'app.log'

class TestingConfig(Config):
    """Configuration for testing environment"""
    TESTING = True
    WTF_CSRF_ENABLED = False  # Disable CSRF for testing
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SECRET_KEY = 'test-secret-key'
    # Tests use local storage (no DO Spaces credentials configured)

class StagingConfig(Config):
    """Configuration for staging environment"""
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    LOG_LEVEL = logging.INFO
    DO_SPACES_BUCKET = os.environ.get('DO_SPACES_BUCKET')


class ProductionConfig(Config):
    """Configuration for production environment"""
    DEBUG = False
    LOG_LEVEL = logging.WARNING
    
    # Production should always use specific environment variables
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    
    def init_app(self, app):
        super().init_app(app)
        # Validate required environment variables when app is initialized
        if not os.environ.get('DATABASE_URL'):
            raise ValueError("DATABASE_URL must be set for production")


# Configuration mapping
config = {
    'development': Config,
    'testing': TestingConfig,
    'staging': StagingConfig,
    'production': ProductionConfig,
    'default': Config
}