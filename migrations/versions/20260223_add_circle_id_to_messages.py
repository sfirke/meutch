"""add_circle_id_to_messages

Revision ID: 20260223_circle_id_messages
Revises: 6f5d0efb9c31
Create Date: 2026-02-23 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260223_circle_id_messages'
down_revision = '6f5d0efb9c31'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint('ck_messages_exactly_one_target', 'messages', type_='check')
    op.add_column('messages', sa.Column('circle_id', sa.UUID(), nullable=True))
    op.create_foreign_key(
        'fk_messages_circle_id_circle',
        'messages',
        'circle',
        ['circle_id'],
        ['id']
    )
    op.create_check_constraint(
        'ck_messages_exactly_one_target',
        'messages',
        '((CASE WHEN item_id IS NOT NULL THEN 1 ELSE 0 END) + '
        '(CASE WHEN request_id IS NOT NULL THEN 1 ELSE 0 END) + '
        '(CASE WHEN circle_id IS NOT NULL THEN 1 ELSE 0 END)) = 1'
    )


def downgrade():
    op.drop_constraint('ck_messages_exactly_one_target', 'messages', type_='check')
    op.drop_constraint('fk_messages_circle_id_circle', 'messages', type_='foreignkey')
    op.drop_column('messages', 'circle_id')
    op.create_check_constraint(
        'ck_messages_exactly_one_target',
        'messages',
        '((item_id IS NOT NULL AND request_id IS NULL) OR (item_id IS NULL AND request_id IS NOT NULL))'
    )
