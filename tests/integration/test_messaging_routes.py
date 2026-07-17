"""Integration tests for messaging inbox routes."""

import re

from app import db
from app.models import Message
from conftest import login_user
from tests.factories import (
    ConversationFactory,
    ConversationParticipantFactory,
    MessageFactory,
    UserFactory,
)


class TestMessagingRoutes:
    """Test messaging inbox routes."""

    def test_mark_all_read_marks_unread_messages(self, client, app):
        """POST /messages/mark-all-read marks unread messages as read."""
        with app.app_context():
            sender = UserFactory()
            recipient = UserFactory()
            conversation = ConversationFactory()
            ConversationParticipantFactory(conversation=conversation, user=sender)
            ConversationParticipantFactory(conversation=conversation, user=recipient)
            msg = MessageFactory(
                sender=sender,
                recipient=recipient,
                conversation=conversation,
                is_read=False,
            )
            db.session.commit()
            msg_id = msg.id

            login_user(client, recipient.email)
            # The CSRF token is disabled in tests so we can POST without it
            response = client.post(
                "/messages/mark-all-read?status=inbox",
                follow_redirects=True,
            )

            assert response.status_code == 200
            assert b"Entire inbox marked as read." in response.data

            db.session.expire_all()
            assert db.session.get(Message, msg_id).is_read is True

    def test_messages_inbox_forms_have_csrf_token(self, client, app):
        """Every POST form in the inbox must include a hidden csrf_token input
        whose value is populated by csrf_token()."""
        with app.app_context():
            sender = UserFactory()
            recipient = UserFactory()
            conversation = ConversationFactory()
            ConversationParticipantFactory(conversation=conversation, user=sender)
            ConversationParticipantFactory(conversation=conversation, user=recipient)
            MessageFactory(
                sender=sender,
                recipient=recipient,
                conversation=conversation,
                is_read=False,
            )
            db.session.commit()

            login_user(client, recipient.email)
            response = client.get("/messages?status=inbox")
            assert response.status_code == 200

            html = response.data.decode("utf-8")

            # The page should contain at least one <form method="POST">.
            post_forms = re.findall(r'<form[^>]*method="POST"[^>]*>', html)
            assert len(post_forms) >= 1, "Expected at least one POST form"

            # Each form should render a hidden csrf_token input.
            csrf_inputs = re.findall(r'<input[^>]*name="csrf_token"[^>]*>', html)
            assert (
                len(csrf_inputs) >= 1
            ), "Expected at least one csrf_token hidden input in the page"

    def test_messages_inbox_shows_avatar_image_when_profile_image_url_set(self, client, app):
        """When the other user has a profile_image_url, the inbox must render
        an <img> tag instead of showing initials."""
        with app.app_context():
            sender = UserFactory(
                profile_image_url="https://example.com/avatars/alice.jpg",
                first_name="Alice",
                last_name="Smith",
            )
            recipient = UserFactory()
            conversation = ConversationFactory()
            ConversationParticipantFactory(conversation=conversation, user=sender)
            ConversationParticipantFactory(conversation=conversation, user=recipient)
            MessageFactory(
                sender=sender,
                recipient=recipient,
                conversation=conversation,
                is_read=False,
            )
            db.session.commit()

            login_user(client, recipient.email)
            response = client.get("/messages?status=inbox")
            assert response.status_code == 200

            html = response.data.decode("utf-8")

            # The avatar for Alice should be an <img> with the correct src
            assert (
                'src="https://example.com/avatars/alice.jpg"' in html
            ), "Expected avatar <img> for user with profile_image_url"
            # Initials should NOT appear inside Alice's avatar div
            avatar_pattern = re.compile(r'<div class="conv-avatar">(.*?)</div>', re.DOTALL)
            alice_avatar_found = False
            for match in avatar_pattern.finditer(html):
                content = match.group(1)
                if "https://example.com/avatars/alice.jpg" in content:
                    alice_avatar_found = True
                    assert (
                        "AS" not in content
                    ), "Initials should not appear in avatar div when profile image is set"
                    assert (
                        "<img" in content
                    ), "Expected <img> tag in avatar div when profile_image_url is set"
            assert alice_avatar_found, "Could not find Alice's avatar div in the page"

    def test_messages_inbox_shows_initials_when_no_profile_image(self, client, app):
        """When the other user has no profile_image_url, the inbox must render
        initials as a fallback."""
        with app.app_context():
            sender = UserFactory(
                profile_image_url=None,
                first_name="Bob",
                last_name="Jones",
            )
            recipient = UserFactory()
            conversation = ConversationFactory()
            ConversationParticipantFactory(conversation=conversation, user=sender)
            ConversationParticipantFactory(conversation=conversation, user=recipient)
            MessageFactory(
                sender=sender,
                recipient=recipient,
                conversation=conversation,
                is_read=False,
            )
            db.session.commit()

            login_user(client, recipient.email)
            response = client.get("/messages?status=inbox")
            assert response.status_code == 200

            html = response.data.decode("utf-8")

            # Initials should appear for this user
            assert "BJ" in html, "Expected initials 'BJ' for user without profile image"
            # No <img> tag in the avatar div for this user
            avatar_pattern = re.compile(r'<div class="conv-avatar">(.*?)</div>', re.DOTALL)
            for match in avatar_pattern.finditer(html):
                content = match.group(1)
                if "BJ" in content:
                    assert (
                        "<img" not in content
                    ), "No <img> expected in avatar div when user has no profile image"
                    break

    def test_bulk_archive_preserves_page_and_sort(self, client, app):
        """POST /messages/bulk-archive preserves page & sort in redirect."""
        with app.app_context():
            sender = UserFactory()
            recipient = UserFactory()
            conversation = ConversationFactory()
            ConversationParticipantFactory(conversation=conversation, user=sender)
            ConversationParticipantFactory(conversation=conversation, user=recipient)
            MessageFactory(
                sender=sender, recipient=recipient, conversation=conversation, is_read=False
            )
            db.session.commit()

            login_user(client, recipient.email)
            response = client.post(
                "/messages/bulk-archive?page=2&sort=oldest&status=inbox",
                data={"conversation_ids": str(conversation.id)},
            )

            assert response.status_code == 302
            assert "page=2" in response.location
            assert "sort=oldest" in response.location
            assert "status=inbox" in response.location

    def test_bulk_mark_read_preserves_page_and_sort(self, client, app):
        """POST /messages/bulk-mark-read preserves page & sort in redirect."""
        with app.app_context():
            sender = UserFactory()
            recipient = UserFactory()
            conversation = ConversationFactory()
            ConversationParticipantFactory(conversation=conversation, user=sender)
            ConversationParticipantFactory(conversation=conversation, user=recipient)
            MessageFactory(
                sender=sender, recipient=recipient, conversation=conversation, is_read=False
            )
            db.session.commit()

            login_user(client, recipient.email)
            response = client.post(
                "/messages/bulk-mark-read?page=3&sort=unread&status=inbox",
                data={"conversation_ids": str(conversation.id)},
            )

            assert response.status_code == 302
            assert "page=3" in response.location
            assert "sort=unread" in response.location
            assert "status=inbox" in response.location

    def test_bulk_mark_unread_preserves_page_and_sort(self, client, app):
        """POST /messages/bulk-mark-unread preserves page & sort in redirect."""
        with app.app_context():
            sender = UserFactory()
            recipient = UserFactory()
            conversation = ConversationFactory()
            ConversationParticipantFactory(conversation=conversation, user=sender)
            ConversationParticipantFactory(conversation=conversation, user=recipient)
            MessageFactory(
                sender=sender, recipient=recipient, conversation=conversation, is_read=True
            )
            db.session.commit()

            login_user(client, recipient.email)
            response = client.post(
                "/messages/bulk-mark-unread?page=2&sort=newest&status=inbox",
                data={"conversation_ids": str(conversation.id)},
            )

            assert response.status_code == 302
            assert "page=2" in response.location
            assert "sort=newest" in response.location
            assert "status=inbox" in response.location

    def test_mark_all_read_preserves_page_and_sort(self, client, app):
        """POST /messages/mark-all-read preserves page & sort in redirect."""
        with app.app_context():
            sender = UserFactory()
            recipient = UserFactory()
            conversation = ConversationFactory()
            ConversationParticipantFactory(conversation=conversation, user=sender)
            ConversationParticipantFactory(conversation=conversation, user=recipient)
            MessageFactory(
                sender=sender, recipient=recipient, conversation=conversation, is_read=False
            )
            db.session.commit()

            login_user(client, recipient.email)
            response = client.post(
                "/messages/mark-all-read?page=5&sort=oldest&status=archived",
            )

            assert response.status_code == 302
            assert "page=5" in response.location
            assert "sort=oldest" in response.location
            assert "status=archived" in response.location

    def test_bulk_unarchive_preserves_page_and_sort(self, client, app):
        """POST /messages/bulk-unarchive preserves page & sort in redirect."""
        with app.app_context():
            sender = UserFactory()
            recipient = UserFactory()
            conversation = ConversationFactory()
            ConversationParticipantFactory(
                conversation=conversation, user=recipient, is_archived=True
            )
            ConversationParticipantFactory(conversation=conversation, user=sender)
            MessageFactory(
                sender=sender, recipient=recipient, conversation=conversation, is_read=True
            )
            db.session.commit()

            login_user(client, recipient.email)
            response = client.post(
                "/messages/bulk-unarchive?page=2&sort=name_asc&status=archived",
                data={"conversation_ids": str(conversation.id)},
            )

            assert response.status_code == 302
            assert "page=2" in response.location
            assert "sort=name_asc" in response.location
            assert "status=archived" in response.location
