"""Add soft delete columns to users

Revision ID: 295e4255c995
Revises: b065c9d9d718
Create Date: 2025-08-23 13:55:20.104099

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '295e4255c995'
down_revision = 'b065c9d9d718'
branch_labels = None
depends_on = None


def upgrade():
    # Add soft delete columns to users table
    op.add_column('users', sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('users', sa.Column('deleted_at', sa.DateTime(), nullable=True))


def downgrade():
    # Remove soft delete columns
    op.drop_column('users', 'deleted_at')
    op.drop_column('users', 'is_deleted')
