"""add account lockout columns

Revision ID: 20260610_account_lockout
Revises: e72bd44d17ba
Create Date: 2026-06-10 22:14:16.625640

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260610_account_lockout"
down_revision = "e72bd44d17ba"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("failed_login_attempts", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column("lockout_count", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(sa.Column("locked_until", sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("locked_until")
        batch_op.drop_column("lockout_count")
        batch_op.drop_column("failed_login_attempts")
