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

# Import pre-computed password hash from factories to avoid slow bcrypt calls
from tests.factories import TEST_PASSWORD_HASH

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
    SQLALCHEMY_DATABASE_URI = os.environ.get('TEST_DATABASE_URL') or 'postgresql://test_user:test_password@localhost:5433/meutch_dev'
    SECRET_KEY = 'test-secret-key'
    
    # File storage - always use local for tests
    STORAGE_BACKEND = 'local'
    
    # Disable file uploads for testing
    DO_SPACES_ENDPOINT = None
    DO_SPACES_BUCKET = None
    DO_SPACES_KEY = None
    DO_SPACES_SECRET = None
    
    # Email testing
    MAIL_SUPPRESS_SEND = True
    
    # Logging
    LOG_LEVEL = 'ERROR'


@pytest.fixture(scope='session')
def app():
    """Create application for testing (session-scoped).
    
    Database schema is created once per test session for speed.
    The clean_db fixture handles cleanup between tests.
    """
    app = create_app(TestConfig)
    
    with app.app_context():
        # Drop and recreate tables once per test session
        db.drop_all()
        db.create_all()
        
        # Create test categories
        categories = ['Tools', 'Electronics', 'Books', 'Sports Equipment']
        for cat_name in categories:
            category = Category(name=cat_name)
            db.session.add(category)
        
        db.session.commit()
    
    yield app
    
    # Clean up after all tests
    with app.app_context():
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

@pytest.fixture(autouse=True)
def clean_db(app):
    """Clean database before each test using TRUNCATE for speed.
    
    Uses TRUNCATE CASCADE which is faster than DELETE for clearing tables.
    Preserves categories since they're seeded at session start.
    Runs BEFORE each test to ensure clean state.
    """
    # Cleanup BEFORE test to ensure clean state
    with app.app_context():
        db.session.rollback()  # Roll back any uncommitted transactions
        
        # Use TRUNCATE CASCADE for fast cleanup - order doesn't matter with CASCADE
        # Exclude 'category' table since it's seeded at session start
        # Use actual PostgreSQL table names (not model names)
        tables_to_truncate = [
            'giveaway_interest', 'messages', 'loan_request', 'circle_join_requests',
            'user_web_links', 'admin_action', 'item_tags', 'item', 'tag', 'feedback',
            'item_request', 'circle_members', 'circle', 'users'
        ]
        
        for table in tables_to_truncate:
            try:
                db.session.execute(db.text(f'TRUNCATE TABLE {table} CASCADE'))
            except Exception:
                pass  # Table might not exist or be empty
        
        db.session.commit()
        db.session.remove()
    
    yield
    
    # Also cleanup after test
    with app.app_context():
        db.session.rollback()
        db.session.remove()

@pytest.fixture
def db_session(app):
    """Create a database session with automatic rollback for test isolation."""
    with app.app_context():
        yield db.session

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
            email_confirmed=True,
            password_hash=TEST_PASSWORD_HASH  # Use pre-computed hash instead of set_password()
        )
        db.session.add(user)
        db.session.commit()
        user_id = user.id
        
    # Return a function that retrieves the user with fresh session
    def get_user():
        return db.session.get(User, user_id)
    
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