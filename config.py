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
    
    # File Storage Configuration
    # STORAGE_BACKEND must be set to either "local" or "digitalocean"
    # - "local": Uses local file system (app/static/uploads/)
    # - "digitalocean": Uses DigitalOcean Spaces (requires all DO_SPACES_* variables)
    # Defaults to "local" in development, must be explicitly set in production/staging
    STORAGE_BACKEND = os.environ.get('STORAGE_BACKEND', '').lower()
    
    # DigitalOcean Spaces configuration (required when STORAGE_BACKEND="digitalocean")
    DO_SPACES_REGION = os.environ.get('DO_SPACES_REGION')
    DO_SPACES_KEY = os.environ.get('DO_SPACES_KEY')
    DO_SPACES_SECRET = os.environ.get('DO_SPACES_SECRET')
    DO_SPACES_BUCKET = os.environ.get('DO_SPACES_BUCKET')
    
    def validate_storage_config(self):
        """Validate storage backend configuration."""
        flask_env = os.environ.get('FLASK_ENV', 'production')
        
        # In development, default to local storage if not specified
        if flask_env == 'development' and not self.STORAGE_BACKEND:
            self.STORAGE_BACKEND = 'local'
        
        # In production/staging, STORAGE_BACKEND must be explicitly set
        if flask_env in ('production', 'staging') and not self.STORAGE_BACKEND:
            raise ValueError(
                f"STORAGE_BACKEND must be explicitly set in {flask_env} environment. "
                "Set to 'local' or 'digitalocean'."
            )
        
        # Validate STORAGE_BACKEND value
        if self.STORAGE_BACKEND not in ('local', 'digitalocean'):
            raise ValueError(
                f"Invalid STORAGE_BACKEND: '{self.STORAGE_BACKEND}'. "
                "Must be 'local' or 'digitalocean'."
            )
        
        # If DigitalOcean is selected, validate all credentials are present
        if self.STORAGE_BACKEND == 'digitalocean':
            missing_vars = []
            if not self.DO_SPACES_REGION:
                missing_vars.append('DO_SPACES_REGION')
            if not self.DO_SPACES_KEY:
                missing_vars.append('DO_SPACES_KEY')
            if not self.DO_SPACES_SECRET:
                missing_vars.append('DO_SPACES_SECRET')
            if not self.DO_SPACES_BUCKET:
                missing_vars.append('DO_SPACES_BUCKET')
            
            if missing_vars:
                raise ValueError(
                    f"STORAGE_BACKEND is set to 'digitalocean' but the following "
                    f"required environment variables are missing: {', '.join(missing_vars)}"
                )
    
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
    STORAGE_BACKEND = 'local'  # Tests always use local storage

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