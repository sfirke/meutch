"""Add email reminder tracking fields to LoanRequest

Revision ID: 50d46e002e85
Revises: 13689397baa9
Create Date: 2025-10-31 19:32:16.765088

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '50d46e002e85'
down_revision = '13689397baa9'
branch_labels = None
depends_on = None


def upgrade():
    # Add email reminder tracking fields to loan_request table
    with op.batch_alter_table('loan_request', schema=None) as batch_op:
        batch_op.add_column(sa.Column('due_soon_reminder_sent', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('due_date_reminder_sent', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('last_overdue_reminder_sent', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('overdue_reminder_count', sa.Integer(), nullable=False, server_default='0'))


def downgrade():
    # Remove email reminder tracking fields from loan_request table
    with op.batch_alter_table('loan_request', schema=None) as batch_op:
        batch_op.drop_column('overdue_reminder_count')
        batch_op.drop_column('last_overdue_reminder_sent')
        batch_op.drop_column('due_date_reminder_sent')
        batch_op.drop_column('due_soon_reminder_sent')
