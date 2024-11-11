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
    db.Column('joined_at', db.DateTime, default=datetime.utcnow)
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

    # Define the other side of the relationship using back_populates
    members = db.relationship('User', secondary=circle_members, back_populates='circles')
    
    def __repr__(self):
        return f'<Circle {self.name}>'

    
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

class Feedback(db.Model):
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True, nullable=False)
    loan_request_id = db.Column(UUID(as_uuid=True), db.ForeignKey('loan_request.id'), nullable=False)
    reviewer_id = db.Column(UUID(as_uuid=True), db.ForeignKey('user.id'), nullable=False)
    rating = db.Column(db.String(10))  # good, neutral, bad
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)