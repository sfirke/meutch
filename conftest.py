# Test configuration
import os
import tempfile
import pytest
from app import create_app, db
from app.models import User, Item, Category, Circle, Tag
from config import Config

class TestConfig(Config):
    """Test configuration class."""
    TESTING = True
    WTF_CSRF_ENABLED = False
    # Use Docker PostgreSQL database for testing (port 5433 to avoid conflicts)
    SQLALCHEMY_DATABASE_URI = os.environ.get('TEST_DATABASE_URL') or 'postgresql://test_user:test_password@localhost:5433/test_meutch'
    SECRET_KEY = 'test-secret-key'
    
    # Disable file uploads for testing
    DO_SPACES_ENDPOINT = None
    DO_SPACES_BUCKET = None
    DO_SPACES_KEY = None
    DO_SPACES_SECRET = None
    
    # Email testing
    MAIL_SUPPRESS_SEND = True
    
    # Logging
    LOG_LEVEL = 'ERROR'

@pytest.fixture
def app():
    """Create application for testing."""
    app = create_app(TestConfig)
    
    with app.app_context():
        db.create_all()
        
        # Create test categories
        categories = ['Tools', 'Electronics', 'Books', 'Sports Equipment']
        for cat_name in categories:
            category = Category(name=cat_name)
            db.session.add(category)
        
        db.session.commit()
        
        yield app
        
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()

@pytest.fixture
def runner(app):
    """Create test CLI runner."""
    return app.test_cli_runner()

@pytest.fixture
def auth_user(app):
    """Create a test user and return user ID for session-safe access."""
    with app.app_context():
        user = User(
            email='test@example.com',
            first_name='Test',
            last_name='User',
            street='123 Test St',
            city='Test City',
            state='TS',
            zip_code='12345',
            country='USA',
            email_confirmed=True
        )
        user.set_password('testpassword')
        db.session.add(user)
        db.session.commit()
        user_id = user.id
        
    # Return a function that retrieves the user with fresh session
    def get_user():
        return User.query.get(user_id)
    
    return get_user

@pytest.fixture
def admin_user(app):
    """Create a test admin user and return user ID for session-safe access."""
    with app.app_context():
        user = User(
            email='admin@example.com',
            first_name='Admin',
            last_name='User',
            street='456 Admin Ave',
            city='Admin City',
            state='AD',
            zip_code='54321',
            country='USA',
            email_confirmed=True,
            is_admin=True
        )
        user.set_password('adminpassword')
        db.session.add(user)
        db.session.commit()
        user_id = user.id
        
    # Return a function that retrieves the user with fresh session
    def get_user():
        return User.query.get(user_id)
    
    return get_user

def login_user(client, email='test@example.com', password='testpassword'):
    """Helper function to log in a user."""
    return client.post('/auth/login', data={
        'email': email,
        'password': password
    }, follow_redirects=True)

def logout_user(client):
    """Helper function to log out a user."""
    return client.get('/auth/logout', follow_redirects=True)
