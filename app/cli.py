#!/usr/bin/env python3
"""Database seeding script with CLI interface.

Provides Flask CLI commands for seeding and managing database data:
- flask seed data --env [development|production]
- flask seed clear
- flask seed status

Development environment creates rich test data with users, items, circles, etc.
Production environment only creates basic categories and tags.
"""

import click
import os
import random
from datetime import datetime
from flask.cli import with_appcontext


@click.group()
def seed():
    """Database seeding commands."""
    pass


@seed.command()
@click.option('--env', default='development', help='Environment: development, production')
@with_appcontext
def data(env):
    """Seed database with data for specified environment."""
    from app import db
    
    click.echo(f"🌱 Seeding {env} database...")
    
    if env == 'production':
        if not click.confirm('⚠️  Are you sure you want to seed PRODUCTION?'):
            click.echo('Aborted.')
            return
        # Only create basic categories for production
        _seed_basic_data()
    elif env == 'development':
        _seed_development_data()
    else:
        click.echo(f"❌ Unknown environment: {env}")
        click.echo("Available environments: development, production")
        click.echo("💡 For staging: use production data sync with sync_staging_db.py")
        return
    
    db.session.commit()
    click.echo(f"✅ {env.title()} seeding completed!")


@seed.command()
@with_appcontext
def clear():
    """Clear all data from database (keep tables)."""
    from app import db
    from app.models import (
        User, Item, Category, Circle, Tag, LoanRequest, Message, 
        Feedback, CircleJoinRequest
    )
    
    if os.environ.get('FLASK_ENV') == 'production':
        click.echo('❌ Cannot clear production database!')
        return
    
    # Get database information for warning
    db_info = _get_database_info()
    
    if not click.confirm(f'⚠️  This will DELETE ALL DATA from database: {db_info}. Continue?'):
        click.echo('Aborted.')
        return
    
    click.echo('🗑️  Clearing all data...')
    
    # Clear many-to-many association tables first
    click.echo('  Clearing association tables...')
    db.session.execute(db.text('DELETE FROM item_tags;'))
    db.session.execute(db.text('DELETE FROM circle_members;'))
    
    # Delete records in correct order to handle all foreign key constraints
    # Order: dependent records first, then their dependencies
    models_to_clear = [
        ('Feedback', Feedback),                    # depends on: loan_request, user
        ('Circle Join Requests', CircleJoinRequest), # depends on: circle, user
        ('Messages', Message),                     # depends on: user, item, loan_request
        ('Loan Requests', LoanRequest),           # depends on: item, user
        ('Items', Item),                          # depends on: user, category
        ('Circles', Circle),                      # depends on: users (via circle_members)
        ('Tags', Tag),                           # depends on: items (via item_tags)
        ('Categories', Category),                # depends on: items
        ('Users', User),                         # base table
    ]
    
    for name, model in models_to_clear:
        count = db.session.query(model).count()
        if count > 0:
            db.session.query(model).delete()
            click.echo(f'  Cleared {count} {name}')
    
    db.session.commit()
    click.echo('✅ Database cleared!')


@seed.command()
@with_appcontext
def status():
    """Show database record counts."""
    from app import db
    from app.models import (
        User, Item, Category, Circle, Tag, LoanRequest, Message, 
        Feedback, CircleJoinRequest
    )
    
    models = [
        ('Users', User),
        ('Items', Item), 
        ('Categories', Category),
        ('Circles', Circle),
        ('Tags', Tag),
        ('Loan Requests', LoanRequest),
        ('Messages', Message),
        ('Feedback', Feedback),
        ('Circle Join Requests', CircleJoinRequest),
    ]
    
    # Get database information
    db_info = _get_database_info()
    
    click.echo('📊 Database Status:')
    click.echo(f'🔍 Database: {db_info}')
    click.echo('─' * 40)
    
    total = 0
    for name, model in models:
        try:
            count = db.session.query(model).count()
            click.echo(f'{name:20}: {count:5} records')
            total += count
        except Exception as e:
            click.echo(f'{name:20}: Error - {str(e)}')
    
    click.echo('─' * 40)
    click.echo(f'{"Total":15}: {total:5} records')


