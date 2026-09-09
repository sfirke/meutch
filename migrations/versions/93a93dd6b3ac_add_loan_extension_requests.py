"""add loan extension requests

Revision ID: 93a93dd6b3ac
Revises: 20260610_account_lockout
Create Date: 2026-04-03 23:59:38.991416

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '93a93dd6b3ac'
down_revision = '20260610_account_lockout'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('loan_extension_request',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('loan_request_id', sa.UUID(), nullable=False),
    sa.Column('proposed_end_date', sa.Date(), nullable=False),
    sa.Column('message', sa.Text(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('responded_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['loan_request_id'], ['loan_request.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('id')
    )
    op.create_index(
        op.f('ix_loan_extension_request_loan_request_id'),
        'loan_extension_request',
        ['loan_request_id'],
    )


def downgrade():
    op.drop_index(
        op.f('ix_loan_extension_request_loan_request_id'),
        table_name='loan_extension_request',
    )
    op.drop_table('loan_extension_request')
