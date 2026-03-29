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
            user = UserFactory(first_name='Digest', digest_frequency='daily')
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
                        'description': 'Great chair in good condition',
                        'image_url': 'https://example.com/chair.jpg',
                        'action': 'posted a giveaway',
                    }
                ],
                'requests': [
                    {
                        'event_type': 'request',
                        'request_id': uuid.uuid4(),
                        'actor_name': 'Taylor',
                        'title': 'Need a ladder',
                        'description': 'Need for one weekend project',
                        'image_url': 'https://example.com/ladder.jpg',
                        'action': 'requested',
                    }
                ],
                'circle_joins': [],
                'loans': [
                    {
                        'event_type': 'lent',
                        'item_id': uuid.uuid4(),
                        'actor_name': 'Morgan',
                        'title': 'Power Drill',
                        'image_url': 'https://example.com/drill.jpg',
                        'action': 'lent out',
                    }
                ],
            }

            content = build_digest_email_content(
                user,
                payload,
                manage_url='https://example.com/digest/manage/token123',
                unsubscribe_url='https://example.com/digest/unsubscribe/token123',
            )

            assert content['subject'] == 'Meutch Digest - 3 new activities'
            assert 'This is your daily Meutch digest.' in content['text']
            assert 'Great chair in good condition' in content['text']
            assert 'Need for one weekend project' in content['text']
            assert 'https://example.com/chair.jpg' in content['text']
            assert 'https://example.com/ladder.jpg' in content['text']
            assert 'https://example.com/drill.jpg' in content['text']
            assert 'Giveaways' in content['text']
            assert 'Requests' in content['text']
            assert 'https://example.com/digest/manage/token123' in content['text']
            assert 'https://example.com/digest/unsubscribe/token123' in content['text']
            assert 'One-click unsubscribe' in content['html']
            assert '0 circle joins' not in content['text']
            assert '3 new activities' not in content['text']

    def test_send_digest_email_returns_false_when_no_events(self, app):
        """Test that send_digest_email returns False and skips sending when payload has no events."""
        with app.app_context():
            user = UserFactory(first_name='Digest', digest_frequency='weekly')
            payload = {
                'summary_stats': {
                    'total_new_items': 0,
                    'giveaways_count': 0,
                    'borrow_requests_count': 0,
                },
                'events': [],
                'giveaways': [],
                'requests': [],
                'circle_joins': [],
                'loans': [],
            }

            with patch('app.utils.email.send_email') as mock_send_email:
                result = send_digest_email(user, payload)

                # Should return False when no events exist
                assert result is False
                # send_email should never be called
                mock_send_email.assert_not_called()
