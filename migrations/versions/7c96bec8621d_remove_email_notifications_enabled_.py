"""Remove email_notifications_enabled column from users

Revision ID: 7c96bec8621d
Revises: 50d46e002e85
Create Date: 2025-11-20 08:48:43.692345

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7c96bec8621d'
down_revision = '50d46e002e85'
branch_labels = None
depends_on = None


def upgrade():
    # Remove email_notifications_enabled column from users table
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('email_notifications_enabled')


def downgrade():
    # Add back email_notifications_enabled column to users table
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('email_notifications_enabled', sa.Boolean(), nullable=False, server_default='true'))
