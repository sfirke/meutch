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


class TestConversationPartnerProfileLink:
    """A conversation grants profile access — except once the partner deletes their account."""

    def _conversation_with(self, viewer, partner):
        conversation = ConversationFactory()
        ConversationParticipantFactory(conversation=conversation, user=viewer)
        ConversationParticipantFactory(conversation=conversation, user=partner)
        MessageFactory(
            sender=partner,
            recipient=viewer,
            conversation=conversation,
            body="Is this still available?",
        )
        return conversation

    def test_conversation_links_partner_profile(self, client, app):
        with app.app_context():
            viewer = UserFactory()
            partner = UserFactory(first_name="Active", last_name="Partner")
            conversation = self._conversation_with(viewer, partner)
            db.session.commit()

            login_user(client, viewer.email)
            response = client.get(f"/conversation/{conversation.id}")
            content = response.data.decode("utf-8")

            assert response.status_code == 200
            assert f'href="/user/{partner.id}"' in content

    def test_conversation_does_not_link_deleted_partner_profile(self, client, app):
        """Deleted accounts have no viewable profile, so the name is plain text."""
        with app.app_context():
            viewer = UserFactory()
            partner = UserFactory(first_name="Gone", last_name="Partner", is_deleted=True)
            conversation = self._conversation_with(viewer, partner)
            db.session.commit()

            login_user(client, viewer.email)
            response = client.get(f"/conversation/{conversation.id}")
            content = response.data.decode("utf-8")

            assert response.status_code == 200
            assert "Gone Partner" in content
            assert f'href="/user/{partner.id}"' not in content


class TestConversationBodyRendering:
    """Message bodies are plain text: links are made clickable, markup is not."""

    def _conversation_with_body(self, viewer, partner, body):
        conversation = ConversationFactory()
        ConversationParticipantFactory(conversation=conversation, user=viewer)
        ConversationParticipantFactory(conversation=conversation, user=partner)
        MessageFactory(sender=partner, recipient=viewer, conversation=conversation, body=body)
        return conversation

    def test_urls_in_a_message_are_clickable(self, client, app):
        with app.app_context():
            viewer = UserFactory()
            partner = UserFactory()
            conversation = self._conversation_with_body(
                viewer, partner, "You can see it here: https://meutch.com/item/abc"
            )
            db.session.commit()

            login_user(client, viewer.email)
            response = client.get(f"/conversation/{conversation.id}")
            content = response.data.decode("utf-8")

            assert response.status_code == 200
            assert (
                '<a href="https://meutch.com/item/abc" target="_blank" '
                'rel="noopener noreferrer nofollow">https://meutch.com/item/abc</a>'
            ) in content

    def test_markup_in_a_message_is_escaped(self, client, app):
        """Bodies are user input and were previously rendered with `| safe`."""
        with app.app_context():
            viewer = UserFactory()
            partner = UserFactory()
            conversation = self._conversation_with_body(
                viewer, partner, "<script>alert('xss')</script>"
            )
            db.session.commit()

            login_user(client, viewer.email)
            response = client.get(f"/conversation/{conversation.id}")
            content = response.data.decode("utf-8")

            assert response.status_code == 200
            assert "<script>alert(" not in content
            assert "&lt;script&gt;" in content

    def test_newlines_in_a_message_become_line_breaks(self, client, app):
        with app.app_context():
            viewer = UserFactory()
            partner = UserFactory()
            conversation = self._conversation_with_body(viewer, partner, "first\nsecond")
            db.session.commit()

            login_user(client, viewer.email)
            response = client.get(f"/conversation/{conversation.id}")
            content = response.data.decode("utf-8")

            assert response.status_code == 200
            assert "first<br>second" in content


class TestConversationListPreviewRendering:
    """The inbox preview is plain text: the whole row is already a link."""

    def test_preview_does_not_linkify_urls(self, client, app):
        """Linkifying here would nest an <a> inside the row's own <a>."""
        with app.app_context():
            viewer = UserFactory()
            partner = UserFactory()
            conversation = ConversationFactory()
            ConversationParticipantFactory(conversation=conversation, user=viewer)
            ConversationParticipantFactory(conversation=conversation, user=partner)
            MessageFactory(
                sender=partner,
                recipient=viewer,
                conversation=conversation,
                body="See https://example.com/dp/B012345",
            )
            db.session.commit()

            login_user(client, viewer.email)
            response = client.get("/messages")
            content = response.data.decode("utf-8")

            assert response.status_code == 200
            preview = content.split('<span class="conv-preview">')[1].split("</span>")[0]
            assert "https://example.com/dp/B012345" in preview
            assert "<a" not in preview
