"""End-to-end functional tests for user workflows."""
import pytest
from flask import url_for
from app.models import User, Item, Category, db
from tests.factories import UserFactory, CategoryFactory

class TestUserRegistrationWorkflow:
    """Test complete user registration workflow."""
    
    def test_user_registration_and_login_flow(self, client, app):
        """Test user can register, confirm email, and login."""
        with app.app_context():
            # User registration
            response = client.post('/auth/register', data={
                'email': 'newuser@example.com',
                'first_name': 'New',
                'last_name': 'User',
                'street': '123 New St',
                'city': 'New City',
                'state': 'NY',
                'zip_code': '12345',
                'country': 'USA',
                'password': 'newpassword123',
                'confirm_password': 'newpassword123'
            }, follow_redirects=True)
            
            assert response.status_code == 200
            assert b'confirmation email has been sent' in response.data
            
            # Verify user was created but not confirmed
            user = User.query.filter_by(email='newuser@example.com').first()
            assert user is not None
            assert user.email_confirmed is False
            
            # Simulate email confirmation
            user.email_confirmed = True
            db.session.commit()
            
            # Login after confirmation
            response = client.post('/auth/login', data={
                'email': 'newuser@example.com',
                'password': 'newpassword123'
            }, follow_redirects=True)
            
            assert response.status_code == 200
            assert b'Welcome' in response.data or b'Your Items' in response.data

class TestItemManagementWorkflow:
    """Test complete item management workflow."""
    
    def test_create_edit_delete_item_flow(self, client, app, auth_user):
        """Test user can create, edit, and delete an item."""
        with app.app_context():
            user = auth_user()  # Call the function to get fresh user
            # Login
            client.post('/auth/login', data={
                'email': user.email,
                'password': 'testpassword'
            }, follow_redirects=True)
            
            # Create an item
            category = CategoryFactory(name='Test Category')
            
            response = client.post('/list-item', data={
                'name': 'Test Item',
                'description': 'A test item for testing',
                'category': str(category.id),
                'tags': 'test, sample'
            }, follow_redirects=True)
            
            assert response.status_code == 200
            assert b'Test Item' in response.data
            
            # Find the created item
            item = Item.query.filter_by(name='Test Item').first()
            assert item is not None
            assert item.owner_id == user.id
            
            # Edit the item
            response = client.post(f'/item/{item.id}/edit', data={
                'name': 'Updated Test Item',
                'description': 'An updated test item',
                'category': str(category.id),
                'tags': 'updated, test'
            }, follow_redirects=True)
            
            assert response.status_code == 200
            
            # Verify changes
            db.session.refresh(item)
            assert item.name == 'Updated Test Item'
            assert item.description == 'An updated test item'
            
            # Delete the item
            response = client.post(f'/item/{item.id}/delete', follow_redirects=True)
            
            assert response.status_code == 200
            assert b'deleted successfully' in response.data
            
            # Verify item is deleted
            deleted_item = Item.query.get(item.id)
            assert deleted_item is None

class TestLoanRequestWorkflow:
    """Test loan request workflow."""
    
    def test_complete_loan_request_flow(self, client, app):
        """Test complete loan request from request to completion."""
        with app.app_context():
            # Create two users
            borrower = UserFactory(email='borrower@test.com')
            lender = UserFactory(email='lender@test.com')
            
            # Create an item
            from tests.factories import ItemFactory
            item = ItemFactory(owner=lender)
            
            # Borrower logs in and requests item
            client.post('/auth/login', data={
                'email': borrower.email,
                'password': 'testpassword123'
            }, follow_redirects=True)
            
            response = client.post(f'/items/{item.id}/request', data={
                'start_date': '2025-06-10',
                'end_date': '2025-06-15',
                'message': 'I would like to borrow this item'
            }, follow_redirects=True)
            
            assert response.status_code == 200
            
            # Logout borrower and login lender
            client.get('/auth/logout', follow_redirects=True)
            client.post('/auth/login', data={
                'email': lender.email,
                'password': 'testpassword123'
            }, follow_redirects=True)
            
            # Lender checks messages and approves loan
            response = client.get('/messages')
            assert response.status_code == 200
            
            # Find the loan request and approve it
            from app.models import LoanRequest
            loan_request = LoanRequest.query.filter_by(
                item_id=item.id,
                borrower_id=borrower.id
            ).first()
            
            assert loan_request is not None
            assert loan_request.status == 'pending'
            
            response = client.post(f'/loan/{loan_request.id}/approve', follow_redirects=True)
            assert response.status_code == 200
            
            # Verify loan is approved
            db.session.refresh(loan_request)
            assert loan_request.status == 'approved'
            assert item.available is False