def _seed_basic_data():
    """Seed basic categories only for production (idempotent)."""
    from app import db
    from app.models import Category
    
    categories = ['Electronics', 'Books', 'Tools', 'Kitchen', 'Sports', 'Clothing', 'Home & Garden', 'Toys']
    
    for name in categories:
        existing = Category.query.filter_by(name=name).first()
        if not existing:
            category = Category(name=name)
            db.session.add(category)
            click.echo(f"  ✓ Category: {name}")
        else:
            click.echo(f"  ≈ Category exists: {name}")


def _seed_development_data():
    """Seed rich development data (idempotent)."""
    from app import db
    from app.models import User, Category, Tag, Circle, Item, LoanRequest, Message, UserWebLink
    import random
    
    click.echo('Creating development data...')
    
    # Categories (idempotent)
    categories = []
    category_names = ['Electronics', 'Books', 'Tools', 'Kitchen', 'Sports', 'Clothing', 'Home & Garden', 'Toys']
    for name in category_names:
        existing = Category.query.filter_by(name=name).first()
        if not existing:
            cat = Category(name=name)
            db.session.add(cat)
            db.session.flush()  # Get the ID
            categories.append(cat)
            click.echo(f"  ✓ Category: {name}")
        else:
            categories.append(existing)
            click.echo(f"  ≈ Category exists: {name}")
    
    # Tags (idempotent)
    tags = []
    tag_names = ['vintage', 'electronics', 'outdoor', 'indoor', 'eco-friendly', 'handmade', 'collectible', 'seasonal']
    for name in tag_names:
        existing = Tag.query.filter_by(name=name).first()
        if not existing:
            tag = Tag(name=name)
            db.session.add(tag)
            db.session.flush()  # Get the ID
            tags.append(tag)
            click.echo(f"  ✓ Tag: {name}")
        else:
            tags.append(existing)
            click.echo(f"  ≈ Tag exists: {name}")
    
    # Users (idempotent)
    users = []
    existing_users = User.query.filter(User.email.like('user%@example.com')).all()
    existing_emails = {user.email for user in existing_users}
    
    for i in range(12):
        email = f"user{i+1}@example.com"
        if email not in existing_emails:
            user = User(
                email=email,
                first_name=f"User{i+1}",
                last_name="Test",
                latitude=40.7128 + (i * 0.01),  # Spread users around NYC area
                longitude=-74.0060 + (i * 0.01),
                email_confirmed=True
            )
            user.set_password("password123")
            db.session.add(user)
            db.session.flush()  # Get the ID
            users.append(user)
            click.echo(f"  ✓ User: {user.email}")
        else:
            existing_user = User.query.filter_by(email=email).first()
            users.append(existing_user)
            click.echo(f"  ≈ User exists: {email}")
    
    # Circles (idempotent)
    circles = []
    circle_data = [
        # Public circles for browsing
        {'name': 'Neighborhood Share', 'desc': 'Share with your neighbors', 'lat': 40.7128, 'lon': -74.0060, 'visibility': 'public'},  # Manhattan
        {'name': 'Tech Enthusiasts', 'desc': 'For tech lovers and gadget sharers', 'lat': 40.7589, 'lon': -73.9851, 'visibility': 'public'},  # Upper West Side
        {'name': 'Book Club', 'desc': 'Share and discuss books', 'lat': 40.7282, 'lon': -73.7949, 'visibility': 'public'},  # Queens
        {'name': 'Outdoor Adventures', 'desc': 'Outdoor gear sharing community', 'lat': 40.6782, 'lon': -73.9442, 'visibility': 'public'},  # Brooklyn
        {'name': 'Cooking Circle', 'desc': 'Kitchen tools and recipe sharing', 'lat': 40.7489, 'lon': -73.9680, 'visibility': 'public'},  # Midtown East
        {'name': 'Gardening Friends', 'desc': 'Share gardening tools and tips', 'lat': 40.7280, 'lon': -74.0020, 'visibility': 'public'},  # Lower Manhattan
        {'name': 'DIY Workshop', 'desc': 'Tools and knowledge for DIY projects', 'lat': 40.7050, 'lon': -73.9970, 'visibility': 'public'},  # Lower East Side
        {'name': 'Sports Equipment Share', 'desc': 'Share sports gear and equipment', 'lat': 40.7580, 'lon': -73.9680, 'visibility': 'public'},  # Upper East Side
        # Public circle with no location set
        {'name': 'Unlocated Public Circle', 'desc': 'A public circle with no location set yet', 'lat': None, 'lon': None, 'visibility': 'public'},
        # Private/unlisted circles
        {'name': 'Family Circle', 'desc': 'Private family lending circle', 'lat': 40.7420, 'lon': -73.9890, 'visibility': 'private'},  # Midtown
        {'name': 'Office Supplies', 'desc': 'Unlisted circle for office equipment', 'lat': 40.7510, 'lon': -73.9930, 'visibility': 'unlisted'},  # Midtown West
    ]
    
    for circle_info in circle_data:
        existing = Circle.query.filter_by(name=circle_info['name']).first()
        if not existing:
            visibility = circle_info['visibility']
            requires_approval = visibility in ['private', 'unlisted']

            circle = Circle(
                name=circle_info['name'],
                description=circle_info['desc'],
                visibility=visibility,
                requires_approval=requires_approval,
                latitude=circle_info['lat'],
                longitude=circle_info['lon']
            )
            db.session.add(circle)
            db.session.flush()  # Get the ID
            
            # Add random users to circles
            circle_users = random.sample(users, random.randint(3, 7))
            for user in circle_users:
                circle.members.append(user)
            
            circles.append(circle)
            location_status = "location set" if circle.is_geocoded else "no location"
            click.echo(f"  ✓ Circle: {circle.name} ({len(circle_users)} members) [visibility={visibility}, {location_status}]")
        else:
            # Circle already exists, skip it
            click.echo(f"  ≈ Circle exists: {existing.name} ({len(existing.members)} members)")
            circles.append(existing)
    
    # Items (idempotent)
    items = []
    item_examples = [
        # Original items
        {'name': 'Power Drill', 'description': 'Cordless power drill with bits included', 'category': 'Tools'},
        {'name': 'Bread Maker', 'description': 'Automatic bread making machine, barely used', 'category': 'Kitchen'},
        {'name': 'Python Programming Book', 'description': 'Learn Python the Hard Way - excellent condition', 'category': 'Books'},
        {'name': 'Tennis Racket', 'description': 'Wilson tennis racket, good condition', 'category': 'Sports'},
        {'name': 'Laptop Stand', 'description': 'Adjustable aluminum laptop stand', 'category': 'Electronics'},
        {'name': 'Garden Hose', 'description': '50ft expandable garden hose with nozzle', 'category': 'Home & Garden'},
        {'name': 'Board Game Collection', 'description': 'Various board games for family fun', 'category': 'Toys'},
        {'name': 'Winter Jacket', 'description': 'Large size winter jacket, barely used', 'category': 'Clothing'},
        
        # Additional Electronics
        {'name': 'Bluetooth Speaker', 'description': 'Portable wireless speaker with great sound', 'category': 'Electronics'},
        {'name': 'iPad Mini', 'description': '2021 iPad Mini, excellent condition with case', 'category': 'Electronics'},
        {'name': 'Digital Camera', 'description': 'Canon DSLR camera with lens kit', 'category': 'Electronics'},
        {'name': 'Gaming Headset', 'description': 'Wireless gaming headset with noise cancellation', 'category': 'Electronics'},
        {'name': 'Tablet Stand', 'description': 'Adjustable tablet stand for desk use', 'category': 'Electronics'},
        {'name': 'Phone Charger', 'description': 'Fast charging cable and wall adapter', 'category': 'Electronics'},
        
        # Additional Books
        {'name': 'JavaScript Guide', 'description': 'Complete guide to modern JavaScript', 'category': 'Books'},
        {'name': 'Cooking for Beginners', 'description': 'Learn basic cooking techniques', 'category': 'Books'},
        {'name': 'The Great Gatsby', 'description': 'Classic American literature', 'category': 'Books'},
        {'name': 'Yoga for Everyone', 'description': 'Beginner-friendly yoga instruction book', 'category': 'Books'},
        {'name': 'Home Repair Manual', 'description': 'DIY guide for common home repairs', 'category': 'Books'},
        
        # Additional Tools
        {'name': 'Hammer Set', 'description': 'Set of 3 hammers for different tasks', 'category': 'Tools'},
        {'name': 'Screwdriver Kit', 'description': 'Complete set of screwdrivers', 'category': 'Tools'},
        {'name': 'Measuring Tape', 'description': '25ft measuring tape with magnetic tip', 'category': 'Tools'},
        {'name': 'Level', 'description': '24-inch bubble level for precise measurements', 'category': 'Tools'},
        {'name': 'Socket Wrench Set', 'description': 'Comprehensive socket wrench set', 'category': 'Tools'},
        
        # Additional Kitchen
        {'name': 'Stand Mixer', 'description': 'KitchenAid stand mixer, red color', 'category': 'Kitchen'},
        {'name': 'Food Processor', 'description': 'Large capacity food processor', 'category': 'Kitchen'},
        {'name': 'Cast Iron Skillet', 'description': '12-inch seasoned cast iron skillet', 'category': 'Kitchen'},
        {'name': 'Pressure Cooker', 'description': 'Electric pressure cooker, 6-quart', 'category': 'Kitchen'},
        {'name': 'Knife Set', 'description': 'Professional chef knife set with block', 'category': 'Kitchen'},
        
        # Additional Sports
        {'name': 'Basketball', 'description': 'Official size basketball, good condition', 'category': 'Sports'},
        {'name': 'Yoga Mat', 'description': 'Non-slip yoga mat with carrying strap', 'category': 'Sports'},
        {'name': 'Bicycle Helmet', 'description': 'Safety helmet for cycling, medium size', 'category': 'Sports'},
        {'name': 'Swimming Goggles', 'description': 'Anti-fog swimming goggles', 'category': 'Sports'},
        {'name': 'Dumbbells', 'description': 'Set of adjustable dumbbells, 5-50 lbs', 'category': 'Sports'},
        
        # Additional Home & Garden
        {'name': 'Lawn Mower', 'description': 'Electric lawn mower, works perfectly', 'category': 'Home & Garden'},
        {'name': 'Plant Pots', 'description': 'Set of ceramic plant pots, various sizes', 'category': 'Home & Garden'},
        {'name': 'Watering Can', 'description': '2-gallon watering can with sprinkler head', 'category': 'Home & Garden'},
        {'name': 'Garden Tools', 'description': 'Set of basic gardening tools', 'category': 'Home & Garden'},
        {'name': 'Outdoor Table', 'description': 'Weather-resistant patio table', 'category': 'Home & Garden'},
        
        # Additional Toys
        {'name': 'LEGO Set', 'description': 'Large LEGO building set, complete', 'category': 'Toys'},
        {'name': 'Puzzle Collection', 'description': '1000-piece jigsaw puzzles, various themes', 'category': 'Toys'},
        {'name': 'Action Figures', 'description': 'Collection of superhero action figures', 'category': 'Toys'},
        {'name': 'Art Supplies', 'description': 'Complete art kit with paints and brushes', 'category': 'Toys'},
        {'name': 'Remote Control Car', 'description': 'Fast RC car with rechargeable battery', 'category': 'Toys'},
        
        # Additional Clothing
        {'name': 'Running Shoes', 'description': 'Nike running shoes, size 10, barely used', 'category': 'Clothing'},
        {'name': 'Formal Dress', 'description': 'Black evening dress, size medium', 'category': 'Clothing'},
        {'name': 'Leather Jacket', 'description': 'Genuine leather jacket, classic style', 'category': 'Clothing'},
        {'name': 'Hiking Boots', 'description': 'Waterproof hiking boots, size 9', 'category': 'Clothing'},
        {'name': 'Summer Hat', 'description': 'Sun protection hat for outdoor activities', 'category': 'Clothing'},
    ]
    
    category_map = {cat.name: cat for cat in categories}
    
    for item_data in item_examples:
        existing = Item.query.filter_by(name=item_data['name']).first()
        if not existing:
            category = category_map.get(item_data['category'], categories[0])
            owner = random.choice(users)
            
            item = Item(
                name=item_data['name'],
                description=item_data['description'],
                category=category,
                owner=owner,
                available=random.choice([True, True, True, False])  # 75% available
            )
            db.session.add(item)
            db.session.flush()  # Get the ID
            
            # Add random tags
            item_tags = random.sample(tags, random.randint(1, 3))
            for tag in item_tags:
                item.tags.append(tag)
            
            items.append(item)
            click.echo(f"  ✓ Item: {item.name} (owner: {owner.email})")
        else:
            items.append(existing)
            click.echo(f"  ≈ Item exists: {existing.name} (owner: {existing.owner.email})")
    
    # Get all existing items for loan requests and messages
    all_items = Item.query.all()
    all_users = User.query.all()
    
    # Loan requests (create a few if none exist)
    existing_loan_requests = LoanRequest.query.count()
    if existing_loan_requests < 5:
        requests_to_create = 5 - existing_loan_requests
        for i in range(requests_to_create):
            available_items = [item for item in all_items if item.available]
            if available_items:
                item = random.choice(available_items)
                potential_borrowers = [u for u in all_users if u != item.owner]
                if potential_borrowers:
                    borrower = random.choice(potential_borrowers)
                    
                    # Check if this combination already exists
                    existing_request = LoanRequest.query.filter_by(
                        item=item, borrower=borrower
                    ).first()
                    
                    if not existing_request:
                        from datetime import date, timedelta
                        
                        # Generate realistic loan dates
                        start_date = date.today() + timedelta(days=random.randint(1, 14))
                        end_date = start_date + timedelta(days=random.randint(1, 30))
                        
                        loan_request = LoanRequest(
                            item=item,
                            borrower=borrower,
                            start_date=start_date,
                            end_date=end_date,
                            status=random.choice(['pending', 'approved', 'rejected'])
                        )
                        db.session.add(loan_request)
                        db.session.flush()  # Ensure the loan request is persisted
                        click.echo(f"  ✓ Loan request: {borrower.email} wants {item.name}")
    else:
        click.echo(f"  ≈ Loan requests exist: {existing_loan_requests} records")
    
    # Messages (create a few if none exist)
    existing_messages = Message.query.count()
    if existing_messages < 5:
        messages_to_create = 5 - existing_messages
        for i in range(messages_to_create):
            sender = random.choice(all_users)
            recipient = random.choice([u for u in all_users if u != sender])
            item = random.choice(all_items)  # Messages must be associated with an item
            
            message = Message(
                sender=sender,
                recipient=recipient,
                item=item,  # Required field
                body=f"Hi {recipient.first_name}, I'm interested in your {item.name}. Is it still available?",
                is_read=random.choice([True, False])
            )
            db.session.add(message)
            db.session.flush()  # Ensure the message is persisted
            click.echo(f"  ✓ Message: {sender.email} -> {recipient.email} about {item.name}")
    else:
        click.echo(f"  ≈ Messages exist: {existing_messages} records")

    # Web Links (add some sample social links for development users)
    existing_web_links = UserWebLink.query.count()
    if existing_web_links < 10:
        # Sample web links for some users
        web_link_examples = [
            {'email': 'user1@example.com', 'platform': 'instagram', 'url': 'https://instagram.com/user1_meutch'},
            {'email': 'user1@example.com', 'platform': 'linkedin', 'url': 'https://linkedin.com/in/user1-meutch'},
            {'email': 'user2@example.com', 'platform': 'facebook', 'url': 'https://facebook.com/user2.meutch'},
            {'email': 'user2@example.com', 'platform': 'blog', 'url': 'https://user2blog.wordpress.com'},
            {'email': 'user3@example.com', 'platform': 'x', 'url': 'https://x.com/user3_meutch'},
            {'email': 'user3@example.com', 'platform': 'website', 'url': 'https://user3.dev'},
            {'email': 'user4@example.com', 'platform': 'mastodon', 'url': 'https://mastodon.social/@user4'},
            {'email': 'user4@example.com', 'platform': 'threads', 'url': 'https://threads.net/@user4_meutch'},
            {'email': 'user5@example.com', 'platform': 'tiktok', 'url': 'https://tiktok.com/@user5_meutch'},
            {'email': 'user5@example.com', 'platform': 'bluesky', 'url': 'https://bsky.app/profile/user5.bsky.social'},
            {'email': 'user6@example.com', 'platform': 'website', 'url': 'https://user6portfolio.dev'},
            {'email': 'user6@example.com', 'platform': 'other', 'url': 'https://dribbble.com/user6', 'custom_name': 'Dribbble'},
        ]
        
        user_emails_map = {user.email: user for user in all_users}
        display_order_counters = {}
        
        for link_data in web_link_examples:
            user = user_emails_map.get(link_data['email'])
            if user:
                # Track display order per user
                if user.id not in display_order_counters:
                    display_order_counters[user.id] = 1
                else:
                    display_order_counters[user.id] += 1
                
                # Check if this link already exists
                existing_link = UserWebLink.query.filter_by(
                    user_id=user.id,
                    display_order=display_order_counters[user.id]
                ).first()
                
                if not existing_link and display_order_counters[user.id] <= 5:
                    web_link = UserWebLink(
                        user_id=user.id,
                        platform_type=link_data['platform'],
                        platform_name=link_data.get('custom_name'),
                        url=link_data['url'],
                        display_order=display_order_counters[user.id]
                    )
                    db.session.add(web_link)
                    db.session.flush()
                    click.echo(f"  ✓ Web link: {user.email} -> {link_data['platform']} ({link_data['url']})")
    else:
        click.echo(f"  ≈ Web links exist: {existing_web_links} records")


