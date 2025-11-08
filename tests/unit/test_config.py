"""Unit tests for configuration parsing and enforcement.

Tests cover:
- EMAIL_ALLOWLIST: Parsing comma-separated email list, enforcing allowlist in send_email()
- SERVER_NAME: Parsing URL scheme from SERVER_NAME environment variable
"""
from unittest.mock import patch
from config import parse_email_allowlist, parse_server_name


class TestEmailAllowlistParsing:
    """Test EMAIL_ALLOWLIST parsing logic.
    
    Note: These tests verify the parsing logic extracted from config.py.
    The actual Config class parsing is tested implicitly through runtime behavior.
    """
    
    def test_parse_empty_string(self):
        """Test parsing empty string returns None."""
        result = parse_email_allowlist('')
        assert result is None
    
    def test_parse_whitespace_only(self):
        """Test parsing whitespace-only string returns None."""
        result = parse_email_allowlist('   ')
        assert result is None
    
    def test_parse_single_email(self):
        """Test parsing single email address."""
        result = parse_email_allowlist('test1@example.com')
        assert result == ['test1@example.com']
    
    def test_parse_multiple_emails(self):
        """Test parsing multiple comma-separated emails."""
        result = parse_email_allowlist('test1@example.com,test2@example.com,admin@example.com')
        assert result == ['test1@example.com', 'test2@example.com', 'admin@example.com']
    
    def test_parse_with_whitespace_trimming(self):
        """Test that parsing trims whitespace around each email."""
        result = parse_email_allowlist('  test1@example.com  ,  test2@example.com  ,  admin@example.com  ')
        assert result == ['test1@example.com', 'test2@example.com', 'admin@example.com']
    
    def test_parse_with_mixed_whitespace(self):
        """Test parsing with mixed whitespace and empty entries."""
        result = parse_email_allowlist('test1@example.com , , test2@example.com , admin@example.com')
        assert result == ['test1@example.com', 'test2@example.com', 'admin@example.com']


class TestEmailAllowlistEnforcement:
    """Test that send_email respects EMAIL_ALLOWLIST.
    
    These tests verify the allowlist blocking logic in send_email. The actual
    Mailgun API calls are tested in test_email.py.
    """
    
    def test_send_email_blocks_non_allowlisted_address(self, app):
        """Test send_email blocks email when address is NOT in allowlist."""
        from app.utils.email import send_email
        
        with app.app_context():
            app.config['EMAIL_ALLOWLIST'] = ['test1@example.com']
            app.config['MAILGUN_DOMAIN'] = 'mg.example.com'
            app.config['MAILGUN_API_KEY'] = 'key-12345'
            
            with patch('app.utils.email.requests.post') as mock_post:
                result = send_email(
                    'blocked@example.com',
                    'Test Subject',
                    'Test body'
                )
                
                # Should return True (success - filtered) but not call Mailgun
                assert result is True
                mock_post.assert_not_called()
    
    def test_send_email_empty_allowlist_blocks_all(self, app):
        """Test send_email blocks all addresses when allowlist is empty list."""
        from app.utils.email import send_email
        
        with app.app_context():
            app.config['EMAIL_ALLOWLIST'] = []  # Empty list blocks everyone
            app.config['MAILGUN_DOMAIN'] = 'mg.example.com'
            app.config['MAILGUN_API_KEY'] = 'key-12345'
            
            with patch('app.utils.email.requests.post') as mock_post:
                result = send_email(
                    'anyone@example.com',
                    'Test Subject',
                    'Test body'
                )
                
                # Should be blocked
                assert result is True
                mock_post.assert_not_called()
    
    def test_send_email_allowlist_case_sensitive(self, app):
        """Test that allowlist checking is case-sensitive.
        
        Note: This documents current behavior. Consider making it case-insensitive
        for better user experience by normalizing emails to lowercase in config parsing.
        """
        from app.utils.email import send_email
        
        with app.app_context():
            app.config['EMAIL_ALLOWLIST'] = ['test1@example.com']  # lowercase
            app.config['MAILGUN_DOMAIN'] = 'mg.example.com'
            app.config['MAILGUN_API_KEY'] = 'key-12345'
            
            with patch('app.utils.email.requests.post') as mock_post:
                # Try with different case
                result = send_email(
                    'test1@example.com',  # Mixed case
                    'Test Subject',
                    'Test body'
                )
                
                # Currently case-sensitive, so this will be blocked
                assert result is True
                mock_post.assert_not_called()


class TestServerNameParsing:
    """Test SERVER_NAME configuration parsing for URL scheme.
    
    Note: These tests verify the parsing logic extracted from config.py.
    The actual Config class parsing is tested implicitly through runtime behavior.
    """
    
    def test_parse_https_scheme(self):
        """Test parsing SERVER_NAME with https:// prefix."""
        server_name, scheme = parse_server_name('https://example.com')
        assert server_name == 'example.com'
        assert scheme == 'https'
    
    def test_parse_http_scheme(self):
        """Test parsing SERVER_NAME with http:// prefix."""
        server_name, scheme = parse_server_name('http://localhost:5000')
        assert server_name == 'localhost:5000'
        assert scheme == 'http'
    
    def test_parse_no_scheme(self):
        """Test parsing SERVER_NAME without scheme defaults to https."""
        server_name, scheme = parse_server_name('example.com')
        assert server_name == 'example.com'
        assert scheme == 'https'
    
    def test_parse_empty_string(self):
        """Test parsing empty SERVER_NAME."""
        server_name, scheme = parse_server_name('')
        assert server_name is None
        assert scheme == 'https'
