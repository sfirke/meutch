"""Integration tests for main routes."""
import pytest
from app import db
from app.models import Item, User, Category, Circle
from tests.factories import UserFactory, ItemFactory, CategoryFactory, CircleFactory, TagFactory, LoanRequestFactory, UserWebLinkFactory, ItemRequestFactory, CircleJoinRequestFactory
from conftest import login_user
from unittest.mock import patch
import io

class TestMainRoutes:
    """Test main application routes."""
    
    def test_index_page(self, client, app):
        """Test index page loads correctly."""
        response = client.get('/')
        assert response.status_code == 200
        assert b'Welcome to Meutch' in response.data
    
    def test_index_with_authenticated_user(self, client, app, auth_user):
        """Test index page with authenticated user."""
        with app.app_context():
            user = auth_user()  # Call the function to get fresh user
            login_user(client, user.email)
            response = client.get('/')
            assert response.status_code == 200
            assert b'Community Activity' in response.data
            assert b'Create Request' in response.data
            assert b'List Item' in response.data

    def test_index_with_authenticated_user_renders_feed_filter_controls(self, client, app, auth_user):
        """Test authenticated homepage renders feed filter controls with smart defaults."""
        with app.app_context():
            user = auth_user()
            user.latitude = 0.0
            user.longitude = 0.0
            db.session.commit()

            login_user(client, user.email)
            response = client.get('/')

            assert response.status_code == 200
            content = response.data.decode('utf-8')
            assert 'name="scope"' in content
            assert 'All Activity' in content
            assert 'My Circles' in content
            assert 'name="distance"' in content
            assert 'value="requests"' in content
            assert 'value="giveaways"' in content
            assert 'value="circle_joins"' in content
            assert 'value="loans"' in content
            assert 'option value="20" selected' in content

    def test_home_feed_scope_circles_hides_non_shared_public_request_and_giveaway(self, client, app, auth_user):
        """Test scope=circles hides public request and giveaway from users without a shared circle."""
        with app.app_context():
            viewer = auth_user()
            shared_user = UserFactory()
            outsider = UserFactory()
            category = CategoryFactory()

            shared_circle = CircleFactory()
            shared_circle.members.extend([viewer, shared_user])

            outsider_circle = CircleFactory()
            outsider_circle.members.append(outsider)

            ItemRequestFactory(user=shared_user, title='Shared Scope Request', visibility='public')
            ItemRequestFactory(user=outsider, title='Outsider Scope Request', visibility='public')

            ItemFactory(
                owner=shared_user,
                category=category,
                is_giveaway=True,
                giveaway_visibility='public',
                claim_status='unclaimed',
                name='Shared Scope Giveaway',
            )
            ItemFactory(
                owner=outsider,
                category=category,
                is_giveaway=True,
                giveaway_visibility='public',
                claim_status='unclaimed',
                name='Outsider Scope Giveaway',
            )
            db.session.commit()

            login_user(client, viewer.email)

            all_scope_response = client.get('/')
            all_scope_content = all_scope_response.data.decode('utf-8')
            assert 'Shared Scope Request' in all_scope_content
            assert 'Outsider Scope Request' in all_scope_content
            assert 'Shared Scope Giveaway' in all_scope_content
            assert 'Outsider Scope Giveaway' in all_scope_content

            circles_scope_response = client.get('/?scope=circles')
            circles_scope_content = circles_scope_response.data.decode('utf-8')
            assert 'Shared Scope Request' in circles_scope_content
            assert 'Outsider Scope Request' not in circles_scope_content
            assert 'Shared Scope Giveaway' in circles_scope_content
            assert 'Outsider Scope Giveaway' not in circles_scope_content

    def test_home_feed_distance_filter_hides_far_requests_and_giveaways(self, client, app, auth_user):
        """Test distance filter applies to request and giveaway activity."""
        with app.app_context():
            viewer = auth_user()
            viewer.latitude = 40.7128  # NYC
            viewer.longitude = -74.0060

            near_user = UserFactory(latitude=40.7400, longitude=-74.0100)  # Nearby NYC
            far_user = UserFactory(latitude=42.3601, longitude=-71.0589)  # Boston
            category = CategoryFactory()
            circle = CircleFactory()
            circle.members.extend([viewer, near_user, far_user])

            ItemRequestFactory(user=near_user, title='Near Distance Request', visibility='public')
            ItemRequestFactory(user=far_user, title='Far Distance Request', visibility='public')

            ItemFactory(
                owner=near_user,
                category=category,
                is_giveaway=True,
                giveaway_visibility='default',
                claim_status='unclaimed',
                name='Near Distance Giveaway',
            )
            ItemFactory(
                owner=far_user,
                category=category,
                is_giveaway=True,
                giveaway_visibility='default',
                claim_status='unclaimed',
                name='Far Distance Giveaway',
            )
            db.session.commit()

            login_user(client, viewer.email)
            response = client.get('/?distance=5')
            content = response.data.decode('utf-8')

            assert 'Near Distance Request' in content
            assert 'Far Distance Request' not in content
            assert 'Near Distance Giveaway' in content
            assert 'Far Distance Giveaway' not in content

    def test_home_feed_type_checkboxes_hide_unchecked_event_types(self, client, app, auth_user):
        """Test type checkbox filters hide unchecked activity event types."""
        with app.app_context():
            viewer = auth_user()
            owner = UserFactory()
            borrower = UserFactory()
            joiner = UserFactory(first_name='Joiner', last_name='Person')
            category = CategoryFactory()

            circle = CircleFactory()
            circle.members.extend([viewer, owner, borrower])

            ItemRequestFactory(user=owner, title='Type Filter Request', visibility='public')
            ItemFactory(
                owner=owner,
                category=category,
                is_giveaway=True,
                giveaway_visibility='default',
                claim_status='unclaimed',
                name='Type Filter Giveaway',
            )

            lent_item = ItemFactory(owner=owner, category=category, name='Type Filter Lent Item')
            LoanRequestFactory(item=lent_item, borrower=borrower, status='approved')

            join_event = CircleJoinRequestFactory(circle=circle, user=joiner, status='approved')
            db.session.add(join_event)
            db.session.commit()

            login_user(client, viewer.email)
            response = client.get('/?types_present=1&types=requests&types=giveaways')
            content = response.data.decode('utf-8')

            assert 'Type Filter Request' in content
            assert 'Type Filter Giveaway' in content
            assert 'Type Filter Lent Item' not in content
            assert f'{joiner.full_name} joined {circle.name}' not in content

    def test_home_feed_circle_join_links_to_specific_circle_and_hides_combined_metadata_row(self, client, app, auth_user):
        """Circle-join feed cards should link to the joined circle and not render the combined metadata row."""
        with app.app_context():
            viewer = auth_user()
            joiner = UserFactory(first_name='Circle', last_name='Joiner')
            circle = CircleFactory(name='Neighborhood Circle')
            circle.members.append(viewer)

            join_event = CircleJoinRequestFactory(circle=circle, user=joiner, status='approved')
            db.session.add(join_event)
            db.session.commit()

            login_user(client, viewer.email)
            response = client.get('/')
            content = response.data.decode('utf-8')

            assert response.status_code == 200
            assert f'href="/circles/{circle.id}"' in content
            assert 'View Circle' in content
            assert 'View Circles' not in content
            assert 'activity-feed-meta' not in content

    def test_find_page_requires_login(self, client):
        """Test /find requires authentication."""
        response = client.get('/find')
        assert response.status_code == 302
        assert '/auth/login' in response.headers['Location']

    def test_find_page_with_authenticated_user(self, client, app, auth_user):
        """Test /find shows the search/find experience for authenticated users."""
        with app.app_context():
            user = auth_user()
            login_user(client, user.email)
            response = client.get('/find')
            assert response.status_code == 200
            assert b'Find Items' in response.data
            assert b'Join a circle to get started' in response.data
    
    def test_index_anonymous_user_limited_items(self, client, app):
        """Test that anonymous users see limited items with 'more' message."""
        with app.app_context():
            # Create more than 12 items to test the limit
            category = CategoryFactory()
            # User must be marked as public showcase for items to be visible to anonymous users
            user = UserFactory(is_public_showcase=True)
            db.session.commit()
            
            for i in range(15):
                ItemFactory(owner=user, category=category, available=True)
            
            response = client.get('/')
            assert response.status_code == 200
            # Should show the "more" message since we have more than 12 items
            response_text = response.data.decode('utf-8')
            assert 'more</strong> available items' in response_text
            assert b'Sign Up' in response.data
    
    def test_find_authenticated_user_pagination(self, client, app, auth_user):
        """Test that authenticated users get pagination controls on /find."""
        with app.app_context():
            user = auth_user()
            other_user = UserFactory()
            category = CategoryFactory()
            
            # Create a circle and add both users to it so auth_user can see other_user's items
            circle = Circle(name="Test Circle", description="Test", circle_type='open')
            db.session.add(circle)
            circle.members.append(user)
            circle.members.append(other_user)
            db.session.commit()
            
            # Create more than 12 items for the other user (not auth_user)
            for i in range(15):
                ItemFactory(owner=other_user, category=category, available=True)
            
            login_user(client, user.email)
            response = client.get('/find')
            assert response.status_code == 200
            
            # Should have pagination controls since we have 15 items (> 12 per page)
            response_text = response.data.decode('utf-8')
            assert 'aria-label="Items pages"' in response_text  # Pagination nav element
            assert 'Page 1 of 2' in response_text or 'page-item' in response_text  # Pagination indicators
            
            # Test that page 2 exists and works
            page2_response = client.get('/find?page=2')
            assert page2_response.status_code == 200
            page2_text = page2_response.data.decode('utf-8')
            assert 'aria-label="Items pages"' in page2_text

    def test_find_public_giveaway_visible_without_query(self, client, app, auth_user):
        """Public giveaways from any circle member should appear on /find even without a search query."""
        with app.app_context():
            user = auth_user()
            # owner is in a separate circle from the viewer — not a shared circle
            owner = UserFactory()
            category = CategoryFactory()

            # Put each user in their own circle (no shared circles)
            user_circle = Circle(name="User Circle", description="", circle_type='open')
            owner_circle = Circle(name="Owner Circle", description="", circle_type='open')
            db.session.add_all([user_circle, owner_circle])
            user_circle.members.append(user)
            owner_circle.members.append(owner)
            db.session.commit()

            public_giveaway = ItemFactory(
                owner=owner,
                category=category,
                is_giveaway=True,
                giveaway_visibility='public',
                claim_status='unclaimed',
            )
            db.session.commit()

            login_user(client, user.email)
            response = client.get('/find')
            assert response.status_code == 200
            assert public_giveaway.name.encode() in response.data

    def test_find_public_giveaway_visible_with_query(self, client, app, auth_user):
        """Public giveaways from any circle member should appear on /find with a search query."""
        with app.app_context():
            user = auth_user()
            owner = UserFactory()
            category = CategoryFactory()

            user_circle = Circle(name="User Circle 2", description="", circle_type='open')
            owner_circle = Circle(name="Owner Circle 2", description="", circle_type='open')
            db.session.add_all([user_circle, owner_circle])
            user_circle.members.append(user)
            owner_circle.members.append(owner)
            db.session.commit()

            public_giveaway = ItemFactory(
                owner=owner,
                category=category,
                name="UniquePublicGiveawayItem",
                is_giveaway=True,
                giveaway_visibility='public',
                claim_status='unclaimed',
            )
            db.session.commit()

            login_user(client, user.email)
            response = client.get('/find?q=UniquePublicGiveawayItem')
            assert response.status_code == 200
            assert public_giveaway.name.encode() in response.data

    def test_index_anonymous_user_few_items_no_more_message(self, client, app):
        """Test that anonymous users don't see 'more' message when items <= 12."""
        with app.app_context():
            # Create only a few items
            category = CategoryFactory()
            user = UserFactory()
            
            # Create a public circle and add the user to it
            circle = Circle(name="Test Public Circle", description="Test", circle_type='open')
            db.session.add(circle)
            circle.members.append(user)
            db.session.commit()
            
            for i in range(5):
                ItemFactory(owner=user, category=category, available=True)
            
            response = client.get('/')
            assert response.status_code == 200
            # Should NOT show the "more" message since we have <= 12 items
            response_text = response.data.decode('utf-8')
            assert 'more</strong> available items' not in response_text

    def test_index_anonymous_user_shows_distinct_giveaway_ribbon(self, client, app):
        """Test anonymous index uses giveaway ribbon styling for free items."""
        with app.app_context():
            category = CategoryFactory()
            user = UserFactory(is_public_showcase=True)
            db.session.commit()

            ItemFactory(owner=user, category=category, name='Loan Drill', is_giveaway=False, available=True)
            ItemFactory(
                owner=user,
                category=category,
                name='Free Drill',
                is_giveaway=True,
                giveaway_visibility='public',
                claim_status='unclaimed',
                available=True
            )
            db.session.commit()

            response = client.get('/')
            assert response.status_code == 200
            response_text = response.data.decode('utf-8')
            assert 'Loan Drill' in response_text
            assert 'Free Drill' in response_text
            assert response_text.count('giveaway-ribbon') == 1
            loan_index = response_text.index('Loan Drill')
            loan_card_snippet = response_text[max(0, loan_index - 500):loan_index + 200]
            assert 'giveaway-ribbon' not in loan_card_snippet
    
    def test_about_page(self, client):
        """Test about page loads correctly."""
        response = client.get('/about')
        assert response.status_code == 200