class TestCircleWorkflow:
    """Test circle management workflow."""
    
    def test_create_and_manage_circle_flow(self, client, app):
        """Test creating and managing a circle."""
        with app.app_context():
            # Create users
            admin_user = UserFactory(email='admin@test.com')
            member_user = UserFactory(email='member@test.com')
            
            # Admin creates circle
            client.post('/auth/login', data={
                'email': admin_user.email,
                'password': 'testpassword123'
            }, follow_redirects=True)
            
            response = client.post('/circles/circles', data={
                'create_circle': True,
                'name': 'Test Circle',
                'description': 'A test circle',
                'requires_approval': True
            }, follow_redirects=True)
            
            assert response.status_code == 200
            assert b'Test Circle' in response.data
            
            # Find created circle
            from app.models import Circle
            circle = Circle.query.filter_by(name='Test Circle').first()
            assert circle is not None
            assert circle.is_admin(admin_user)
            
            # Member requests to join
            client.get('/auth/logout', follow_redirects=True)
            client.post('/auth/login', data={
                'email': member_user.email,
                'password': 'testpassword123'
            }, follow_redirects=True)
            
            response = client.post(f'/circles/circles/join/{circle.id}', data={
                'message': 'I would like to join this circle'
            }, follow_redirects=True)
            
            assert response.status_code == 200
            
            # Admin approves request
            client.get('/auth/logout', follow_redirects=True)
            client.post('/auth/login', data={
                'email': admin_user.email,
                'password': 'testpassword123'
            }, follow_redirects=True)
            
            # Find join request
            from app.models import CircleJoinRequest
            join_request = CircleJoinRequest.query.filter_by(
                circle_id=circle.id,
                user_id=member_user.id
            ).first()
            
            assert join_request is not None
            
            response = client.post(f'/circles/circles/{circle.id}/request/{join_request.id}/approve', 
                                   follow_redirects=True)
            assert response.status_code == 200
            
            # Verify member was added
            assert member_user in circle.members

class TestSearchAndBrowsingWorkflow:
    """Test search and browsing functionality."""
    
    def test_search_and_browse_items(self, client, app):
        """Test searching and browsing items."""
        with app.app_context():
            # Create test data
            user = UserFactory()
            category = CategoryFactory()
            
            from tests.factories import ItemFactory, TagFactory
            tag1 = TagFactory(name='laptop')
            tag2 = TagFactory(name='computer')
            
            item1 = ItemFactory(
                name='Gaming Laptop',
                description='High-performance gaming laptop',
                owner=user,
                category=category
            )
            item1.tags.append(tag1)
            item1.tags.append(tag2)
            
            item2 = ItemFactory(
                name='Office Monitor',
                description='24-inch office monitor',
                owner=user,
                category=category
            )
            
            db.session.commit()
            
            # Search for items
            response = client.get('/search?q=laptop')
            assert response.status_code == 200
            assert b'Gaming Laptop' in response.data
            assert b'Office Monitor' not in response.data
            
            # Search by tag
            response = client.get('/search?q=computer')
            assert response.status_code == 200
            assert b'Gaming Laptop' in response.data
            
            # Browse by category
            response = client.get(f'/tag/{tag1.id}')
            assert response.status_code == 200
            assert b'Gaming Laptop' in response.data

class TestMessagingWorkflow:
    """Test messaging functionality."""
    
    def test_send_and_receive_messages(self, client, app):
        """Test messaging between users."""
        with app.app_context():
            # Create users and item
            sender = UserFactory(email='sender@test.com')
            recipient = UserFactory(email='recipient@test.com')
            
            from tests.factories import ItemFactory
            item = ItemFactory(owner=recipient)
            
            # Sender logs in and sends message
            client.post('/auth/login', data={
                'email': sender.email,
                'password': 'testpassword123'
            }, follow_redirects=True)
            
            response = client.post(f'/item/{item.id}', data={
                'body': 'Hello, I am interested in this item!'
            }, follow_redirects=True)
            
            assert response.status_code == 200
            assert b'message has been sent' in response.data
            
            # Recipient logs in and checks messages
            client.get('/auth/logout', follow_redirects=True)
            client.post('/auth/login', data={
                'email': recipient.email,
                'password': 'testpassword123'
            }, follow_redirects=True)
            
            response = client.get('/messages')
            assert response.status_code == 200
            assert b'interested in this item' in response.data
            
            # Check unread count in context
            from app.models import Message
            message = Message.query.filter_by(
                sender_id=sender.id,
                recipient_id=recipient.id,
                item_id=item.id
            ).first()
            
            assert message is not None
            assert message.is_read is False
            
            # View conversation
            response = client.get(f'/message/{message.id}')
            assert response.status_code == 200
            assert b'interested in this item' in response.data
            
            # Message should be marked as read
            db.session.refresh(message)
            assert message.is_read is True
