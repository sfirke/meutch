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
from flask.cli import with_appcontext


@click.group()
def seed():
    """Database seeding commands."""
    pass


@seed.command()
@click.option('--env', default='development', help='Environment: development, staging, production')
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
    elif env == 'staging':
        click.echo('⚠️  Staging environment should use production data copy!')
        click.echo('   Staging seeding is not recommended - use production data sync instead.')
        click.echo('   To sync production data: python sync_staging_db.py')
        if not click.confirm('Continue with basic staging seeding anyway?'):
            click.echo('Aborted. Use production data sync for authentic testing.')
            return
        # Create minimal staging setup only
        _seed_staging_data()
    elif env == 'development':
        _seed_development_data()
    else:
        click.echo(f"❌ Unknown environment: {env}")
        click.echo("Available environments: development, staging, production")
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
    from app.models import User, Category, Tag, Circle, Item, LoanRequest, Message
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
                street=f"{100 + i} Test Street",
                city="Testville",
                state="NY", 
                zip_code=f"1000{i}",
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
        {'name': 'Neighborhood Share', 'desc': 'Share with your neighbors'},
        {'name': 'Tech Enthusiasts', 'desc': 'For tech lovers and gadget sharers'},
        {'name': 'Book Club', 'desc': 'Share and discuss books'},
        {'name': 'Outdoor Adventures', 'desc': 'Outdoor gear sharing community'},
        {'name': 'Cooking Circle', 'desc': 'Kitchen tools and recipe sharing'},
    ]
    
    for circle_info in circle_data:
        existing = Circle.query.filter_by(name=circle_info['name']).first()
        if not existing:
            circle = Circle(
                name=circle_info['name'],
                description=circle_info['desc'],
                requires_approval=random.choice([True, False])
            )
            db.session.add(circle)
            db.session.flush()  # Get the ID
            
            # Add random users to circles
            circle_users = random.sample(users, random.randint(3, 7))
            for user in circle_users:
                circle.members.append(user)
            
            circles.append(circle)
            click.echo(f"  ✓ Circle: {circle.name} ({len(circle_users)} members)")
        else:
            circles.append(existing)
            click.echo(f"  ≈ Circle exists: {existing.name} ({len(existing.members)} members)")
    
    # Items (idempotent)
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


def _seed_staging_data():
    """Minimal staging setup - not recommended. Use production data sync instead."""
    from app import db
    from app.models import Category
    
    click.echo('⚠️  Creating minimal staging data (not recommended)...')
    click.echo('   For authentic testing, use: python sync_staging_db.py')
    
    # Only create basic categories - no users or complex data
    _seed_basic_data()
    
    click.echo('   💡 Staging should typically use production data copy for authentic testing')
    click.echo('   💡 Run "python sync_staging_db.py" to sync real production data')


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


if __name__ == '__main__':
    seed()
