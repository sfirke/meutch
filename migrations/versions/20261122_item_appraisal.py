"""add item_appraisal table

Revision ID: 20261122_item_appraisal
Revises: 20261028_announcements
Create Date: 2026-11-22 12:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20261122_item_appraisal"
down_revision = "20261028_announcements"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "item_appraisal",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("item_id", sa.UUID(), nullable=False),
        sa.Column("new_price_usd", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("unit_new_price_usd", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=True),
        sa.Column("condition", sa.String(length=16), nullable=False),
        sa.Column("resale_demand", sa.String(length=16), nullable=False),
        sa.Column("confidence", sa.String(length=16), nullable=True),
        sa.Column("footprint_category", sa.String(length=64), nullable=True),
        sa.Column("assumption", sa.Text(), nullable=False),
        sa.Column("impacts", sa.String(length=64), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("model_version", sa.String(length=100), nullable=False),
        sa.Column("model_fingerprint", sa.String(length=100), nullable=True),
        sa.Column("estimated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["item_id"], ["item.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("item_id"),
    )
    op.create_index(
        op.f("ix_item_appraisal_fingerprint"), "item_appraisal", ["fingerprint"], unique=False
    )


def downgrade():
    op.drop_index(op.f("ix_item_appraisal_fingerprint"), table_name="item_appraisal")
    op.drop_table("item_appraisal")
