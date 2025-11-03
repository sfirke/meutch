import uuid
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import func
from datetime import datetime, UTC
from app import db
from flask_login import UserMixin
from flask import url_for
from werkzeug.security import generate_password_hash, check_password_hash
import secrets

# Association table for many-to-many relationship between Users and Circles
circle_members = db.Table('circle_members',
    db.Column('user_id', UUID(as_uuid=True), db.ForeignKey('users.id'), primary_key=True),
    db.Column('circle_id', UUID(as_uuid=True), db.ForeignKey('circle.id'), primary_key=True),
    db.Column('joined_at', db.DateTime, default=func.now()),
    db.Column('is_admin', db.Boolean, default=False)
)

item_tags = db.Table('item_tags',
    db.Column('item_id', UUID(as_uuid=True), db.ForeignKey('item.id'), primary_key=True),
    db.Column('tag_id', UUID(as_uuid=True), db.ForeignKey('tag.id'), primary_key=True)
)

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    about_me = db.Column(db.Text, default='')
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    geocoded_at = db.Column(db.DateTime, nullable=True)
    geocoding_failed = db.Column(db.Boolean, default=False, nullable=False)
    profile_image_url = db.Column(db.String(500), nullable=True)
    email_confirmed = db.Column(db.Boolean, default=False, nullable=False)
    email_confirmation_token = db.Column(db.String(128), nullable=True)
    email_confirmation_sent_at = db.Column(db.DateTime, nullable=True)
    password_reset_token = db.Column(db.String(128), nullable=True)
    password_reset_sent_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=func.now())
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)
    email_notifications_enabled = db.Column(db.Boolean, default=True, nullable=False)
    
    @property
    def profile_image(self):
        return self.profile_image_url or url_for('static', filename='img/generic_user_avatar.png')

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    @property
    def is_geocoded(self):
        """Returns True if user has valid latitude and longitude"""
        return self.latitude is not None and self.longitude is not None
    
    def distance_to(self, other_user):
        """Calculate distance in miles to another user using Haversine formula"""
        if not (self.is_geocoded and other_user.is_geocoded):
            return None
        
        from app.utils.geocoding import calculate_distance
        return calculate_distance(self.latitude, self.longitude, other_user.latitude, other_user.longitude)
    
    def can_update_location(self):
        """Check if user can update their location (limited to one successful geolocation per day)"""
        # If no previous geocoding attempt, allow update
        if not self.geocoded_at:
            return True
        
        # If last geocoding failed, allow retry regardless of timing
        if self.geocoding_failed:
            return True
            
        # If last geocoding succeeded, enforce daily limit
        from datetime import timedelta
        # Ensure geocoded_at is timezone-aware for comparison
        geocoded_at_utc = self.geocoded_at.replace(tzinfo=UTC) if self.geocoded_at.tzinfo is None else self.geocoded_at
        time_since_last_successful_update = datetime.now(UTC) - geocoded_at_utc
        return time_since_last_successful_update >= timedelta(days=1)
    
    def get_active_loans_as_borrower(self):
        """Returns items user is currently borrowing"""
        return Item.query.join(LoanRequest).filter(
            LoanRequest.borrower_id == self.id,
            LoanRequest.status == 'approved'
        ).all()

    def get_active_loans_as_owner(self):
        """Returns items user is currently lending"""
        return Item.query.join(LoanRequest).filter(
            Item.owner_id == self.id,
            LoanRequest.status == 'approved'
        ).all()
    
    def generate_confirmation_token(self):
        """Generate a secure token for email confirmation"""
        self.email_confirmation_token = secrets.token_urlsafe(32)
        self.email_confirmation_sent_at = datetime.now(UTC)
        return self.email_confirmation_token
    
    def confirm_email(self, token):
        """Confirm email with the provided token"""
        if self.email_confirmation_token == token:
            self.email_confirmed = True
            self.email_confirmation_token = None
            self.email_confirmation_sent_at = None
            return True
        return False
    
    def is_confirmed(self):
        """Check if email is confirmed"""
        return self.email_confirmed
    
    def generate_password_reset_token(self):
        """Generate a secure token for password reset"""
        self.password_reset_token = secrets.token_urlsafe(32)
        self.password_reset_sent_at = datetime.now(UTC)
        return self.password_reset_token
    
    def reset_password(self, token, new_password):
        """Reset password with the provided token"""
        if self.password_reset_token == token:
            # Check if token is not too old (1 hour)
            if self.password_reset_sent_at:
                from datetime import timedelta
                # Ensure password_reset_sent_at is timezone-aware for comparison
                reset_sent_at_utc = self.password_reset_sent_at.replace(tzinfo=UTC) if self.password_reset_sent_at.tzinfo is None else self.password_reset_sent_at
                token_age = datetime.now(UTC) - reset_sent_at_utc
                if token_age > timedelta(hours=1):
                    return False
            
            self.set_password(new_password)
            self.password_reset_token = None
            self.password_reset_sent_at = None
            return True
        return False

    def set_password(self, password):
        """Set password hash"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check password against hash"""
        return check_password_hash(self.password_hash, password)
    
    def get_outstanding_loans_summary(self):
        """Get summary of outstanding loans for account deletion warning"""
        from datetime import date
        
        # Active loans as borrower
        borrowing = LoanRequest.query.filter_by(
            borrower_id=self.id,
            status='approved'
        ).filter(LoanRequest.end_date >= date.today()).count()
        
        # Active loans as owner
        lending = LoanRequest.query.join(Item).filter(
            Item.owner_id == self.id,
            LoanRequest.status == 'approved'
        ).filter(LoanRequest.end_date >= date.today()).count()
        
        # Pending requests as borrower
        pending_borrowing = LoanRequest.query.filter_by(
            borrower_id=self.id,
            status='pending'
        ).count()
        
        # Pending requests as owner
        pending_lending = LoanRequest.query.join(Item).filter(
            Item.owner_id == self.id,
            LoanRequest.status == 'pending'
        ).count()
        
        return {
            'active_borrowing': borrowing,
            'active_lending': lending,
            'pending_borrowing': pending_borrowing,
            'pending_lending': pending_lending,
            'has_outstanding': borrowing + lending + pending_borrowing + pending_lending > 0
        }

    def delete_account(self):
        """Perform cascading deletion of user account"""
        from app.utils.storage import delete_file
        from app.utils.email import send_account_deletion_email
        
        # Store user info for email before deletion
        user_email = self.email
        user_first_name = self.first_name
        
        # 1. Auto-deny all pending loan requests (but keep the user references)
        # Deny requests FROM this user
        LoanRequest.query.filter_by(
            borrower_id=self.id,
            status='pending'
        ).update({'status': 'canceled'})
        
        # Deny requests TO this user's items
        item_ids = [item.id for item in self.items]
        if item_ids:
            LoanRequest.query.filter(
                LoanRequest.item_id.in_(item_ids),
                LoanRequest.status == 'pending'
            ).update({'status': 'denied'}, synchronize_session=False)
        
        # 2. Handle circles - transfer admin rights if needed
        for circle in self.circles:
            if circle.is_admin(self):
                # Count total admins
                admin_count = db.session.query(circle_members).filter_by(
                    circle_id=circle.id,
                    is_admin=True
                ).count()
                
                if admin_count == 1 and len(circle.members) > 1:
                    # Find earliest non-admin member to promote
                    next_admin_assoc = db.session.query(circle_members).filter(
                        circle_members.c.circle_id == circle.id,
                        circle_members.c.user_id != self.id,
                        circle_members.c.is_admin == False
                    ).order_by(circle_members.c.joined_at).first()
                    
                    if next_admin_assoc:
                        from sqlalchemy import and_
                        stmt = circle_members.update().where(
                            and_(
                                circle_members.c.circle_id == circle.id,
                                circle_members.c.user_id == next_admin_assoc.user_id
                            )
                        ).values(is_admin=True)
                        db.session.execute(stmt)
        
        # Remove from all circles
        self.circles.clear()
        
        # 3. Delete circle join requests
        CircleJoinRequest.query.filter_by(user_id=self.id).delete()
        
        # 4. Delete feedback given by user
        Feedback.query.filter_by(reviewer_id=self.id).delete()
        
        # 5. Handle user's items - check for active loans
        from datetime import date
        for item in self.items[:]:  # Use slice to avoid modifying list during iteration
            # Check if item has active loans
            has_active_loans = LoanRequest.query.filter_by(
                item_id=item.id,
                status='approved'
            ).filter(LoanRequest.end_date >= date.today()).first() is not None
            
            if has_active_loans:
                # Keep item but set owner_id to None (anonymize)
                item.owner_id = None
                # Don't delete image for items with active loans
                # Mark as unavailable for new loans
                item.available = False
            else:
                # Delete item image if exists and no active loans
                if item.image_url:
                    delete_file(item.image_url)
                
                # Delete associated loan requests
                LoanRequest.query.filter_by(item_id=item.id).delete()
                
                # Delete associated messages
                Message.query.filter_by(item_id=item.id).delete()
                
                # Delete the item itself
                db.session.delete(item)
        
        # 6. Delete user's profile image
        if self.profile_image_url:
            delete_file(self.profile_image_url)
        
        # 7. Send deletion confirmation email before deleting user
        try:
            send_account_deletion_email(user_email, user_first_name)
        except Exception as e:
            # Log error but don't fail the deletion if email fails
            print(f"Failed to send deletion confirmation email: {e}")
        
        # 8. Soft delete the user (preserve for message/loan history)
        self.is_deleted = True
        self.deleted_at = datetime.now(UTC)
        self.email = f"deleted_{self.id}@deleted.meutch"  # Anonymize email to allow re-registration
        db.session.commit()

    # Relationships
    items = db.relationship('Item', backref='owner', lazy=True)
    circles = db.relationship('Circle', secondary=circle_members, back_populates='members')
    # Friendships will go here later
    def __repr__(self):
        return f'<User {self.email}>'