def _get_database_info():
    """Get readable database information for user display."""
    import os
    from urllib.parse import urlparse
    
    db_url = os.environ.get('DATABASE_URL', '')
    
    if not db_url:
        return "Unknown database"
    
    try:
        parsed = urlparse(db_url)
        
        # Handle different database types
        if parsed.scheme == 'sqlite':
            if db_url == 'sqlite:///:memory:':
                return "SQLite (in-memory)"
            else:
                # Extract filename from path
                path = parsed.path
                if path.startswith('/'):
                    path = path[1:]  # Remove leading slash
                return f"SQLite ({path or 'local file'})"
        
        elif parsed.scheme in ['postgresql', 'postgres']:
            host = parsed.hostname or 'localhost'
            port = parsed.port or 5432
            database = parsed.path.lstrip('/') if parsed.path else 'unknown'
            
            # Identify common setups
            if host == 'localhost' and port == 5433:
                return f"PostgreSQL (Local Docker - {database})"
            elif host == 'localhost':
                return f"PostgreSQL (Local - {database})"
            elif 'digitalocean' in host or 'db.ondigitalocean.com' in host:
                return f"PostgreSQL (DigitalOcean Production - {database})"
            else:
                return f"PostgreSQL ({host}:{port} - {database})"
        
        else:
            # Generic fallback
            host = parsed.hostname or 'localhost'
            database = parsed.path.lstrip('/') if parsed.path else 'unknown'
            return f"{parsed.scheme.upper()} ({host} - {database})"
    
    except Exception:
        # If parsing fails, show a safe fallback
        if 'localhost' in db_url:
            return "Local database"
        elif 'digitalocean' in db_url:
            return "DigitalOcean Production database"
        else:
            return "Remote database"


