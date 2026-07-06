"""Test factories for creating test data."""

import uuid
from datetime import UTC, datetime, timedelta

import factory
from factory.alchemy import SQLAlchemyModelFactory
from faker import Faker
from werkzeug.security import generate_password_hash

from app import db
from app.models import (
    AdminAction,
    Category,
    Circle,
    CircleJoinRequest,
    Conversation,
    ConversationParticipant,
    GiveawayInterest,
    Item,
    ItemImage,
    ItemRequest,
    LoanRequest,
    Message,
    Tag,
    User,
    UserWebLink,
)
from app.utils.messaging_queries import _find_conversation

fake = Faker()


def _find_or_build_conversation(context_type, context_id, user1_id, user2_id):
    """Test-only helper: find or build a conversation WITHOUT committing.

    Used by MessageFactory so that conversations can be resolved inside
    ``_create`` (which runs with ``sqlalchemy_session_persistence = "flush"``)
    without prematurely committing the message under construction.

    Returns (conversation, is_new).
    """
    u1, u2 = sorted([user1_id, user2_id])
    existing = _find_conversation(context_type, context_id, u1, u2)
    if existing:
        return existing, False

    conv = Conversation(context_type=context_type, context_id=context_id)
    db.session.add(conv)
    db.session.flush()  # get the ID
    for uid in {u1, u2}:
        db.session.add(ConversationParticipant(conversation_id=conv.id, user_id=uid))
    db.session.flush()  # ensure participants are visible to later queries
    return conv, True


# Pre-compute password hash once to avoid slow bcrypt on every user creation
# This matches TEST_PASSWORD in conftest.py
TEST_PASSWORD_HASH = generate_password_hash("testpassword123")


class CategoryFactory(SQLAlchemyModelFactory):
    """Factory for Category model."""

    class Meta:
        model = Category
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = "flush"

    name = factory.Sequence(lambda n: f"Category {n} {uuid.uuid4().hex[:8]}")


class UserFactory(SQLAlchemyModelFactory):
    """Factory for User model."""

    class Meta:
        model = User
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = "flush"

    email = factory.LazyAttribute(lambda obj: f"{uuid.uuid4().hex[:8]}@example.com")
    first_name = factory.LazyAttribute(lambda obj: fake.first_name())
    last_name = factory.LazyAttribute(lambda obj: fake.last_name())
    email_confirmed = True
    is_admin = False
    is_public_showcase = False
    # Use pre-computed hash instead of hashing on every factory call
    password_hash = TEST_PASSWORD_HASH


class TagFactory(SQLAlchemyModelFactory):
    """Factory for Tag model."""

    class Meta:
        model = Tag
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = "flush"

    name = factory.Sequence(lambda n: f"tag-{n}-{uuid.uuid4().hex[:8]}")


class ItemFactory(SQLAlchemyModelFactory):
    """Factory for Item model."""

    class Meta:
        model = Item
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = "flush"

    name = factory.LazyAttribute(lambda obj: f"{fake.catch_phrase()} {uuid.uuid4().hex[:8]}")
    description = factory.LazyAttribute(lambda obj: fake.text(max_nb_chars=200))
    owner = factory.SubFactory(UserFactory)
    category = factory.SubFactory(CategoryFactory)
    available = True


class ItemImageFactory(SQLAlchemyModelFactory):
    """Factory for ItemImage model."""

    class Meta:
        model = ItemImage
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = "flush"

    item = factory.SubFactory(ItemFactory)
    url = factory.LazyAttribute(lambda obj: f"https://example.com/items/{uuid.uuid4()}.jpg")
    position = factory.Sequence(lambda n: n)


class CircleFactory(SQLAlchemyModelFactory):
    """Factory for Circle model."""

    class Meta:
        model = Circle
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = "flush"

    name = factory.LazyAttribute(lambda obj: f"{fake.company()} {uuid.uuid4().hex[:8]}")
    description = factory.LazyAttribute(lambda obj: fake.text(max_nb_chars=200))
    circle_type = "open"
    is_regional = False
    regional_radius_miles = None


class LoanRequestFactory(SQLAlchemyModelFactory):
    """Factory for LoanRequest model."""

    class Meta:
        model = LoanRequest
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = "flush"

    item = factory.SubFactory(ItemFactory)
    borrower = factory.SubFactory(UserFactory)
    start_date = factory.LazyAttribute(lambda obj: fake.date_this_month())
    end_date = factory.LazyAttribute(lambda obj: fake.date_this_year())
    status = "pending"


class ConversationFactory(SQLAlchemyModelFactory):
    """Factory for Conversation model.

    Requires ``context_type`` and ``context_id`` to be passed explicitly,
    or accepts an ``item`` parameter that derives them automatically.
    """

    class Meta:
        model = Conversation
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = "flush"
        exclude = ("item", "request", "circle")

    context_type = "item"

    # Transient helpers — not model fields
    item = None
    request = None
    circle = None

    @factory.lazy_attribute
    def context_id(self):
        """Derive context_id from the transient item/request/circle param."""
        if self.item is not None:
            return self.item.id
        if self.request is not None:
            return self.request.id
        if self.circle is not None:
            return self.circle.id
        # Fall back to auto-creating a default item
        default_item = ItemFactory()
        return default_item.id


