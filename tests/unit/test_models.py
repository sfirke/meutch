"""Unit tests for models."""
import pytest
from app.models import User, Item, Category, Circle, Tag, LoanRequest, Message
from tests.factories import UserFactory, ItemFactory, CategoryFactory, CircleFactory, TagFactory, LoanRequestFactory, MessageFactory

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
            password = 'testpassword123'
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
    
    def test_user_email_token_methods(self, app):
        """Test user email token generation and validation methods."""
        with app.app_context():
            user = UserFactory()
            
            # Test confirmation token generation
            token = user.generate_confirmation_token()
            assert token is not None
            assert len(token) > 0
            
            # Test password reset token generation  
            reset_token = user.generate_password_reset_token()
            assert reset_token is not None
            assert len(reset_token) > 0
            
            # Test reset password method
            new_password = 'newpassword123'
            result = user.reset_password(reset_token, new_password)
            assert result is True
            assert user.check_password(new_password) is True

class TestItem:
    """Test Item model."""
    
    def test_item_creation(self, app):
        """Test item creation."""
        with app.app_context():
            item = ItemFactory()
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
            item = ItemFactory()
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
            category = CategoryFactory()
            assert category.id is not None
            assert category.name is not None
    
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
