import uuid
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
from app import db
from flask_login import UserMixin
from flask import url_for

# Association table for many-to-many relationship between Users and Circles
circle_members = db.Table('circle_members',
    db.Column('user_id', UUID(as_uuid=True), db.ForeignKey('user.id'), primary_key=True),
    db.Column('circle_id', UUID(as_uuid=True), db.ForeignKey('circle.id'), primary_key=True),
    db.Column('joined_at', db.DateTime, default=datetime.utcnow),
    db.Column('is_admin', db.Boolean, default=False)
)

item_tags = db.Table('item_tags',
    db.Column('item_id', UUID(as_uuid=True), db.ForeignKey('item.id'), primary_key=True),
    db.Column('tag_id', UUID(as_uuid=True), db.ForeignKey('tag.id'), primary_key=True)
)

class User(UserMixin, db.Model):
    __tablename__ = 'user'
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    about_me = db.Column(db.Text, default='')
    street = db.Column(db.String(200), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    state = db.Column(db.String(100), nullable=False)
    zip_code = db.Column(db.String(20), nullable=False)
    country = db.Column(db.String(100), nullable=False, default='USA')  # Default to 'USA'
    profile_image_url = db.Column(db.String(500), nullable=True)
    @property
    def profile_image(self):
        return self.profile_image_url or url_for('static', filename='img/generic_user_avatar.png')

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

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
    owner_id = db.Column(UUID(as_uuid=True), db.ForeignKey('user.id'), nullable=False)
    available = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    category_id = db.Column(UUID(as_uuid=True), db.ForeignKey('category.id'), nullable=False)
    loan_requests = db.relationship('LoanRequest', backref='item')
    image_url = db.Column(db.String(500), nullable=True)

    @property
    def image(self):
        return self.image_url or url_for('static', filename='img/default_item_photo.png')
    
    def __repr__(self):
        return f'<Item {self.name}>'

    
class Circle(db.Model):
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=True)
    visibility = db.Column(db.String(20))  # public-open, public-approval, private
    requires_approval = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    members = db.relationship('User', secondary=circle_members, back_populates='circles')
    
    def __repr__(self):
        return f'<Circle {self.name}>'
    
    def is_admin(self, user):
        member = db.session.query(circle_members).filter_by(
            user_id=user.id,
            circle_id=self.id
        ).first()
        return member and member.is_admin if member else False

    
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
    borrower_id = db.Column(UUID(as_uuid=True), db.ForeignKey('user.id'), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, approved, denied, completed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    borrower = db.relationship('User', foreign_keys=[borrower_id], backref='loan_requests')

    def __repr__(self):
        return f'<LoanRequest {self.id} for Item {self.item_id} by User {self.borrower_id}>'
    
class Feedback(db.Model):
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True, nullable=False)
    loan_request_id = db.Column(UUID(as_uuid=True), db.ForeignKey('loan_request.id'), nullable=False)
    reviewer_id = db.Column(UUID(as_uuid=True), db.ForeignKey('user.id'), nullable=False)
    rating = db.Column(db.String(10))  # good, neutral, bad
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Message(db.Model):
    __tablename__ = 'messages'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sender_id = db.Column(UUID(as_uuid=True), db.ForeignKey('user.id'), nullable=False)
    recipient_id = db.Column(UUID(as_uuid=True), db.ForeignKey('user.id'), nullable=False)
    item_id = db.Column(UUID(as_uuid=True), db.ForeignKey('item.id'), nullable=False)
    body = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)
    parent_id = db.Column(UUID(as_uuid=True), db.ForeignKey('messages.id'), nullable=True)
    
    sender = db.relationship('User', foreign_keys=[sender_id], backref='sent_messages')
    recipient = db.relationship('User', foreign_keys=[recipient_id], backref='received_messages')
    item = db.relationship('Item', backref='messages')
    parent = db.relationship('Message', remote_side=[id], backref='replies')

    def __repr__(self):
        return f"<Message from {self.sender_id} to {self.recipient_id} at {self.timestamp}>"
        
class CircleJoinRequest(db.Model):
    __tablename__ = 'circle_join_requests'
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    circle_id = db.Column(UUID(as_uuid=True), db.ForeignKey('circle.id'), nullable=False)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    circle = db.relationship('Circle', backref='join_requests')
    user = db.relationship('User', backref='circle_join_requests')