class Item(db.Model):
    __tablename__ = 'item'
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    owner_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=False)
    available = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=func.now())
    category_id = db.Column(UUID(as_uuid=True), db.ForeignKey('category.id'), nullable=False)
    loan_requests = db.relationship('LoanRequest', backref='item')
    image_url = db.Column(db.String(500), nullable=True)

    @property
    def image(self):
        return self.image_url or url_for('static', filename='img/default_item_photo.png')
    
    @property
    def current_loan(self):
        return LoanRequest.query.filter_by(
            item_id=self.id,
            status='approved'
        ).order_by(LoanRequest.end_date.desc()).first()

    @property
    def owner_name(self):
        """Returns owner name or 'Deleted User' if owner is None"""
        return self.owner.full_name if self.owner else "Deleted User"

    def __repr__(self):
        return f'<Item {self.name}>'

    
class Circle(db.Model):
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=True)
    visibility = db.Column(db.String(20), default='public')  # public, private, unlisted
    requires_approval = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=func.now())
    image_url = db.Column(db.String(500), nullable=True)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)

    members = db.relationship('User', secondary=circle_members, back_populates='circles')
    
    def __repr__(self):
        return f'<Circle {self.name}>'
    
    def is_admin(self, user):
        member = db.session.query(circle_members).filter_by(
            user_id=user.id,
            circle_id=self.id
        ).first()
        return member and member.is_admin if member else False

    @property
    def image(self):
        return self.image_url or url_for('static', filename='img/default_item_photo.png')
    
    @property
    def is_geocoded(self):
        """Returns True if circle has valid latitude and longitude"""
        return self.latitude is not None and self.longitude is not None
    
    def distance_to_user(self, user):
        """Calculate distance in miles from circle center to a user using Haversine formula"""
        if not (self.is_geocoded and user.is_geocoded):
            return None
        
        from app.utils.geocoding import calculate_distance
        return calculate_distance(self.latitude, self.longitude, user.latitude, user.longitude)
    