class TestItemRoutes:
    """Test item-related routes."""
    
    def test_list_item_get_requires_login(self, client):
        """Test that listing items requires login."""
        response = client.get('/list-item')
        assert response.status_code == 302  # Redirect to login
    
    def test_list_item_get_authenticated(self, client, app, auth_user):
        """Test list item page for authenticated user."""
        with app.app_context():
            user = auth_user()  # Call the function to get fresh user
            login_user(client, user.email)
            response = client.get('/list-item')
            assert response.status_code == 200
            assert b'List a New Item' in response.data
    
    def test_list_item_post_valid(self, client, app, auth_user):
        """Test creating a new item."""
        with app.app_context():
            user = auth_user()  # Call the function to get fresh user
            category = CategoryFactory()
            login_user(client, user.email)
            
            response = client.post('/list-item', data={
                'name': 'Test Item',
                'description': 'A test item',
                'category': str(category.id),
                'tags': 'electronics, test'
            }, follow_redirects=True)
            
            assert response.status_code == 200
            assert b'has been listed successfully!' in response.data
            
            # Verify item was created
            item = Item.query.filter_by(name='Test Item').first()
            assert item is not None
            assert item.owner_id == user.id
            assert len(item.tags) == 2

    def test_list_item_post_create_another_redirects_to_list_form(self, client, app, auth_user):
        """Test create-another submit action returns user to the list-item form."""
        with app.app_context():
            user = auth_user()
            category = CategoryFactory()
            login_user(client, user.email)

            response = client.post('/list-item', data={
                'name': 'Another Item',
                'description': 'A test item for create another flow',
                'category': str(category.id),
                'submit_and_create_another': 'List Item & Create Another'
            }, follow_redirects=False)

            assert response.status_code == 302
            assert response.headers['Location'].endswith('/list-item')

            item = Item.query.filter_by(name='Another Item').first()
            assert item is not None
            assert item.owner_id == user.id
    
    def test_item_detail_requires_login(self, client, app):
        """Test that item detail requires login."""
        with app.app_context():
            item = ItemFactory()
            response = client.get(f'/item/{item.id}')
            assert response.status_code == 302  # Redirect to login
    
    def test_item_detail_authenticated(self, client, app, auth_user):
        """Test item detail page for authenticated user."""
        with app.app_context():
            user = auth_user()  # Call the function to get fresh user
            item = ItemFactory()
            login_user(client, user.email)
            
            response = client.get(f'/item/{item.id}')
            assert response.status_code == 200
            assert item.name.encode() in response.data
    
    def test_edit_item_own_item(self, client, app, auth_user):
        """Test editing own item."""
        with app.app_context():
            user = auth_user()  # Call the function to get fresh user
            category = CategoryFactory()
            item = ItemFactory(owner=user, category=category)
            login_user(client, user.email)
            
            response = client.get(f'/item/{item.id}/edit')
            assert response.status_code == 200
            assert b'Edit Item' in response.data
    
    def test_edit_item_not_owner(self, client, app, auth_user):
        """Test editing item not owned by user."""
        with app.app_context():
            user = auth_user()  # Call the function to get fresh user
            other_user = UserFactory()
            item = ItemFactory(owner=other_user)
            login_user(client, user.email)
            
            response = client.get(f'/item/{item.id}/edit', follow_redirects=True)
            assert response.status_code == 200
            assert b'You do not have permission to edit this item.' in response.data
    
    def test_edit_item_post_valid(self, client, app, auth_user):
        """Test updating an item."""
        with app.app_context():
            user = auth_user()  # Call the function to get fresh user
            category = CategoryFactory()
            item = ItemFactory(owner=user, category=category)
            login_user(client, user.email)
            
            response = client.post(f'/item/{item.id}/edit', data={
                'name': 'Updated Item Name',
                'description': 'Updated description',
                'category': str(category.id),
                'tags': 'updated, tags'
            }, follow_redirects=True)
            
            assert response.status_code == 200
            assert b'Item has been updated.' in response.data
            
            # Verify item was updated
            updated_item = db.session.get(Item, item.id)
            assert updated_item.name == 'Updated Item Name'
            assert updated_item.description == 'Updated description'

    def test_edit_item_redirects_to_item_detail(self, client, app, auth_user):
        """After editing an item, the user should be redirected to the item's detail page."""
        with app.app_context():
            user = auth_user()
            category = CategoryFactory()
            item = ItemFactory(owner=user, category=category)
            login_user(client, user.email)

            # Don't follow redirects so we can inspect the Location header
            response = client.post(f'/item/{item.id}/edit', data={
                'name': 'Redirected Name',
                'description': 'Redirect description',
                'category': str(category.id),
                'tags': 'redirect, test'
            }, follow_redirects=False)

            # Expect a redirect (302) to the item detail page
            assert response.status_code in (301, 302)
            location = response.headers.get('Location', '')
            assert f'/item/{item.id}' in location

            # Confirm the database was updated
            updated = db.session.get(Item, item.id)
            assert updated.name == 'Redirected Name'
    
    def test_edit_item_retains_category(self, client, app, auth_user):
        """Test that the category is retained when editing an item."""
        with app.app_context():
            user = auth_user()
            category = CategoryFactory()
            item = ItemFactory(owner=user, category=category, name='Original Item', description='Original description')
            # Add tags to verify they are also retained (as reference)
            tag1 = TagFactory(name='tag1')
            tag2 = TagFactory(name='tag2')
            item.tags.append(tag1)
            item.tags.append(tag2)
            db.session.commit()
            
            login_user(client, user.email)
            
            # GET request to edit page
            response = client.get(f'/item/{item.id}/edit')
            assert response.status_code == 200
            response_text = response.data.decode('utf-8')
            
            # Verify the category is present and pre-selected in the form
            assert str(category.id) in response_text, \
                   f"Category ID {category.id} should be present in the edit form"
            # Check that the category option has the "selected" attribute
            assert f'<option selected value="{category.id}">{category.name}</option>' in response_text or \
                   f'<option value="{category.id}" selected>{category.name}</option>' in response_text, \
                   "Category should be pre-selected in the edit form"
            
            # Verify tags are also populated (as reference)
            assert 'tag1, tag2' in response_text or 'tag2, tag1' in response_text, \
                   "Tags should be pre-populated in the edit form"
    
    def test_delete_item_own_item(self, client, app, auth_user):
        """Test deleting own item."""
        with app.app_context():
            user = auth_user()  # Call the function to get fresh user
            item = ItemFactory(owner=user)
            item_id = item.id
            login_user(client, user.email)
            
            response = client.post(f'/item/{item.id}/delete', follow_redirects=True)
            assert response.status_code == 200
            assert b'Item deleted successfully.' in response.data
            
            # Verify item was deleted
            deleted_item = db.session.get(Item, item_id)
            assert deleted_item is None
    
    def test_delete_item_not_owner(self, client, app, auth_user):
        """Test deleting item not owned by user."""
        with app.app_context():
            user = auth_user()  # Call the function to get fresh user
            other_user = UserFactory()
            item = ItemFactory(owner=other_user)
            login_user(client, user.email)
            
            response = client.post(f'/item/{item.id}/delete', follow_redirects=True)
            assert response.status_code == 200
            assert b'You can only delete your own items.' in response.data
    
    def test_add_item_image_upload_failure(self, app, client, auth_user):
        """Test adding item when image upload fails."""
        with app.app_context():
            user = auth_user()
            category = CategoryFactory() 
            login_user(client, user.email)

            with patch('app.main.routes.upload_item_image', return_value=None):
                response = client.post('/list-item', data={
                    'name': 'Test Item',
                    'description': 'Test Description',
                    'category': str(category.id),
                    'image': (io.BytesIO(b'fake image data'), 'test.jpg'),
                    'tags': 'electronics, test'
                }, follow_redirects=True, content_type='multipart/form-data')

                assert response.status_code == 200
                assert b'Image upload failed' in response.data
                
                # Verify item was not created due to upload failure
                item = Item.query.filter_by(name='Test Item').first()
                assert item is None, "Item should not be created when image upload fails"

