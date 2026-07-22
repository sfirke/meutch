"""Mailgun inbound webhook handlers."""

import hashlib
import hmac
import re
from email.utils import parseaddr
from uuid import UUID

from flask import current_app, request

from app import db
from app.models import Message
from app.services import message_service
from app.services.exceptions import AuthorizationError, InvalidActionError
from app.webhooks import bp

REPLY_RECIPIENT_RE = re.compile(r"^reply\+(?:[a-z]+-)?([0-9a-fA-F-]{36})$")


def verify_mailgun_signature(timestamp, token, signature):
    signing_key = current_app.config.get("MAILGUN_WEBHOOK_SIGNING_KEY")
    if not signing_key or not timestamp or not token or not signature:
        return False

    digest = hmac.new(
        signing_key.encode("utf-8"),
        f"{timestamp}{token}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(digest, signature)


def parse_reply_message_id(recipient):
    _, address = parseaddr(recipient or "")
    local_part = address.split("@", 1)[0].lower()
    match = REPLY_RECIPIENT_RE.fullmatch(local_part)
    if not match:
        return None

    try:
        return UUID(match.group(1))
    except ValueError:
        return None


def normalize_email(value):
    _, address = parseaddr(value or "")
    return address.strip().lower()


def extract_reply_body(form):
    for field_name in ("stripped-text", "body-plain"):
        value = form.get(field_name)
        if value and value.strip():
            return value.strip()
    return None


def find_replying_user(message, sender_email):
    if message.sender.email.lower() == sender_email:
        return message.sender
    if message.recipient.email.lower() == sender_email:
        return message.recipient
    return None


@bp.post("/mailgun/messages")
def receive_mailgun_message_reply():
    form = request.form
    current_app.logger.info("Mailgun webhook received")

    if not verify_mailgun_signature(
        form.get("timestamp"),
        form.get("token"),
        form.get("signature"),
    ):
        current_app.logger.warning("Mailgun reply rejected: invalid signature")
        return "invalid signature", 406

    message_id = parse_reply_message_id(form.get("recipient"))
    if message_id is None:
        current_app.logger.warning(
            "Mailgun reply rejected: could not parse message id from recipient %r",
            form.get("recipient"),
        )
        return "invalid recipient", 406

    original_message = db.session.get(Message, message_id)
    if original_message is None:
        current_app.logger.warning("Mailgun reply rejected: message %s not found", message_id)
        return "unknown message", 406

    sender_email = normalize_email(form.get("sender"))
    replying_user = find_replying_user(original_message, sender_email)
    if replying_user is None:
        current_app.logger.warning(
            "Mailgun reply rejected: sender %r is not in conversation for message %s",
            sender_email,
            message_id,
        )
        return "sender is not in this conversation", 406

    body = extract_reply_body(form)
    if body is None:
        current_app.logger.warning("Mailgun reply rejected: empty body for message %s", message_id)
        return "empty reply", 406

    try:
        message_service.reply_to_message(original_message, replying_user.id, body)
        current_app.logger.info(
            "Mailgun reply created: message %s from user %s", message_id, replying_user.id
        )
    except (AuthorizationError, InvalidActionError) as exc:
        current_app.logger.info("Mailgun reply rejected: %s", exc)
        return "invalid reply", 406
    except Exception:
        current_app.logger.exception("Mailgun reply failed")
        return "reply failed", 500

    return "", 200
