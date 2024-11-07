from datetime import datetime
from app import db
from flask_login import UserMixin

# Many-to-many relationships
circle_memberships = db.Table('circle_memberships',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('circle_id', db.Integer, db.ForeignKey('circle.id'))
)

item_categories = db.Table('item_categories',
    db.Column('item_id', db.Integer, db.ForeignKey('item.id')),
    db.Column('category_id', db.Integer, db.ForeignKey('item_category.id'))
)

class Friendship(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    requester_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    requested_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    status = db.Column(db.String(20), default='pending')  # pending, approved
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    
    # Updated Name Fields
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    
    # Updated Address Fields
    street = db.Column(db.String(200), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    state = db.Column(db.String(100), nullable=False)
    zip_code = db.Column(db.String(20), nullable=False)
    country = db.Column(db.String(100), nullable=False, default='USA')  # Default to 'USA'
    
    # Relationships
    items = db.relationship('Item', backref='owner', lazy=True)
    circles = db.relationship('Circle', secondary=circle_memberships, backref='members')
    friends = db.relationship('User',
        secondary='friendship',
        primaryjoin=(Friendship.requester_id == id) & (Friendship.status == 'approved'),
        secondaryjoin=(Friendship.requested_id == id) & (Friendship.status == 'approved'),
        backref='friend_of'
    )
    
class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    available = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    categories = db.relationship('ItemCategory', secondary=item_categories, backref='items')
    tags = db.relationship('ItemTag', backref='item')
    loan_requests = db.relationship('LoanRequest', backref='item')
    
class Circle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    uuid = db.Column(db.String(36), unique=True)
    visibility = db.Column(db.String(20))  # public-open, public-approval, private
    
class ItemCategory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True)

class ItemTag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50))
    item_id = db.Column(db.Integer, db.ForeignKey('item.id'))

class LoanRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('item.id'))
    borrower_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, approved, denied, completed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Feedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    loan_request_id = db.Column(db.Integer, db.ForeignKey('loan_request.id'))
    reviewer_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    rating = db.Column(db.String(10))  # good, neutral, bad
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)