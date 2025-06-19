"""Initial migration - create all tables

Revision ID: 00000000_initial
Revises: 
Create Date: 2025-06-07 22:45:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
import uuid

# revision identifiers, used by Alembic.
revision = '00000000_initial'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Create user table
    op.create_table('user',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False),
        sa.Column('email', sa.String(length=120), nullable=False),
        sa.Column('password_hash', sa.String(length=128), nullable=False),
        sa.Column('first_name', sa.String(length=50), nullable=False),
        sa.Column('last_name', sa.String(length=50), nullable=False),
        sa.Column('about_me', sa.Text(), nullable=True),
        sa.Column('street', sa.String(length=200), nullable=False),
        sa.Column('city', sa.String(length=100), nullable=False),
        sa.Column('state', sa.String(length=100), nullable=False),
        sa.Column('zip_code', sa.String(length=20), nullable=False),
        sa.Column('country', sa.String(length=100), nullable=False),
        sa.Column('profile_image_url', sa.String(length=500), nullable=True),
        sa.Column('email_confirmed', sa.Boolean(), nullable=False),
        sa.Column('email_confirmation_token', sa.String(length=128), nullable=True),
        sa.Column('email_confirmation_sent_at', sa.DateTime(), nullable=True),
        sa.Column('password_reset_token', sa.String(length=128), nullable=True),
        sa.Column('password_reset_sent_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email')
    )

    # Create category table
    op.create_table('category',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )

    # Create circle table
    op.create_table('circle',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('requires_approval', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Create tag table
    op.create_table('tag',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )

    # Create item table
    op.create_table('item',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('category_id', UUID(as_uuid=True), nullable=False),
        sa.Column('owner_id', UUID(as_uuid=True), nullable=False),
        sa.Column('image_url', sa.String(length=500), nullable=True),
        sa.Column('available', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['category_id'], ['category.id'], ),
        sa.ForeignKeyConstraint(['owner_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create loan_request table
    op.create_table('loan_request',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False),
        sa.Column('item_id', UUID(as_uuid=True), nullable=False),
        sa.Column('borrower_id', UUID(as_uuid=True), nullable=False),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=True),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(['borrower_id'], ['user.id'], ),
        sa.ForeignKeyConstraint(['item_id'], ['item.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create message table
    op.create_table('message',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False),
        sa.Column('sender_id', UUID(as_uuid=True), nullable=False),
        sa.Column('recipient_id', UUID(as_uuid=True), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('is_read', sa.Boolean(), nullable=False),
        sa.Column('loan_request_id', UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['loan_request_id'], ['loan_request.id'], ),
        sa.ForeignKeyConstraint(['recipient_id'], ['user.id'], ),
        sa.ForeignKeyConstraint(['sender_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create circle_join_requests table
    op.create_table('circle_join_requests',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False),
        sa.Column('circle_id', UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), nullable=False),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['circle_id'], ['circle.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create association tables
    op.create_table('circle_members',
        sa.Column('user_id', UUID(as_uuid=True), nullable=False),
        sa.Column('circle_id', UUID(as_uuid=True), nullable=False),
        sa.Column('joined_at', sa.DateTime(), nullable=True),
        sa.Column('is_admin', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['circle_id'], ['circle.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('user_id', 'circle_id')
    )

    op.create_table('item_tags',
        sa.Column('item_id', UUID(as_uuid=True), nullable=False),
        sa.Column('tag_id', UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(['item_id'], ['item.id'], ),
        sa.ForeignKeyConstraint(['tag_id'], ['tag.id'], ),
        sa.PrimaryKeyConstraint('item_id', 'tag_id')
    )

def downgrade():
    op.drop_table('item_tags')
    op.drop_table('circle_members')
    op.drop_table('circle_join_requests')
    op.drop_table('message')
    op.drop_table('loan_request')
    op.drop_table('item')
    op.drop_table('tag')
    op.drop_table('circle')
    op.drop_table('category')
    op.drop_table('user')
