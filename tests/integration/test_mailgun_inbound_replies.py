import hashlib
import hmac

from app import db
from app.models import Message
from tests.factories import ItemFactory, MessageFactory, UserFactory

SIGNING_KEY = "test-signing-key"


def mailgun_payload(message_id, *, sender, body="Sure, that works.", signature=None):
    timestamp = "1760000000"
    token = "test-token"
    if signature is None:
        signature = hmac.new(
            SIGNING_KEY.encode("utf-8"),
            f"{timestamp}{token}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    return {
        "timestamp": timestamp,
        "token": token,
        "signature": signature,
        "sender": sender,
        "recipient": f"Meutch Replies <reply+{message_id}@reply.example.com>",
        "stripped-text": body,
        "body-plain": f"{body}\n\nOn yesterday, someone wrote:",
    }


class TestMailgunInboundReplies:
    def test_mailgun_reply_creates_message_reply(self, client, app):
        with app.app_context():
            app.config["MAILGUN_WEBHOOK_SIGNING_KEY"] = SIGNING_KEY
            sender = UserFactory(email="sender@example.com")
            recipient = UserFactory(email="recipient@example.com")
            item = ItemFactory(owner=recipient)
            original = MessageFactory(
                sender=sender,
                recipient=recipient,
                item=item,
                body="Can I borrow this?",
            )
            db.session.commit()
            original_id = original.id
            sender_id = sender.id
            recipient_id = recipient.id
            item_id = item.id

        response = client.post(
            "/webhooks/mailgun/messages",
            data=mailgun_payload(original_id, sender="recipient@example.com", body="Yes."),
        )

        assert response.status_code == 200

        with app.app_context():
            reply = Message.query.filter_by(parent_id=original_id).one()
            assert reply.sender_id == recipient_id
            assert reply.recipient_id == sender_id
            assert reply.item_id == item_id
            assert reply.body == "Yes."

    def test_mailgun_reply_rejects_bad_signature(self, client, app):
        with app.app_context():
            app.config["MAILGUN_WEBHOOK_SIGNING_KEY"] = SIGNING_KEY
            original = MessageFactory()
            db.session.commit()
            original_id = original.id
            recipient_email = original.recipient.email

        response = client.post(
            "/webhooks/mailgun/messages",
            data=mailgun_payload(
                original_id,
                sender=recipient_email,
                signature="bad-signature",
            ),
        )

        assert response.status_code == 406

        with app.app_context():
            assert Message.query.filter_by(parent_id=original_id).count() == 0

    def test_mailgun_reply_rejects_non_participant_sender(self, client, app):
        with app.app_context():
            app.config["MAILGUN_WEBHOOK_SIGNING_KEY"] = SIGNING_KEY
            original = MessageFactory()
            outsider = UserFactory(email="outsider@example.com")
            db.session.commit()
            original_id = original.id
            outsider_email = outsider.email

        response = client.post(
            "/webhooks/mailgun/messages",
            data=mailgun_payload(original_id, sender=outsider_email),
        )

        assert response.status_code == 406

        with app.app_context():
            assert Message.query.filter_by(parent_id=original_id).count() == 0

    def test_mailgun_reply_rejects_empty_body(self, client, app):
        with app.app_context():
            app.config["MAILGUN_WEBHOOK_SIGNING_KEY"] = SIGNING_KEY
            original = MessageFactory()
            db.session.commit()
            original_id = original.id
            recipient_email = original.recipient.email

        payload = mailgun_payload(original_id, sender=recipient_email, body="")
        payload["body-plain"] = "   "

        response = client.post("/webhooks/mailgun/messages", data=payload)

        assert response.status_code == 406

        with app.app_context():
            assert Message.query.filter_by(parent_id=original_id).count() == 0
