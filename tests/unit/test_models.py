"""Unit tests for models."""
import pytest
from datetime import datetime, UTC
from app.models import User, Item, Circle, Tag, Category
from tests.factories import UserFactory, ItemFactory, TagFactory, CircleFactory, CategoryFactory, LoanRequestFactory, MessageFactory
from conftest import TEST_PASSWORD

class TestUser:
    """Test User model."""
    
    def test_user_creation(self, app):
        """Test user creation."""
        with app.app_context():
            user = UserFactory()
            assert user.id is not None
            assert user.email is not None
            assert user.first_name is not None
            assert user.last_name is not None
            assert user.email_confirmed is True
    
    def test_password_hashing(self, app):
        """Test password hashing and verification."""
        with app.app_context():
            user = UserFactory()
            password = TEST_PASSWORD
            user.set_password(password)
            
            assert user.password_hash is not None
            assert user.password_hash != password
            assert user.check_password(password) is True
            assert user.check_password('wrongpassword') is False
    
    def test_user_repr(self, app):
        """Test user string representation."""
        with app.app_context():
            user = UserFactory(email='test@example.com')
            assert repr(user) == '<User test@example.com>'
    
    def test_user_full_name(self, app):
        """Test user full name property."""
        with app.app_context():
            user = UserFactory(first_name='John', last_name='Doe')
            assert user.full_name == 'John Doe'

    def test_user_is_geocoded_true(self, app):
        """Test is_geocoded property when user has coordinates."""
        with app.app_context():
            user = UserFactory(latitude=40.7128, longitude=-74.0060)
            assert user.is_geocoded is True
    
    def test_user_is_geocoded_false_no_coordinates(self, app):
        """Test is_geocoded property when user has no coordinates."""
        with app.app_context():
            user = UserFactory(latitude=None, longitude=None)
            assert user.is_geocoded is False
    
    def test_user_is_geocoded_false_partial_coordinates(self, app):
        """Test is_geocoded property when user has only one coordinate."""
        with app.app_context():
            user1 = UserFactory(latitude=40.7128, longitude=None)
            user2 = UserFactory(latitude=None, longitude=-74.0060)
            assert user1.is_geocoded is False
            assert user2.is_geocoded is False
    
    def test_user_distance_to_success(self, app):
        """Test distance calculation between two geocoded users."""
        with app.app_context():
            # New York City coordinates
            user1 = UserFactory(latitude=40.7128, longitude=-74.0060)
            # Los Angeles coordinates
            user2 = UserFactory(latitude=34.0522, longitude=-118.2437)
            
            distance = user1.distance_to(user2)
            
            # Distance between NYC and LA is approximately 2445 miles
            assert distance is not None
            assert 2400 < distance < 2500
    
    def test_user_distance_to_same_location(self, app):
        """Test distance calculation between users at same location."""
        with app.app_context():
            # Same coordinates for both users
            coords = (40.7128, -74.0060)
            user1 = UserFactory(latitude=coords[0], longitude=coords[1])
            user2 = UserFactory(latitude=coords[0], longitude=coords[1])
            
            distance = user1.distance_to(user2)
            
            # Distance should be very close to 0
            assert distance is not None
            assert distance < 0.01  # Less than 0.01 miles
    
    def test_user_distance_to_nearby_locations(self, app):
        """Test distance calculation between nearby users."""
        with app.app_context():
            # Times Square, NYC
            user1 = UserFactory(latitude=40.7580, longitude=-73.9855)
            # Central Park, NYC (about 0.5 miles away)
            user2 = UserFactory(latitude=40.7829, longitude=-73.9654)
            
            distance = user1.distance_to(user2)
            
            # Distance should be roughly 0.5-2 miles
            assert distance is not None
            assert 0.3 < distance < 3.0
    
    def test_user_distance_to_not_geocoded_self(self, app):
        """Test distance calculation when self is not geocoded."""
        with app.app_context():
            user1 = UserFactory(latitude=None, longitude=None)
            user2 = UserFactory(latitude=40.7128, longitude=-74.0060)
            
            distance = user1.distance_to(user2)
            assert distance is None
    
    def test_user_distance_to_not_geocoded_other(self, app):
        """Test distance calculation when other user is not geocoded."""
        with app.app_context():
            user1 = UserFactory(latitude=40.7128, longitude=-74.0060)
            user2 = UserFactory(latitude=None, longitude=None)
            
            distance = user1.distance_to(user2)
            assert distance is None
    
    def test_user_distance_to_neither_geocoded(self, app):
        """Test distance calculation when neither user is geocoded."""
        with app.app_context():
            user1 = UserFactory(latitude=None, longitude=None)
            user2 = UserFactory(latitude=None, longitude=None)
            
            distance = user1.distance_to(user2)
            assert distance is None
    
    def test_user_can_update_location_no_previous_geocoding(self, app):
        """Test can_update_location when user has never been geocoded."""
        with app.app_context():
            user = UserFactory(geocoded_at=None, geocoding_failed=False)
            assert user.can_update_location() is True

    def test_user_can_update_location_previous_failure(self, app):
        """Test can_update_location when previous geocoding failed."""
        with app.app_context():
            from datetime import timedelta
            yesterday = datetime.now(UTC) - timedelta(days=1)
            user = UserFactory(
                geocoded_at=yesterday,
                geocoding_failed=True
            )
            assert user.can_update_location() is True

    def test_user_can_update_location_recent_success(self, app):
        """Test can_update_location when recent geocoding was successful."""
        with app.app_context():
            from datetime import timedelta
            two_hours_ago = datetime.now(UTC) - timedelta(hours=2)
            user = UserFactory(
                geocoded_at=two_hours_ago,
                geocoding_failed=False
            )
            assert user.can_update_location() is False

    def test_user_can_update_location_old_success(self, app):
        """Test can_update_location when old geocoding was successful."""
        with app.app_context():
            from datetime import timedelta
            two_days_ago = datetime.now(UTC) - timedelta(days=2)
            user = UserFactory(
                geocoded_at=two_days_ago,
                geocoding_failed=False
            )
            assert user.can_update_location() is True