def check_loan_reminders_logic():
    """
    Core logic for checking and sending loan reminder emails.
    Extracted as a separate function so it can be called from both
    CLI and HTTP endpoint (the latter doesn't currently exist).
    
    Returns a dict with statistics about emails sent.
    """
    from app import db
    from app.models import LoanRequest
    from app.utils.email import (
        send_loan_due_soon_email,
        send_loan_due_today_borrower_email,
        send_loan_due_today_owner_email,
        send_loan_overdue_borrower_email,
        send_loan_overdue_owner_email
    )
    from datetime import date, datetime, UTC
    
    today = date.today()
    
    # Get all approved loans
    approved_loans = LoanRequest.query.filter_by(status='approved').all()
    
    stats = {
        'total_loans': len(approved_loans),
        'due_soon': 0,
        'due_today': 0,
        'overdue': 0,
        'skipped': 0,
        'errors': []
    }
    
    if not approved_loans:
        return stats
    
    for loan in approved_loans:
        days_until = (loan.end_date - today).days
        
        # 1. Check for 3-day reminders
        if days_until == 3 and not loan.due_soon_reminder_sent:
            try:
                if send_loan_due_soon_email(loan):
                    loan.due_soon_reminder_sent = datetime.now(UTC)
                    db.session.commit()
                    stats['due_soon'] += 1
                else:
                    stats['errors'].append(f'Failed to send 3-day reminder for loan {loan.id}')
            except Exception as e:
                stats['errors'].append(f'Error sending 3-day reminder for loan {loan.id}: {str(e)}')
                db.session.rollback()
        
        # 2. Check for due date reminders
        elif days_until == 0 and not loan.due_date_reminder_sent:
            try:
                borrower_sent = send_loan_due_today_borrower_email(loan)
                owner_sent = send_loan_due_today_owner_email(loan)
                
                if borrower_sent or owner_sent:
                    loan.due_date_reminder_sent = datetime.now(UTC)
                    db.session.commit()
                    stats['due_today'] += 1
                else:
                    stats['errors'].append(f'Failed to send due date reminders for loan {loan.id}')
            except Exception as e:
                stats['errors'].append(f'Error sending due date reminders for loan {loan.id}: {str(e)}')
                db.session.rollback()
        
        # 3. Check for overdue reminders
        elif days_until < 0:
            days_overdue = abs(days_until)
            
            # Only send on specific days: 1, 3, 7, 14
            if days_overdue not in [1, 3, 7, 14]:
                continue
            
            # Check if we've already sent a reminder today
            if loan.last_overdue_reminder_sent:
                # Ensure last_overdue_reminder_sent is timezone-aware for comparison
                last_sent_utc = loan.last_overdue_reminder_sent.replace(tzinfo=UTC) if loan.last_overdue_reminder_sent.tzinfo is None else loan.last_overdue_reminder_sent
                if last_sent_utc.date() == today:
                    stats['skipped'] += 1
                    continue
            
            # Don't send more than 4 overdue reminders
            if loan.overdue_reminder_count >= 4:
                stats['skipped'] += 1
                continue
            
            try:
                borrower_sent = send_loan_overdue_borrower_email(loan, days_overdue)
                owner_sent = send_loan_overdue_owner_email(loan, days_overdue)
                
                if borrower_sent or owner_sent:
                    loan.last_overdue_reminder_sent = datetime.now(UTC)
                    loan.overdue_reminder_count += 1
                    db.session.commit()
                    stats['overdue'] += 1
                else:
                    stats['errors'].append(f'Failed to send overdue reminders for loan {loan.id}')
            except Exception as e:
                stats['errors'].append(f'Error sending overdue reminders for loan {loan.id}: {str(e)}')
                db.session.rollback()
    
    return stats


@click.command()
@with_appcontext
def check_loan_reminders():
    """Check and send loan reminder emails (3-day, due date, overdue)."""
    click.echo('🔔 Checking loan reminders...')
    
    stats = check_loan_reminders_logic()
    
    if stats['total_loans'] == 0:
        click.echo('  No approved loans found.')
    else:
        click.echo(f'  Found {stats["total_loans"]} approved loan(s)')
        
        # Print any errors
        for error in stats['errors']:
            click.echo(f'    ⚠ {error}')
    
    click.echo('\n📊 Summary:')
    click.echo(f'  • 3-day reminders sent: {stats["due_soon"]}')
    click.echo(f'  • Due date reminders sent: {stats["due_today"]}')
    click.echo(f'  • Overdue reminders sent: {stats["overdue"]}')
    click.echo(f'  • Skipped (already sent): {stats["skipped"]}')
    if stats['errors']:
        click.echo(f'  • Errors: {len(stats["errors"])}')
    click.echo('✅ Done!')


if __name__ == '__main__':
    seed()
