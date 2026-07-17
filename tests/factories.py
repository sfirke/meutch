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

fake = Faker()

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

    Pass ``context_type`` and ``context_id`` explicitly to target a specific
    entity.  When called with no arguments a default item-backed conversation
    is created automatically.
    """

    class Meta:
        model = Conversation
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = "flush"

    context_type = "item"

    @factory.lazy_attribute
    def context_id(self):
        return ItemFactory().id


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

    Pass ``conversation=`` to target a specific conversation.  When called
    with only ``sender`` and ``recipient`` a default item-backed
    conversation is created automatically.
    """

    class Meta:
        model = Message
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = "flush"

    sender = factory.SubFactory(UserFactory)
    recipient = factory.SubFactory(UserFactory)
    body = factory.LazyAttribute(lambda obj: fake.text(max_nb_chars=500))
    is_read = False

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        if "conversation" not in kwargs:
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
                participant = ConversationParticipant(
                    conversation_id=self.conversation_id, user_id=user.id
                )
                db.session.add(participant)


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
