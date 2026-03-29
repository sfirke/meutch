"""add_request_id_to_messages_and_target_check

Revision ID: 6f5d0efb9c31
Revises: 3cd04173bf87
Create Date: 2026-02-13 12:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6f5d0efb9c31'
down_revision = '3cd04173bf87'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('messages', 'item_id', existing_type=sa.UUID(), nullable=True)
    op.add_column('messages', sa.Column('request_id', sa.UUID(), nullable=True))
    op.create_foreign_key(
        'fk_messages_request_id_item_request',
        'messages',
        'item_request',
        ['request_id'],
        ['id']
    )
    op.create_check_constraint(
        'ck_messages_exactly_one_target',
        'messages',
        '((item_id IS NOT NULL AND request_id IS NULL) OR (item_id IS NULL AND request_id IS NOT NULL))'
    )


def downgrade():
    op.drop_constraint('ck_messages_exactly_one_target', 'messages', type_='check')
    op.drop_constraint('fk_messages_request_id_item_request', 'messages', type_='foreignkey')
    op.drop_column('messages', 'request_id')
    op.alter_column('messages', 'item_id', existing_type=sa.UUID(), nullable=False)