class ConversationParticipantFactory(SQLAlchemyModelFactory):
    """Factory for ConversationParticipant model."""

    class Meta:
        model = ConversationParticipant
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = "flush"

    conversation = factory.SubFactory(ConversationFactory)
    user = factory.SubFactory(UserFactory)
    is_archived = False


class MessageFactory(SQLAlchemyModelFactory):
    """Factory for Message model.

    Supports legacy ``item``, ``request``, and ``circle`` keyword arguments
    by resolving the appropriate Conversation via ``_find_or_build_conversation``
    so that multiple messages with the same context are grouped correctly.

    For new code, pass ``conversation=`` directly.
    """

    class Meta:
        model = Message
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = "flush"

    sender = factory.SubFactory(UserFactory)
    recipient = factory.SubFactory(UserFactory)
    body = factory.LazyAttribute(lambda obj: fake.text(max_nb_chars=500))
    is_read = False
    # conversation handled in _create, NOT a SubFactory here

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        """Resolve conversation before creating the Message instance."""
        # Pop legacy context kwargs before they reach the model constructor
        item = kwargs.pop("item", None)
        request = kwargs.pop("request", None)
        circle = kwargs.pop("circle", None)

        # If conversation was explicitly provided, keep it
        if "conversation" in kwargs:
            return super()._create(model_class, *args, **kwargs)

        context_type = None
        context_id = None
        if item is not None:
            context_type = "item"
            context_id = item.id
        elif request is not None:
            context_type = "request"
            context_id = request.id
        elif circle is not None:
            context_type = "circle"
            context_id = circle.id

        if context_type is not None:
            sender = kwargs.get("sender")
            recipient = kwargs.get("recipient")
            sender_id = sender.id if hasattr(sender, "id") else sender
            recipient_id = recipient.id if hasattr(recipient, "id") else recipient
            real_conv, _is_new = _find_or_build_conversation(
                context_type, context_id, sender_id, recipient_id
            )
            kwargs["conversation"] = real_conv
        else:
            kwargs["conversation"] = ConversationFactory()

        return super()._create(model_class, *args, **kwargs)

    @factory.post_generation
    def ensure_participants(self, create, extracted, **kwargs):
        """Ensure both sender and recipient are participants in the conversation."""
        if not create:
            return
        seen = set()
        for user in [self.sender, self.recipient]:
            if user.id in seen:
                continue
            seen.add(user.id)
            existing = ConversationParticipant.query.filter_by(
                conversation_id=self.conversation_id, user_id=user.id
            ).first()
            if not existing:
                try:
                    participant = ConversationParticipant(
                        conversation_id=self.conversation_id, user_id=user.id
                    )
                    db.session.add(participant)
                except Exception:
                    db.session.rollback()
                    # Participant already exists — that's fine


class CircleJoinRequestFactory(SQLAlchemyModelFactory):
    """Factory for CircleJoinRequest model."""

    class Meta:
        model = CircleJoinRequest
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = "flush"

    circle = factory.SubFactory(CircleFactory)
    user = factory.SubFactory(UserFactory)
    message = factory.LazyAttribute(lambda obj: fake.text(max_nb_chars=200))
    status = "pending"


class UserWebLinkFactory(SQLAlchemyModelFactory):
    """Factory for UserWebLink model."""

    class Meta:
        model = UserWebLink
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = "flush"

    user = factory.SubFactory(UserFactory)
    platform_type = factory.Iterator(
        ["facebook", "instagram", "linkedin", "x", "mastodon", "bluesky"]
    )
    url = factory.LazyAttribute(lambda obj: f"https://{obj.platform_type}.com/testuser")
    display_order = factory.Sequence(lambda n: (n % 5) + 1)  # 1-5


class AdminActionFactory(SQLAlchemyModelFactory):
    """Factory for AdminAction model."""

    class Meta:
        model = AdminAction
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = "flush"

    action_type = factory.Iterator(["promote", "demote", "delete"])
    target_user = factory.SubFactory(UserFactory)
    admin_user = factory.SubFactory(UserFactory, is_admin=True)
    details = factory.LazyAttribute(
        lambda obj: {
            "target_email": obj.target_user.email,
            "target_name": obj.target_user.full_name,
        }
    )


class GiveawayInterestFactory(SQLAlchemyModelFactory):
    """Factory for GiveawayInterest model."""

    class Meta:
        model = GiveawayInterest
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = "flush"

    item = factory.SubFactory(
        ItemFactory, is_giveaway=True, giveaway_visibility="default", claim_status="unclaimed"
    )
    user = factory.SubFactory(UserFactory)
    message = factory.LazyAttribute(lambda obj: fake.text(max_nb_chars=200))
    status = "active"


class ItemRequestFactory(SQLAlchemyModelFactory):
    """Factory for ItemRequest model."""

    class Meta:
        model = ItemRequest
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = "flush"

    user = factory.SubFactory(UserFactory)
    title = factory.LazyAttribute(lambda obj: f"{fake.catch_phrase()} {uuid.uuid4().hex[:6]}")
    description = factory.LazyAttribute(lambda obj: fake.text(max_nb_chars=200))
    expires_at = factory.LazyAttribute(lambda obj: datetime.now(UTC) + timedelta(days=30))
    seeking = "either"
    visibility = "public"
    status = "open"
