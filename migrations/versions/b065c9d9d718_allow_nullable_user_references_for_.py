"""Allow nullable user references for account deletion

Revision ID: b065c9d9d718
Revises: 20250619_add_circle_image_url
Create Date: 2025-08-23 13:13:38.579093

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b065c9d9d718'
down_revision = '20250619_add_circle_image_url'
branch_labels = None
depends_on = None


def upgrade():
    # Make owner_id nullable in items table
    op.alter_column('item', 'owner_id', nullable=True)
    
    # Make borrower_id nullable in loan_request table
    op.alter_column('loan_request', 'borrower_id', nullable=True)
    
    # Make sender_id and recipient_id nullable in messages table
    op.alter_column('messages', 'sender_id', nullable=True)
    op.alter_column('messages', 'recipient_id', nullable=True)


def downgrade():
    # Reverse the changes - make columns NOT nullable again
    # Note: This might fail if there are NULL values in the database
    op.alter_column('messages', 'recipient_id', nullable=False)
    op.alter_column('messages', 'sender_id', nullable=False)
    op.alter_column('loan_request', 'borrower_id', nullable=False)
    op.alter_column('item', 'owner_id', nullable=False)
