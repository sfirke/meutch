"""Data seeding utilities for development and testing environments."""

from app.models import User

def check_and_seed_if_empty():
    """Check if the database is empty and seed it if needed."""
    user_count = User.query.count()
    if user_count == 0:
        print("Database appears empty, seeding with development data...")
        # Import here to avoid circular imports
        from app.cli import _seed_development_data
        from app import db
        
        _seed_development_data()
        db.session.commit()
        print("✅ Auto-seeding completed!")
        return True
    else:
        print(f"Database already has {user_count} users, skipping seeding.")
        return False
