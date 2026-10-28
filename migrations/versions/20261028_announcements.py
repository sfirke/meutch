"""add announcement and announcement_dismissal tables

Revision ID: 20261028_announcements
Revises: 20260922_is_archived_not_null
Create Date: 2026-10-28 18:30:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20261028_announcements"
down_revision = "20260922_is_archived_not_null"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "announcement",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("message", sa.String(length=280), nullable=False),
        sa.Column("link_url", sa.String(length=500), nullable=True),
        sa.Column("link_text", sa.String(length=60), nullable=True),
        sa.Column("level", sa.String(length=16), nullable=False),
        sa.Column("starts_at", sa.DateTime(), nullable=False),
        sa.Column("ends_at", sa.DateTime(), nullable=True),
        sa.Column("dismissible", sa.Boolean(), nullable=False),
        sa.Column("created_by_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "announcement_dismissal",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("announcement_id", sa.UUID(), nullable=False),
        sa.Column("dismissed_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["announcement_id"], ["announcement.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "announcement_id"),
    )


def downgrade():
    op.drop_table("announcement_dismissal")
    op.drop_table("announcement")
