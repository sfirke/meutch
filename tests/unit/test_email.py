"""Unit tests for email utilities."""
import pytest
from unittest.mock import patch, Mock
from app.utils.email import send_account_deletion_email


class TestEmailUtils:
    """Test email utility functions."""
    
    def test_send_account_deletion_email_content(self):
        """Test that account deletion email contains correct content."""
        with patch('app.utils.email.send_email') as mock_send_email:
            mock_send_email.return_value = True
            
            # Call the function
            result = send_account_deletion_email("test@example.com", "John")
            
            # Verify send_email was called
            assert mock_send_email.called
            call_args = mock_send_email.call_args[0]
            
            # Check email parameters
            email_address = call_args[0]
            subject = call_args[1]
            content = call_args[2]
            
            assert email_address == "test@example.com"
            assert "Account Successfully Deleted" in subject
            assert "Hello John" in content
            assert "successfully deleted" in content
            assert "Your name will continue to appear in message history" in content
            assert "Thank you for being part of the Meutch community" in content
            assert result is True
    
    def test_send_account_deletion_email_failure(self):
        """Test that account deletion email handles send failure gracefully."""
        with patch('app.utils.email.send_email') as mock_send_email:
            mock_send_email.return_value = False
            
            # Call the function
            result = send_account_deletion_email("test@example.com", "John")
            
            # Should return False when send_email fails
            assert result is False
    
    def test_send_account_deletion_email_exception(self):
        """Test that account deletion email handles exceptions."""
        with patch('app.utils.email.send_email') as mock_send_email:
            mock_send_email.side_effect = Exception("Network error")
            
            # Should raise the exception (not caught in this function)
            with pytest.raises(Exception, match="Network error"):
                send_account_deletion_email("test@example.com", "John")