class Category(db.Model):
    __tablename__ = 'category'
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True, nullable=False)

    name = db.Column(db.String(50), unique=True, nullable=False, index=True)
    
    items = db.relationship('Item', backref='category', lazy=True)
    
    def __repr__(self):
        return f'<Category {self.name}>'


class Tag(db.Model):
    __tablename__ = 'tag'
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True, nullable=False)
    name = db.Column(db.String(50), unique=True, nullable=False, index=True)
    items = db.relationship('Item', secondary=item_tags, backref=db.backref('tags'))
    
    def __repr__(self):
        return f'<Tag {self.name}>'

class LoanRequest(db.Model):
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True, nullable=False)
    item_id = db.Column(UUID(as_uuid=True), db.ForeignKey('item.id'), nullable=False)
    borrower_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=True)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, approved, canceled, denied, completed
    created_at = db.Column(db.DateTime, default=func.now())
    
    # Email reminder tracking fields
    due_soon_reminder_sent = db.Column(db.DateTime, nullable=True)
    due_date_reminder_sent = db.Column(db.DateTime, nullable=True)
    last_overdue_reminder_sent = db.Column(db.DateTime, nullable=True)
    overdue_reminder_count = db.Column(db.Integer, default=0, nullable=False)

    borrower = db.relationship('User', foreign_keys=[borrower_id], backref='loan_requests')

    @property
    def borrower_name(self):
        """Returns borrower name or 'Deleted User' if borrower is None"""
        return self.borrower.full_name if self.borrower else "Deleted User"
    
    def days_until_due(self):
        """Returns number of days until due date (negative if overdue)"""
        from datetime import date
        today = date.today()
        return (self.end_date - today).days
    
    def is_due_soon(self):
        """Returns True if loan is due within 3 days (and not yet due)"""
        days = self.days_until_due()
        return 0 < days <= 3
    
    def is_overdue(self):
        """Returns True if loan is past due date"""
        return self.days_until_due() < 0
    
    def days_overdue(self):
        """Returns number of days overdue (0 if not overdue)"""
        days = self.days_until_due()
        return abs(days) if days < 0 else 0

    def __repr__(self):
        return f'<LoanRequest {self.id} for Item {self.item_id} by User {self.borrower_id}>'
    
class Feedback(db.Model):
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True, nullable=False)
    loan_request_id = db.Column(UUID(as_uuid=True), db.ForeignKey('loan_request.id'), nullable=False)
    reviewer_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=False)
    rating = db.Column(db.String(10))  # good, neutral, bad
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=func.now())

