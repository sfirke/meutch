#!/usr/bin/env python3
"""
Database seeding utilities for different environments.
"""

import os
import random


class DataSeeder:
    """Base class for data seeding."""
    
    def __init__(self, app_context=None):
        from app import create_app
        self.app = app_context or create_app()
    
    def seed_categories(self):
        """Create basic categories needed for the app."""
        from app.models import Category
        from tests.factories import CategoryFactory
        from app import db
        
        categories = []
        category_names = ['Electronics', 'Books', 'Tools', 'Kitchen', 'Sports', 'Clothing', 'Home & Garden', 'Toys']
        
        with self.app.app_context():
            for name in category_names:
                # Check if category already exists
                existing = Category.query.filter_by(name=name).first()
                if not existing:
                    category = CategoryFactory(name=name)
                    categories.append(category)
                    print(f"Created category: {name}")
                else:
                    categories.append(existing)
        
        return categories
    
    def seed_tags(self):
        """Create basic tags for items."""
        from app.models import Tag
        from tests.factories import TagFactory
        from app import db
        
        tags = []
        tag_names = ['vintage', 'electronics', 'outdoor', 'indoor', 'eco-friendly', 'handmade', 'collectible', 'seasonal']
        
        with self.app.app_context():
            for name in tag_names:
                # Check if tag already exists
                existing = Tag.query.filter_by(name=name).first()
                if not existing:
                    tag = TagFactory(name=name)
                    tags.append(tag)
                    print(f"Created tag: {name}")
                else:
                    tags.append(existing)
        
        return tags


class DevelopmentSeeder(DataSeeder):
    """Seeder for development environment with rich test data."""
    
    def seed_all(self):
        """Seed development database with comprehensive test data."""
        with self.app.app_context():
            print("🌱 Seeding development database...")
            
            # Basic data
            categories = self.seed_categories()
            tags = self.seed_tags()
            
            # Development-specific data
            users = self.seed_dev_users()
            circles = self.seed_dev_circles(users)
            items = self.seed_dev_items(categories, tags, users)
            loan_requests = self.seed_dev_loan_requests(items, users)
            messages = self.seed_dev_messages(users, loan_requests)
            
            db.session.commit()
            
            print("\n✅ Development seeding completed!")
            self.print_summary(categories, tags, users, circles, items, loan_requests, messages)
    
    def seed_dev_users(self):
        """Create development users with predictable emails."""
        users = []
        
        # Create admin user
        admin = UserFactory(
            email="admin@meutch.com",
            first_name="Admin",
            last_name="User",
            street="123 Admin Street",
            city="AdminCity",
            state="NY",
            zip_code="10001",
            email_confirmed=True
        )
        admin.set_password("admin123")
        users.append(admin)
        print(f"Created admin user: {admin.email}")
        
        # Create test users
        for i in range(10):
            user = UserFactory(
                email=f"user{i+1}@example.com",
                first_name=f"User{i+1}",
                last_name="Test",
                street=f"{100 + i} Test Street",
                city="Testville",
                state="NY",
                zip_code=f"1000{i}",
                email_confirmed=True
            )
            user.set_password("password123")
            users.append(user)
            print(f"Created user: {user.email}")
        
        return users
    
    def seed_dev_circles(self, users):
        """Create development circles."""
        circles = []
        circle_data = [
            {'name': 'Neighborhood Share', 'desc': 'Share with your neighbors', 'approval': False},
            {'name': 'Tech Enthusiasts', 'desc': 'For tech lovers and gadget sharers', 'approval': True},
            {'name': 'Book Club', 'desc': 'Share and discuss books', 'approval': False},
            {'name': 'Outdoor Adventures', 'desc': 'Outdoor gear sharing community', 'approval': True},
            {'name': 'Cooking Circle', 'desc': 'Kitchen tools and recipe sharing', 'approval': False},
        ]
        
        for circle_info in circle_data:
            circle = CircleFactory(
                name=circle_info['name'],
                description=circle_info['desc'],
                requires_approval=circle_info['approval']
            )
            circles.append(circle)
            
            # Add random users to circles
            circle_users = random.sample(users, random.randint(3, 7))
            for user in circle_users:
                circle.members.append(user)
            
            print(f"Created circle: {circle.name} with {len(circle_users)} members")
        
        return circles
    
    def seed_dev_items(self, categories, tags, users):
        """Create development items with realistic data."""
        items = []
        item_examples = [
            {'name': 'Power Drill', 'description': 'Cordless power drill with bits included', 'category': 'Tools'},
            {'name': 'Bread Maker', 'description': 'Automatic bread making machine, barely used', 'category': 'Kitchen'},
            {'name': 'Python Programming Book', 'description': 'Learn Python the Hard Way - excellent condition', 'category': 'Books'},
            {'name': 'Tennis Racket', 'description': 'Wilson tennis racket, good condition', 'category': 'Sports'},
            {'name': 'Laptop Stand', 'description': 'Adjustable aluminum laptop stand', 'category': 'Electronics'},
            {'name': 'Garden Hose', 'description': '50ft expandable garden hose with nozzle', 'category': 'Home & Garden'},
            {'name': 'Board Game Collection', 'description': 'Various board games for family fun', 'category': 'Toys'},
            {'name': 'Winter Jacket', 'description': 'Large size winter jacket, barely used', 'category': 'Clothing'},
            {'name': 'Camping Tent', 'description': '4-person camping tent with rainfly', 'category': 'Sports'},
            {'name': 'Stand Mixer', 'description': 'KitchenAid stand mixer with attachments', 'category': 'Kitchen'},
        ]
        
        category_map = {cat.name: cat for cat in categories}
        
        for item_data in item_examples:
            category = category_map.get(item_data['category'], categories[0])
            owner = random.choice(users)
            
            item = ItemFactory(
                name=item_data['name'],
                description=item_data['description'],
                category=category,
                owner=owner,
                available=random.choice([True, True, True, False])  # 75% available
            )
            
            # Add random tags
            item_tags = random.sample(tags, random.randint(1, 3))
            for tag in item_tags:
                item.tags.append(tag)
            
            items.append(item)
            print(f"Created item: {item.name} (owner: {owner.email})")
        
        return items
    
    def seed_dev_loan_requests(self, items, users):
        """Create development loan requests."""
        loan_requests = []
        
        for i in range(7):
            available_items = [item for item in items if item.available]
            if available_items:
                item = random.choice(available_items)
                potential_borrowers = [u for u in users if u != item.owner]
                if potential_borrowers:
                    borrower = random.choice(potential_borrowers)
                    
                    messages = [
                        f"Hi, I'd like to borrow your {item.name} for the weekend.",
                        f"Could I borrow your {item.name}? I'll take good care of it!",
                        f"I need a {item.name} for a project. Can I borrow yours?",
                        f"Would you be willing to lend me your {item.name}?",
                    ]
                    
                    loan_request = LoanRequestFactory(
                        item=item,
                        borrower=borrower,
                        message=random.choice(messages),
                        status=random.choice(['pending', 'pending', 'approved', 'rejected'])  # More pending
                    )
                    loan_requests.append(loan_request)
                    print(f"Created loan request: {borrower.email} wants {item.name}")
        
        return loan_requests
    
    def seed_dev_messages(self, users, loan_requests):
        """Create development messages."""
        messages = []
        
        # Messages related to loan requests
        for loan_request in loan_requests[:3]:
            message = MessageFactory(
                sender=loan_request.item.owner,
                recipient=loan_request.borrower,
                body=f"Thanks for your interest in my {loan_request.item.name}! When do you need it?",
                loan_request=loan_request,
                is_read=random.choice([True, False])
            )
            messages.append(message)
        
        # General messages
        for i in range(5):
            sender = random.choice(users)
            recipient = random.choice([u for u in users if u != sender])
            
            general_messages = [
                "Hi! I saw you have some great items. Do you live nearby?",
                "Thanks for letting me borrow that tool last week!",
                "I'm looking for a specific item. Do you know anyone who might have one?",
                "Great to meet a neighbor through this app!",
                "Would you be interested in forming a sharing circle?",
            ]
            
            message = MessageFactory(
                sender=sender,
                recipient=recipient,
                body=random.choice(general_messages),
                is_read=random.choice([True, False])
            )
            messages.append(message)
            print(f"Created message: {sender.email} -> {recipient.email}")
        
        return messages
    
    def print_summary(self, categories, tags, users, circles, items, loan_requests, messages):
        """Print summary of created data."""
        print("\n📊 Development Data Summary:")
        print(f"   Categories: {len(categories)}")
        print(f"   Tags: {len(tags)}")
        print(f"   Users: {len(users)} (including admin@meutch.com)")
        print(f"   Circles: {len(circles)}")
        print(f"   Items: {len(items)}")
        print(f"   Loan Requests: {len(loan_requests)}")
        print(f"   Messages: {len(messages)}")
        print("\n🔑 Admin credentials: admin@meutch.com / admin123")
        print("🔑 User credentials: user1@example.com / password123 (through user10@example.com)")


