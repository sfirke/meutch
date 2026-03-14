"""add_digest_fields_to_users

Revision ID: 20260313_digest_fields
Revises: 20260311_circle_type_refactor
Create Date: 2026-03-13 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260313_digest_fields'
down_revision = '20260311_circle_type_refactor'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('digest_frequency', sa.String(length=20), nullable=False, server_default='weekly'))
        batch_op.add_column(sa.Column('digest_radius_miles', sa.Integer(), nullable=False, server_default='10'))
        batch_op.add_column(sa.Column('digest_include_giveaways', sa.Boolean(), nullable=False, server_default='true'))
        batch_op.add_column(sa.Column('digest_include_requests', sa.Boolean(), nullable=False, server_default='true'))
        batch_op.add_column(sa.Column('digest_include_circle_joins', sa.Boolean(), nullable=False, server_default='true'))
        batch_op.add_column(sa.Column('digest_include_loans', sa.Boolean(), nullable=False, server_default='true'))
        batch_op.add_column(sa.Column('digest_giveaways_include_public', sa.Boolean(), nullable=False, server_default='true'))
        batch_op.add_column(sa.Column('digest_requests_include_public', sa.Boolean(), nullable=False, server_default='true'))
        batch_op.add_column(sa.Column('digest_last_sent_at', sa.DateTime(), nullable=True))

    # Product decision: existing users should be explicitly opted out.
    conn = op.get_bind()
    conn.execute(sa.text("UPDATE users SET digest_frequency = 'none'"))


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('digest_last_sent_at')
        batch_op.drop_column('digest_requests_include_public')
        batch_op.drop_column('digest_giveaways_include_public')
        batch_op.drop_column('digest_include_loans')
        batch_op.drop_column('digest_include_circle_joins')
        batch_op.drop_column('digest_include_requests')
        batch_op.drop_column('digest_include_giveaways')
        batch_op.drop_column('digest_radius_miles')
        batch_op.drop_column('digest_frequency')
