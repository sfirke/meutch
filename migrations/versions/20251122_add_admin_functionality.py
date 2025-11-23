"""Add admin functionality with is_admin field and AdminAction audit log

Revision ID: 20251122_add_admin_functionality
Revises: 7c96bec8621d
Create Date: 2025-11-22 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import func


# revision identifiers, used by Alembic.
revision = '20251122_add_admin_functionality'
down_revision = '7c96bec8621d'
branch_labels = None
depends_on = None


def upgrade():
    # Add is_admin column to users table
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_admin', sa.Boolean(), nullable=False, server_default='false'))
    
    # Create admin_action audit log table
    op.create_table(
        'admin_action',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('action_type', sa.String(50), nullable=False),
        sa.Column('target_user_id', UUID(as_uuid=True), nullable=False),
        sa.Column('admin_user_id', UUID(as_uuid=True), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False, server_default=func.now()),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['target_user_id'], ['users.id'], name='fk_admin_action_target_user'),
        sa.ForeignKeyConstraint(['admin_user_id'], ['users.id'], name='fk_admin_action_admin_user')
    )
    
    # Create indexes for efficient querying
    op.create_index('ix_admin_action_timestamp', 'admin_action', ['timestamp'])
    op.create_index('ix_admin_action_target_user_id', 'admin_action', ['target_user_id'])
    op.create_index('ix_admin_action_admin_user_id', 'admin_action', ['admin_user_id'])


def downgrade():
    # Drop admin_action table and indexes
    op.drop_index('ix_admin_action_admin_user_id', table_name='admin_action')
    op.drop_index('ix_admin_action_target_user_id', table_name='admin_action')
    op.drop_index('ix_admin_action_timestamp', table_name='admin_action')
    op.drop_table('admin_action')
    
    # Remove is_admin column from users table
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('is_admin')
