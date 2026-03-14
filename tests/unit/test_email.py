"""Unit tests for email utilities."""
import pytest
import uuid
from unittest.mock import patch, Mock
from app.utils.email import send_account_deletion_email, build_digest_email_content, send_digest_email
from tests.factories import UserFactory


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

    def test_build_digest_email_content_includes_sections_and_manage_links(self, app):
        with app.app_context():
            user = UserFactory(first_name='Digest')
            payload = {
                'summary_stats': {
                    'total_new_items': 2,
                    'giveaways_count': 1,
                    'borrow_requests_count': 1,
                },
                'giveaways': [
                    {
                        'event_type': 'giveaway',
                        'item_id': uuid.uuid4(),
                        'actor_name': 'Alex',
                        'title': 'Free Chair',
                        'action': 'posted a giveaway',
                    }
                ],
                'requests': [
                    {
                        'event_type': 'request',
                        'request_id': uuid.uuid4(),
                        'actor_name': 'Taylor',
                        'title': 'Need a ladder',
                        'action': 'requested',
                    }
                ],
                'circle_joins': [],
                'loans': [],
            }

            content = build_digest_email_content(
                user,
                payload,
                manage_url='https://example.com/digest/manage/token123',
                unsubscribe_url='https://example.com/digest/unsubscribe/token123',
            )

            assert 'Meutch Digest' in content['subject']
            assert 'Giveaways' in content['text']
            assert 'Requests' in content['text']
            assert 'https://example.com/digest/manage/token123' in content['text']
            assert 'https://example.com/digest/unsubscribe/token123' in content['text']
            assert 'One-click unsubscribe' in content['html']

    def test_send_digest_email_calls_send_email_with_rendered_content(self, app):
        with app.app_context():
            user = UserFactory(first_name='Digest')
            payload = {
                'summary_stats': {
                    'total_new_items': 0,
                    'giveaways_count': 0,
                    'borrow_requests_count': 0,
                },
                'giveaways': [],
                'requests': [],
                'circle_joins': [],
                'loans': [],
            }

            with patch('app.utils.email.send_email') as mock_send_email:
                mock_send_email.return_value = True
                result = send_digest_email(user, payload)

                assert result is True
                mock_send_email.assert_called_once()
                args = mock_send_email.call_args[0]
                assert args[0] == user.email
                assert 'Meutch Digest' in args[1]
                assert '/digest/manage/' in args[2]
                assert '/digest/unsubscribe/' in args[2]
