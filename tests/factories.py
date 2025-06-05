"""Test factories for creating test data."""
import factory
from factory.alchemy import SQLAlchemyModelFactory
from faker import Faker
from werkzeug.security import generate_password_hash
from app import db
from app.models import User, Item, Category, Circle, Tag, LoanRequest, Message
import uuid

fake = Faker()

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
    street = factory.LazyAttribute(lambda obj: fake.street_address())
    city = factory.LazyAttribute(lambda obj: fake.city())
    state = factory.LazyAttribute(lambda obj: fake.state_abbr())
    zip_code = factory.LazyAttribute(lambda obj: fake.zipcode())
    country = "USA"
    email_confirmed = True
    password_hash = factory.LazyFunction(lambda: generate_password_hash('testpassword123'))

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

class CircleFactory(SQLAlchemyModelFactory):
    """Factory for Circle model."""
    class Meta:
        model = Circle
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = "flush"
    
    name = factory.LazyAttribute(lambda obj: f"{fake.company()} {uuid.uuid4().hex[:8]}")
    description = factory.LazyAttribute(lambda obj: fake.text(max_nb_chars=200))
    requires_approval = False

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
    status = 'pending'

class MessageFactory(SQLAlchemyModelFactory):
    """Factory for Message model."""
    class Meta:
        model = Message
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = "flush"
    
    sender = factory.SubFactory(UserFactory)
    recipient = factory.SubFactory(UserFactory)
    item = factory.SubFactory(ItemFactory)
    body = factory.LazyAttribute(lambda obj: fake.text(max_nb_chars=500))
    is_read = False