class TestSearchRoutes:
    """Test search functionality."""

class TestTagAndCategoryBrowsing:
    """Test tag and category browsing functionality."""
    
    def test_tag_items_page_valid_tag(self, client, app):
        """Test tag items page with valid tag."""
        with app.app_context():

            # Create a user and login
            from conftest import login_user
            user = UserFactory()
            login_user(client, user.email)
            
            # Create item owner and a shared circle
            item_owner = UserFactory()
            circle = CircleFactory()
            circle.members.append(user)
            circle.members.append(item_owner)
            
            # Create a tag and some items with that tag
            tag = TagFactory(name='electronics')
            
            # Get or create categories - use factory-generated unique names
            electronics_category = CategoryFactory()
            
            books_category = CategoryFactory()
            
            # Create items with this tag - owned by user in shared circle
            item1 = ItemFactory(name='Laptop', category=electronics_category, owner=item_owner)
            item2 = ItemFactory(name='Phone', category=electronics_category, owner=item_owner)
            item3 = ItemFactory(name='Book', category=books_category, owner=item_owner)  # Different category, no tag
            
            item1.tags.append(tag)
            item2.tags.append(tag)
            # item3 has no tags
            
            db.session.commit()
            
            response = client.get(f'/tag/{tag.id}')
            assert response.status_code == 200
            assert b'Items Tagged "electronics"' in response.data
            assert b'Laptop' in response.data
            assert b'Phone' in response.data
            assert b'Book' not in response.data  # Should not appear since it doesn't have the tag
    
    def test_tag_items_page_invalid_tag(self, client, app):
        """Test tag items page with invalid tag ID."""
        with app.app_context():
            from conftest import login_user
            user = UserFactory()
            login_user(client, user.email)
            
            import uuid
            fake_tag_id = str(uuid.uuid4())
            response = client.get(f'/tag/{fake_tag_id}')
            assert response.status_code == 404
    
    def test_tag_items_page_no_items(self, client, app):
        """Test tag items page with tag that has no items."""
        with app.app_context():
            from conftest import login_user
            user = UserFactory()
            login_user(client, user.email)
            
            # User must be in a circle to see the "no items" message (not the "join a circle" message)
            circle = CircleFactory()
            circle.members.append(user)
            
            tag = TagFactory(name='unused-tag')
            db.session.commit()
            
            response = client.get(f'/tag/{tag.id}')
            assert response.status_code == 200
            assert b'Items Tagged "unused-tag"' in response.data
            assert b'No items found with the tag "unused-tag"' in response.data
    
    def test_tag_items_pagination(self, client, app):
        """Test tag items page pagination."""
        with app.app_context():
            from conftest import login_user
            user = UserFactory()
            login_user(client, user.email)
            
            # Create item owner and shared circle
            item_owner = UserFactory()
            circle = CircleFactory()
            circle.members.append(user)
            circle.members.append(item_owner)
                        
            tag = TagFactory(name='test-pagination')
            
            # Get or create category
            category = CategoryFactory()
            
            # Create more than 12 items (current per_page) with this tag - owned by circle member
            items = []
            from datetime import timedelta, UTC
            import datetime as dt
            base_time = dt.datetime.now(UTC)
            for i in range(15):
                item = ItemFactory(name=f'Item {i}', category=category, owner=item_owner)
                # Set created_at explicitly to ensure proper ordering (older items get older timestamps)
                item.created_at = base_time - timedelta(minutes=15-i)
                item.tags.append(tag)
                items.append(item)
            
            db.session.commit()
            
            # Test first page (newest items first)
            response = client.get(f'/tag/{tag.id}')
            assert response.status_code == 200
            assert b'Item 14' in response.data  # Newest item should be on page 1
            assert b'Item 3' in response.data   # Last item on page 1 (12 items per page)
            assert b'Item 2' not in response.data  # Should be on page 2
            
            # Test second page
            response = client.get(f'/tag/{tag.id}?page=2')
            assert response.status_code == 200
            assert b'Item 2' in response.data   # First item on page 2
            assert b'Item 0' in response.data   # Oldest item should be on page 2
            assert b'Item 14' not in response.data  # Should be on page 1
    
    def test_category_items_page_valid_category(self, client, app):
        """Test category items page with valid category."""
        with app.app_context():
            from conftest import login_user
            user = UserFactory()
            login_user(client, user.email)
            
            # Create item owner and shared circle
            item_owner = UserFactory()
            circle = CircleFactory()
            circle.members.append(user)
            circle.members.append(item_owner)
                        
            # Create categories
            category = CategoryFactory()
                
            books_category = CategoryFactory()
            
            # Create items in this category - owned by circle member
            item1 = ItemFactory(name='Laptop', category=category, owner=item_owner)
            item2 = ItemFactory(name='Phone', category=category, owner=item_owner)
            item3 = ItemFactory(name='Book', category=books_category, owner=item_owner)  # Different category
            
            db.session.commit()
            
            response = client.get(f'/category/{category.id}')
            assert response.status_code == 200
            assert b'Items in' in response.data
            assert b'Laptop' in response.data
            assert b'Phone' in response.data
            assert b'Book' not in response.data  # Should not appear since it's in a different category
    
    def test_category_items_page_invalid_category(self, client, app):
        """Test category items page with invalid category ID."""
        with app.app_context():
            from conftest import login_user
            user = UserFactory()
            login_user(client, user.email)
            
            import uuid
            fake_category_id = str(uuid.uuid4())
            response = client.get(f'/category/{fake_category_id}')
            assert response.status_code == 404
    
    def test_category_items_page_no_items(self, client, app):
        """Test category items page with category that has no items."""
        with app.app_context():
            from conftest import login_user
            user = UserFactory()
            login_user(client, user.email)
            
            # User must be in a circle to see the "no items" message
            circle = CircleFactory()
            circle.members.append(user)
            
            category = CategoryFactory()
            
            db.session.commit()
            
            response = client.get(f'/category/{category.id}')
            assert response.status_code == 200
            assert f'Items in "{category.name}"'.encode() in response.data
            assert f'No items found in the "{category.name}" category'.encode() in response.data
    
    def test_category_items_pagination(self, client, app):
        """Test category items page pagination."""
        with app.app_context():
            from conftest import login_user
            user = UserFactory()
            login_user(client, user.email)
            
            # Create item owner and shared circle
            item_owner = UserFactory()
            circle = CircleFactory()
            circle.members.append(user)
            circle.members.append(item_owner)
            
            category = CategoryFactory()
            
            # Create more than 12 items (current per_page) in this category - owned by circle member
            items = []
            from datetime import timedelta, UTC
            import datetime as dt
            base_time = dt.datetime.now(UTC)
            for i in range(15):
                item = ItemFactory(name=f'Item {i}', category=category, owner=item_owner)
                # Set created_at explicitly to ensure proper ordering (older items get older timestamps)
                item.created_at = base_time - timedelta(minutes=15-i)
                items.append(item)
            
            db.session.commit()
            
            # Test first page (newest items first)
            response = client.get(f'/category/{category.id}')
            assert response.status_code == 200
            assert b'Item 14' in response.data  # Newest item should be on page 1
            assert b'Item 3' in response.data   # Last item on page 1 (12 items per page)
            assert b'Item 2' not in response.data  # Should be on page 2
            
            # Test second page
            response = client.get(f'/category/{category.id}?page=2')
            assert response.status_code == 200
            assert b'Item 2' in response.data   # First item on page 2
            assert b'Item 0' in response.data   # Oldest item should be on page 2
            assert b'Item 14' not in response.data  # Should be on page 1

