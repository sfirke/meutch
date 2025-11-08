import os
from dotenv import load_dotenv
import logging

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv()


def parse_email_allowlist(raw_string):
    """Parse EMAIL_ALLOWLIST from comma-separated string.
    
    Args:
        raw_string: Raw string from environment variable (may contain leading/trailing whitespace)
    
    Returns:
        List of lowercase email addresses if raw_string is non-empty after stripping, otherwise None.
        Empty entries (from extra commas or whitespace-only tokens) are filtered out.
        Emails are normalized to lowercase for case-insensitive comparison.
    """
    stripped = raw_string.strip() if raw_string else ''
    if not stripped:
        return None
    return [email.strip().lower() for email in stripped.split(',') if email.strip()]


def parse_server_name(raw_string):
    """Parse SERVER_NAME to extract domain and URL scheme.
    
    Args:
        raw_string: Raw SERVER_NAME from environment variable (may include scheme)
    
    Returns:
        Tuple of (server_name, scheme) where:
        - server_name is the domain/host part (or None if empty)
        - scheme is 'http' or 'https' (defaults to 'https' if not specified)
    
    Examples:
        >>> parse_server_name('https://example.com')
        ('example.com', 'https')
        >>> parse_server_name('http://localhost:5000')
        ('localhost:5000', 'http')
        >>> parse_server_name('example.com')
        ('example.com', 'https')
    """
    if not raw_string:
        return None, 'https'
    
    if raw_string.startswith('http://'):
        return raw_string.replace('http://', ''), 'http'
    elif raw_string.startswith('https://'):
        return raw_string.replace('https://', ''), 'https'
    else:
        # No scheme provided, assume https for safety
        return raw_string, 'https'


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

    # Email allowlist (for staging/testing - restricts who can receive emails)
    # Comma-separated list of email addresses. If set, only these addresses receive emails.
    # Leave empty or unset in production to send to all users.
    _email_allowlist_raw = os.environ.get('EMAIL_ALLOWLIST', '').strip()
    EMAIL_ALLOWLIST = parse_email_allowlist(_email_allowlist_raw)

    # URL building configuration for url_for() outside request context (CLI, scheduled jobs)
    # SERVER_NAME should include the scheme (http:// or https://) and domain
    # Examples: https://meutch.com or http://localhost:5000
    _server_name_raw = os.environ.get('SERVER_NAME', '')
    SERVER_NAME, PREFERRED_URL_SCHEME = parse_server_name(_server_name_raw)

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
    SERVER_NAME = 'localhost:5000'
    PREFERRED_URL_SCHEME = 'http'

class StagingConfig(Config):
    """Configuration for staging environment"""
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    LOG_LEVEL = logging.INFO
    # SERVER_NAME and PREFERRED_URL_SCHEME inherited from base Config (parsed from SERVER_NAME env var)


class ProductionConfig(Config):
    """Configuration for production environment"""
    DEBUG = False
    LOG_LEVEL = logging.WARNING
    
    # Production should always use specific environment variables
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    
    # SERVER_NAME and PREFERRED_URL_SCHEME inherited from base Config (parsed from SERVER_NAME env var)
    
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