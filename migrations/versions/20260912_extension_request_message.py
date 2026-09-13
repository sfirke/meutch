"""link extension request messages and record the due date at request time

Revision ID: 20260912_ext_request_message
Revises: 93a93dd6b3ac
Create Date: 2026-09-12 15:30:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260912_ext_request_message"
down_revision = "93a93dd6b3ac"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "loan_extension_request",
        sa.Column("previous_end_date", sa.Date(), nullable=True),
    )
    op.execute(
        "UPDATE loan_extension_request SET previous_end_date = loan_request.end_date "
        "FROM loan_request WHERE loan_request.id = loan_extension_request.loan_request_id"
    )
    op.alter_column("loan_extension_request", "previous_end_date", nullable=False)

    op.add_column(
        "messages",
        sa.Column("loan_extension_request_id", sa.UUID(), nullable=True),
    )
    op.create_index(
        op.f("ix_messages_loan_extension_request_id"),
        "messages",
        ["loan_extension_request_id"],
    )
    op.create_foreign_key(
        "messages_loan_extension_request_id_fkey",
        "messages",
        "loan_extension_request",
        ["loan_extension_request_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade():
    op.drop_constraint("messages_loan_extension_request_id_fkey", "messages", type_="foreignkey")
    op.drop_index(op.f("ix_messages_loan_extension_request_id"), table_name="messages")
    op.drop_column("messages", "loan_extension_request_id")
    op.drop_column("loan_extension_request", "previous_end_date")
