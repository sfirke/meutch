"""Add is_public_showcase to users

Revision ID: b7b770cddce5
Revises: 20251123_add_last_login_to_users
Create Date: 2025-11-29 15:17:55.019095

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b7b770cddce5'
down_revision = '20251123_add_last_login_to_users'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_public_showcase', sa.Boolean(), nullable=False, server_default='false'))


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('is_public_showcase')