class ProductionSeeder(DataSeeder):
    """Seeder for production environment with minimal essential data."""
    
    def seed_essential(self):
        """Seed production database with only essential data."""
        with self.app.app_context():
            print("🌱 Seeding production database with essential data...")
            
            # Only create categories and tags - no test users or items
            categories = self.seed_categories()
            tags = self.seed_tags()
            
            db.session.commit()
            
            print("\n✅ Production seeding completed!")
            print(f"📊 Created {len(categories)} categories and {len(tags)} tags")
            print("ℹ️  No test users or items created for production")


class TestSeeder(DataSeeder):
    """Seeder for test environment with minimal, predictable data."""
    
    def seed_test_data(self):
        """Seed test database with minimal, predictable test data."""
        with self.app.app_context():
            print("🌱 Seeding test database...")
            
            # Create minimal test data
            category = CategoryFactory(name='Test Category')
            tag = TagFactory(name='test-tag')
            
            user = UserFactory(
                email='test@example.com',
                first_name='Test',
                last_name='User',
                email_confirmed=True
            )
            user.set_password('testpass')
            
            item = ItemFactory(
                name='Test Item',
                description='A test item for testing',
                category=category,
                owner=user,
                available=True
            )
            
            db.session.commit()
            
            print("✅ Test seeding completed!")
            print("📊 Created 1 user, 1 item, 1 category, 1 tag")


def seed_for_environment(env=None):
    """Seed database based on environment."""
    if env is None:
        env = os.environ.get('FLASK_ENV', 'development')
    
    if env == 'production':
        seeder = ProductionSeeder()
        seeder.seed_essential()
    elif env == 'testing':
        seeder = TestSeeder()
        seeder.seed_test_data()
    else:  # development
        seeder = DevelopmentSeeder()
        seeder.seed_all()


if __name__ == '__main__':
    import sys
    env = sys.argv[1] if len(sys.argv) > 1 else None
    seed_for_environment(env)
