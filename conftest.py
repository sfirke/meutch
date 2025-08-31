# Test configuration
import os
import tempfile
import pytest
import subprocess
import time
import socket
from app import create_app, db
from app.models import User, Item, Category, Circle, Tag
from config import Config
from unittest.mock import patch

# Test constants
TEST_PASSWORD = 'testpassword123'  # Must match UserFactory password

def is_port_open(host, port):
    """Check if a port is open."""
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except (socket.error, OSError):
        return False

def ensure_test_database():
    """Ensure the test database is running."""
    # Check if the test database is already running
    if is_port_open('localhost', 5433):
        print("✅ Test database is already running")
        return
    
    print("🚀 Starting test database...")
    try:
        # Start the Docker container using docker-compose
        subprocess.run(
            ['docker', 'compose', '-f', 'docker-compose.test.yml', 'up', '-d'],
            check=True,
            capture_output=True,
            text=True
        )
        
        # Wait for database to be ready
        max_attempts = 30
        for attempt in range(max_attempts):
            if is_port_open('localhost', 5433):
                # Give it an extra second to fully initialize
                time.sleep(1)
                print("✅ Test database is ready!")
                return
            time.sleep(1)
        
        raise Exception("Timeout waiting for test database to start")
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to start test database: {e}")
        print(f"stdout: {e.stdout}")
        print(f"stderr: {e.stderr}")
        raise
    except Exception as e:
        print(f"❌ Error starting test database: {e}")
        raise

# Ensure test database is running before any tests
ensure_test_database()

class TestConfig(Config):
    """Test configuration class."""
    TESTING = True
    WTF_CSRF_ENABLED = False
    # Use separate test database to avoid wiping development data
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
        # Ensure clean state by dropping all tables first
        db.drop_all()
        db.create_all()
        
        # Create test categories - check if they exist first to avoid duplicates
        categories = ['Tools', 'Electronics', 'Books', 'Sports Equipment']
        for cat_name in categories:
            existing_cat = Category.query.filter_by(name=cat_name).first()
            if not existing_cat:
                category = Category(name=cat_name)
                db.session.add(category)
        
        db.session.commit()
        
        yield app
        
        # Clean up after test
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
def db_session(app):
    """Create a database session with automatic rollback for test isolation."""
    with app.app_context():
        # Start a transaction
        connection = db.engine.connect()
        transaction = connection.begin()
        
        # Configure session to use this connection
        db.session.configure(bind=connection)
        
        yield db.session
        
        # Rollback transaction and close connection
        transaction.rollback()
        connection.close()
        db.session.remove()

@pytest.fixture
def auth_user(app):
    """Create a test user and return user ID for session-safe access."""
    import uuid
    unique_id = str(uuid.uuid4())[:8]
    
    with app.app_context():
        user = User(
            email=f'test{unique_id}@example.com',
            first_name='Test',
            last_name='User',
            latitude=40.7128,
            longitude=-74.0060,
            email_confirmed=True
        )
        user.set_password(TEST_PASSWORD)
        db.session.add(user)
        db.session.commit()
        user_id = user.id
        
    # Return a function that retrieves the user with fresh session
    def get_user():
        return User.query.get(user_id)
    
    return get_user

def login_user(client, email='test@example.com', password=None):
    """Helper function to log in a user."""
    if password is None:
        password = TEST_PASSWORD  # Use constant instead of hardcoded string
    
    return client.post('/auth/login', data={
        'email': email,
        'password': password
    }, follow_redirects=True)

def logout_user(client):
    """Helper function to log out a user."""
    return client.get('/auth/logout', follow_redirects=True)

@pytest.fixture(autouse=True)
def mock_email_sending():
    with patch('app.utils.email.send_email', return_value=True), \
         patch('app.utils.email.send_confirmation_email', return_value=True), \
         patch('app.utils.email.send_password_reset_email', return_value=True):
        yield
