"""Add last_login field to users

Revision ID: 20251123_add_last_login_to_users
Revises: 20251122_add_admin_functionality
Create Date: 2025-11-23 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20251123_add_last_login_to_users'
down_revision = '20251122_add_admin_functionality'
branch_labels = None
depends_on = None


def upgrade():
    # Add last_login column to users table
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_login', sa.DateTime(), nullable=True))


def downgrade():
    # Remove last_login column from users table
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('last_login')