class TestItem:
    """Test Item model."""
    
    def test_item_creation(self, app):
        """Test item creation."""
        with app.app_context():
            # Use a canonical category name and avoid duplicate
            from app.models import Category
            category = Category.query.filter_by(name='Electronics').first()
            if not category:
                category = CategoryFactory(name='Electronics')
            item = ItemFactory(category=category)
            assert item.id is not None
            assert item.name is not None
            assert item.description is not None
            assert item.owner is not None
            assert item.category is not None
            assert item.available is True
    
    def test_item_repr(self, app):
        """Test item string representation."""
        with app.app_context():
            item = ItemFactory(name='Test Item')
            assert repr(item) == '<Item Test Item>'
    
    def test_item_image_property(self, app):
        """Test item image property with default."""
        with app.app_context():
            item = ItemFactory()
            # Should return default image URL when no image_url is set
            assert 'default_item_photo.png' in item.image
    
    def test_item_with_tags(self, app):
        """Test item with tags relationship."""
        with app.app_context():
            category = CategoryFactory(name='Books & Media')
            item = ItemFactory(category=category)
            tag1 = TagFactory(name='electronics')
            tag2 = TagFactory(name='vintage')
            item.tags.append(tag1)
            item.tags.append(tag2)
            assert len(item.tags) == 2
            assert tag1 in item.tags
            assert tag2 in item.tags

class TestCategory:
    """Test Category model."""
    
    def test_category_creation(self, app):
        """Test category creation."""
        with app.app_context():
            category = CategoryFactory(name='Home & Garden')
            assert category.id is not None
            assert category.name == 'Home & Garden'
    
    def test_category_repr(self, app):
        """Test category string representation."""
        with app.app_context():
            category = CategoryFactory()
            assert repr(category) == f'<Category {category.name}>'

class TestCircle:
    """Test Circle model."""
    
    def test_circle_creation(self, app):
        """Test circle creation."""
        with app.app_context():
            circle = CircleFactory()
            assert circle.id is not None
            assert circle.name is not None
            assert circle.requires_approval is False
    
    def test_circle_repr(self, app):
        """Test circle string representation."""
        with app.app_context():
            circle = CircleFactory(name='Test Circle')
            assert repr(circle) == '<Circle Test Circle>'

class TestTag:
    """Test Tag model."""
    
    def test_tag_creation(self, app):
        """Test tag creation."""
        with app.app_context():
            tag = TagFactory(name='electronics')
            assert tag.id is not None
            assert tag.name == 'electronics'
    
    def test_tag_repr(self, app):
        """Test tag string representation."""
        with app.app_context():
            tag = TagFactory(name='vintage')
            assert repr(tag) == '<Tag vintage>'

class TestLoanRequest:
    """Test LoanRequest model."""
    
    def test_loan_request_creation(self, app):
        """Test loan request creation."""
        with app.app_context():
            loan = LoanRequestFactory()
            assert loan.id is not None
            assert loan.item is not None
            assert loan.borrower is not None
            assert loan.status == 'pending'
    
    def test_loan_request_repr(self, app):
        """Test loan request string representation."""
        with app.app_context():
            item = ItemFactory(name='Test Item')
            user = UserFactory(email='test@example.com')
            loan = LoanRequestFactory(item=item, borrower=user)
            expected = f'<LoanRequest {loan.id} for Item {item.id} by User {user.id}>'
            assert repr(loan) == expected

class TestMessage:
    """Test Message model."""
    
    def test_message_creation(self, app):
        """Test message creation."""
        with app.app_context():
            message = MessageFactory()
            assert message.id is not None
            assert message.sender is not None
            assert message.recipient is not None
            assert message.body is not None
            assert message.is_read is False
    
    def test_message_repr(self, app):
        """Test message string representation."""
        with app.app_context():
            sender = UserFactory(email='sender@example.com')
            recipient = UserFactory(email='recipient@example.com')
            message = MessageFactory(sender=sender, recipient=recipient)
            expected = f'<Message from {sender.id} to {recipient.id} at {message.timestamp}>'
            assert repr(message) == expected