class Message(db.Model):
    __tablename__ = 'messages'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sender_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=False)
    recipient_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=False)
    item_id = db.Column(UUID(as_uuid=True), db.ForeignKey('item.id'), nullable=False)
    body = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=func.now())
    is_read = db.Column(db.Boolean, default=False)
    parent_id = db.Column(UUID(as_uuid=True), db.ForeignKey('messages.id'), nullable=True)
    loan_request_id = db.Column(UUID(as_uuid=True), db.ForeignKey('loan_request.id'), nullable=True)

    loan_request = db.relationship('LoanRequest', backref='messages')

    sender = db.relationship('User', foreign_keys=[sender_id], backref='sent_messages')
    recipient = db.relationship('User', foreign_keys=[recipient_id], backref='received_messages')
    item = db.relationship('Item', backref='messages')
    parent = db.relationship('Message', remote_side=[id], backref='replies')

    @staticmethod
    def create_message(sender_id, recipient_id, item_id, body, loan_request_id=None):
        if sender_id == recipient_id:
            raise ValueError("Sender and recipient cannot be the same user.")

    @property
    def is_loan_request_message(self):
        """Returns True if this message is related to a loan request"""
        return self.loan_request_id is not None
    
    @property
    def has_pending_action(self):
        """Returns True if message needs action (pending request or unread)"""
        if self.loan_request and self.loan_request.status == 'pending':
            # For owner: show pending if they haven't responded
            if self.recipient_id == self.item.owner_id:
                return not self.is_read
            # For borrower: show pending until request is processed
            return True
        return not self.is_read
    
    def __repr__(self):
        return f"<Message from {self.sender_id} to {self.recipient_id} at {self.timestamp}>"
        
class CircleJoinRequest(db.Model):
    __tablename__ = 'circle_join_requests'
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    circle_id = db.Column(UUID(as_uuid=True), db.ForeignKey('circle.id'), nullable=False)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=False)
    message = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected
    created_at = db.Column(db.DateTime, default=func.now())
    
    circle = db.relationship('Circle', backref='join_requests')
    user = db.relationship('User', backref='circle_join_requests')


class UserWebLink(db.Model):
    __tablename__ = 'user_web_links'
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True, nullable=False)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    platform_type = db.Column(db.String(50), nullable=False)
    platform_name = db.Column(db.String(50), nullable=True)  # For custom "other" platforms
    url = db.Column(db.String(500), nullable=False)
    display_order = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=func.now())
    
    user = db.relationship('User', backref='web_links')
    
    __table_args__ = (
        db.CheckConstraint('display_order >= 1 AND display_order <= 5'),
        db.UniqueConstraint('user_id', 'display_order'),
    )
    
    # Platform choices - organized by category
    PLATFORM_CHOICES = [
        # Major social media platforms (alphabetical)
        ('bluesky', 'Bluesky'),
        ('facebook', 'Facebook'),
        ('instagram', 'Instagram'),
        ('linkedin', 'LinkedIn'),
        ('mastodon', 'Mastodon'),
        ('threads', 'Threads'),
        ('tiktok', 'TikTok'),
        ('x', 'X (Twitter)'),
        # Content/publishing platforms
        ('blog', 'Blog'),
        ('website', 'Website'),
        # Custom option
        ('other', 'Other'),
    ]
    
    @property
    def display_name(self):
        """Returns the display name for the platform"""
        if self.platform_type == 'other' and self.platform_name:
            return self.platform_name
        
        # Find the display name from PLATFORM_CHOICES
        for value, label in self.PLATFORM_CHOICES:
            if value == self.platform_type:
                return label
        
        # This should never happen if platform_type is properly validated
        raise ValueError(f"Unknown platform type: {self.platform_type}")
    
    @property
    def icon_class(self):
        """Returns the Font Awesome icon class for the platform"""
        platform_icons = {
            'facebook': 'fab fa-facebook',
            'instagram': 'fab fa-instagram', 
            'linkedin': 'fab fa-linkedin',
            'tiktok': 'fab fa-tiktok',
            'x': 'fab fa-x-twitter',  # Updated X/Twitter icon (available in 6.4.2+)
            'mastodon': 'fab fa-mastodon',
            'bluesky': 'fas fa-cloud',  # No specific Bluesky icon, using cloud
            'threads': 'fas fa-comments',  # Use comments icon for Threads (threading concept)
            'blog': 'fas fa-blog',
            'website': 'fas fa-globe',
            'other': 'fas fa-link',  # Generic link icon for other
        }
        return platform_icons.get(self.platform_type, 'fas fa-link')
    
    def __repr__(self):
        return f'<UserWebLink {self.user_id}: {self.platform_type} - {self.url}>'
