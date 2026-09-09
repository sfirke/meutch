"""Add API token session tables

Revision ID: 20260516_api_jwt_auth
Revises: 20260405_item_images
Create Date: 2026-05-16 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260516_api_jwt_auth"
down_revision = "20260405_item_images"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "api_token_family",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("current_refresh_jti", sa.String(length=36), nullable=False),
        sa.Column("current_refresh_expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("revoke_reason", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id"),
    )
    op.create_index(
        op.f("ix_api_token_family_current_refresh_jti"),
        "api_token_family",
        ["current_refresh_jti"],
        unique=True,
    )

    op.create_table(
        "api_token_blocklist",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("jti", sa.String(length=36), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("family_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("token_type", sa.String(length=20), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("reason", sa.String(length=50), nullable=True),
        sa.ForeignKeyConstraint(["family_id"], ["api_token_family.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id"),
    )
    op.create_index(
        op.f("ix_api_token_blocklist_jti"),
        "api_token_blocklist",
        ["jti"],
        unique=True,
    )


def downgrade():
    op.drop_index(op.f("ix_api_token_blocklist_jti"), table_name="api_token_blocklist")
    op.drop_table("api_token_blocklist")

    op.drop_index(op.f("ix_api_token_family_current_refresh_jti"), table_name="api_token_family")
    op.drop_table("api_token_family")
