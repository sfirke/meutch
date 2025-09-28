"""Integration tests for web links functionality."""

import pytest
from app.models import User, UserWebLink
from conftest import login_user


class TestWebLinksIntegration:
    """Test web links integration with user profiles."""
    
    def test_profile_form_renders_with_web_links(self, client, app, auth_user):
        """Test that profile form includes web link fields."""
        with app.app_context():
            user = auth_user()
            
            # Login
            login_user(client, user.email)
            
            # Access profile page
            response = client.get('/profile')
            assert response.status_code == 200
            
            # Check that web link fields are present
            data = response.data.decode()
            assert 'Where to find me on the web' in data
            assert 'link_1_platform' in data
            assert 'link_1_url' in data
            assert 'link_5_platform' in data  # Check all 5 fields are there
            
    def test_create_web_links_via_form(self, client, app, auth_user):
        """Test creating web links through the profile form."""
        with app.app_context():
            user = auth_user()
            
            # Login
            login_user(client, user.email)
            
            # Submit profile with web links
            response = client.post('/profile', data={
                'about_me': 'Test bio',
                'link_1_platform': 'instagram',
                'link_1_url': 'https://instagram.com/test',
                'link_2_platform': 'other',
                'link_2_custom_name': 'My Portfolio',
                'link_2_url': 'https://myportfolio.com',
            }, follow_redirects=True)
            
            assert response.status_code == 200
            assert b'Your profile has been updated.' in response.data
            
            # Verify links were created in database
            web_links = UserWebLink.query.filter_by(user_id=user.id).all()
            assert len(web_links) == 2
            
            # Check first link
            link1 = UserWebLink.query.filter_by(user_id=user.id, display_order=1).first()
            assert link1.platform_type == 'instagram'
            assert link1.url == 'https://instagram.com/test'
            assert link1.display_name == 'Instagram'
            
            # Check second link
            link2 = UserWebLink.query.filter_by(user_id=user.id, display_order=2).first()
            assert link2.platform_type == 'other'
            assert link2.platform_name == 'My Portfolio'
            assert link2.url == 'https://myportfolio.com'
            assert link2.display_name == 'My Portfolio'
    
    def test_user_profile_displays_web_links(self, client, app, auth_user):
        """Test that user profiles display web links correctly."""
        with app.app_context():
            user1 = auth_user()
            user2 = User(
                email='user2@example.com',
                first_name='User',
                last_name='Two',
                email_confirmed=True
            )
            user2.set_password('password')
            from app import db
            db.session.add(user2)
            db.session.flush()
            
            # Create web links for user2
            link1 = UserWebLink(
                user_id=user2.id,
                platform_type='facebook',
                url='https://facebook.com/user2',
                display_order=1
            )
            link2 = UserWebLink(
                user_id=user2.id,
                platform_type='blog',
                url='https://user2blog.com',
                display_order=2
            )
            db.session.add(link1)
            db.session.add(link2)
            db.session.commit()
            
            # Login as user1
            login_user(client, user1.email)
            
            # View user2's profile
            response = client.get(f'/user/{user2.id}')
            assert response.status_code == 200
            
            data = response.data.decode()
            assert 'Find User on the web' in data
            assert 'Facebook' in data
            assert 'Blog' in data
    
    def test_update_existing_web_links(self, client, app, auth_user):
        """Test updating existing web links."""
        with app.app_context():
            user = auth_user()
            
            # Create initial web link
            from app import db
            link = UserWebLink(
                user_id=user.id,
                platform_type='x',
                url='https://x.com/test',
                display_order=1
            )
            db.session.add(link)
            db.session.commit()
            
            # Login
            login_user(client, user.email)
            
            # Update the web link
            response = client.post('/profile', data={
                'about_me': 'Updated bio',
                'link_1_platform': 'instagram',
                'link_1_url': 'https://instagram.com/test',
            }, follow_redirects=True)
            
            assert response.status_code == 200
            
            # Check that old link was replaced
            links = UserWebLink.query.filter_by(user_id=user.id).all()
            assert len(links) == 1
            assert links[0].platform_type == 'instagram'
            assert links[0].url == 'https://instagram.com/test'
    
    def test_form_validation_errors(self, client, app, auth_user):
        """Test form validation for web links."""
        with app.app_context():
            user = auth_user()
            
            # Login
            login_user(client, user.email)
            
            # Submit invalid data (URL without platform)
            response = client.post('/profile', data={
                'about_me': 'Test bio',
                'link_1_url': 'https://example.com',
                'link_1_platform': '',  # Missing platform
            })
            
            # Should not redirect (form has validation errors)
            assert response.status_code == 200
            data = response.data.decode()
            assert 'Please select a platform when providing a URL' in data
            
            # Submit invalid data (other without custom name)
            response = client.post('/profile', data={
                'about_me': 'Test bio',
                'link_1_platform': 'other',
                'link_1_url': 'https://example.com',
                'link_1_custom_name': '',  # Missing custom name
            })
            
            # Should not redirect (form has validation errors)
            assert response.status_code == 200
            data = response.data.decode()
            assert 'Please provide a custom name when selecting' in data