class TestProfileRoutes:
    """Test profile-related routes."""
    
    def test_profile_requires_login(self, client):
        """Test that profile requires login."""
        response = client.get('/profile')
        assert response.status_code == 302  # Redirect to login
    
    def test_profile_authenticated(self, client, app, auth_user):
        """Test profile page for authenticated user."""
        with app.app_context():
            user = auth_user()  # Call the function to get fresh user
            login_user(client, user.email)
            response = client.get('/profile')
            assert response.status_code == 200
            assert b'About Me' in response.data
    
    def test_profile_has_tabs(self, client, app, auth_user):
        """Test profile page has tab navigation."""
        with app.app_context():
            user = auth_user()
            login_user(client, user.email)
            response = client.get('/profile')
            assert response.status_code == 200
            content = response.data.decode('utf-8')
            assert 'my-items-tab' in content
            assert 'active-loans-tab' in content
            assert 'about-me-tab' in content
            assert 'settings-tab' in content
    
    def test_profile_about_me_read_only_by_default(self, client, app, auth_user):
        """Test that the About Me section shows read-only view by default."""
        with app.app_context():
            user = auth_user()
            user.about_me = 'Test bio content'
            db.session.commit()
            
            login_user(client, user.email)
            response = client.get('/profile')
            assert response.status_code == 200
            content = response.data.decode('utf-8')
            # Edit button should be present
            assert 'Edit Profile' in content
            # Read-only view is visible (not hidden)
            assert 'id="profile-view"' in content
            assert 'id="profile-view" class="d-none"' not in content
            # Edit form exists but is hidden
            assert 'id="profile-edit"' in content
            assert 'id="profile-edit" class="d-none"' in content
    
    def test_profile_edit_form_shown_on_validation_error(self, client, app, auth_user):
        """Test that edit form is shown when form validation fails."""
        with app.app_context():
            user = auth_user()
            login_user(client, user.email)
            
            # Submit invalid data (URL without platform)
            response = client.post('/profile', data={
                'about_me': 'Test bio',
                'link_1_url': 'https://example.com',
                'link_1_platform': '',
            })
            assert response.status_code == 200
            content = response.data.decode('utf-8')
            # About Me tab should be active when form has errors
            assert 'about-me-tab' in content
            # Edit view should be visible and read-only view hidden on validation errors
            assert 'id="profile-view" class="d-none"' in content
            assert 'id="profile-edit" class="d-none"' not in content

    def test_profile_active_loans_have_clickable_user_and_item_links(self, client, app, auth_user):
        """Test active loans tab links borrower/lender names and item thumbnail/name."""
        with app.app_context():
            user = auth_user()
            lender = UserFactory()
            borrower = UserFactory()
            category = CategoryFactory()

            # Shared circle ensures profile links are accessible
            circle = CircleFactory()
            circle.members.append(user)
            circle.members.append(lender)
            circle.members.append(borrower)

            borrowed_item = ItemFactory(owner=lender, category=category, name='Borrowed Item', image_url='https://example.com/borrowed.jpg')
            lent_item = ItemFactory(owner=user, category=category, name='Lent Item', image_url='https://example.com/lent.jpg')

            LoanRequestFactory(item=borrowed_item, borrower=user, status='approved')
            LoanRequestFactory(item=lent_item, borrower=borrower, status='approved')
            db.session.commit()

            login_user(client, user.email)
            response = client.get('/profile?tab=active-loans')
            assert response.status_code == 200
            content = response.data.decode('utf-8')

            # Borrowing section: lender profile + item links (name + thumbnail)
            assert f'href="/user/{lender.id}"' in content
            borrowed_item_href = f'href="/item/{borrowed_item.id}"'
            assert content.count(borrowed_item_href) >= 2

            # Lending section: borrower profile + item links (name + thumbnail)
            assert f'href="/user/{borrower.id}"' in content
            lent_item_href = f'href="/item/{lent_item.id}"'
            assert content.count(lent_item_href) >= 2

    def test_profile_displays_custom_other_site_name(self, client, app, auth_user):
        """Test that custom name for 'Other' web links is shown in read-only profile view."""
        with app.app_context():
            user = auth_user()
            UserWebLinkFactory(
                user=user,
                platform_type='other',
                platform_name='GitHub',
                url='https://github.com/example_user',
                display_order=1
            )
            db.session.commit()

            login_user(client, user.email)
            response = client.get('/profile')
            assert response.status_code == 200
            content = response.data.decode('utf-8')
            assert 'GitHub' in content
            assert 'https://github.com/example_user' in content

    def test_update_profile(self, client, app, auth_user):
        """Test updating profile."""
        with app.app_context():
            user = auth_user()  # Call the function to get fresh user
            login_user(client, user.email)
            
            response = client.post('/profile', data={
                'about_me': 'Updated bio information'
            }, follow_redirects=True)
            
            assert response.status_code == 200
            assert b'Your profile has been updated.' in response.data
            
            # Verify profile was updated
            updated_user = db.session.get(User, user.id)
            assert updated_user.about_me == 'Updated bio information'


class TestAccountDeletion:
    """Test account deletion functionality."""
    
    def test_delete_account_page_requires_login(self, client):
        """Test that delete account page requires login."""
        response = client.get('/delete_account')
        assert response.status_code == 302  # Redirect to login
    
    def test_delete_account_soft_delete_preserves_user_data(self, client, app, auth_user):
        """Test that account deletion uses soft delete to preserve user data for history."""
        with app.app_context():
            user = auth_user()
            user_id = user.id
            user_email = user.email
            
            login_user(client, user.email)
            
            response = client.post('/delete_account', data={
                'confirmation': 'DELETE MY ACCOUNT'
            }, follow_redirects=True)
            
            assert response.status_code == 200
            
            # Verify user was soft deleted (not hard deleted)
            soft_deleted_user = db.session.get(User, user_id)
            assert soft_deleted_user is not None
            assert soft_deleted_user.is_deleted is True
            assert soft_deleted_user.deleted_at is not None
            assert "deleted_" in soft_deleted_user.email  # Email should be anonymized
            assert soft_deleted_user.email != user_email  # Email changed
