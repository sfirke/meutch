"""add impact_event table

Revision ID: 20261122_impact_event
Revises: 20261122_item_appraisal
Create Date: 2026-11-22 13:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20261122_impact_event"
down_revision = "20261122_item_appraisal"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "impact_event",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("item_id", sa.UUID(), nullable=True),
        sa.Column("loan_request_id", sa.UUID(), nullable=True),
        sa.Column("beneficiary_id", sa.UUID(), nullable=True),
        sa.Column("provider_id", sa.UUID(), nullable=True),
        sa.Column("item_name", sa.String(length=100), nullable=False),
        sa.Column("category_name", sa.String(length=50), nullable=False),
        sa.Column("new_price_usd", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=True),
        sa.Column("condition", sa.String(length=16), nullable=True),
        sa.Column("resale_demand", sa.String(length=16), nullable=True),
        sa.Column("footprint_category", sa.String(length=64), nullable=True),
        sa.Column("model_version", sa.String(length=100), nullable=True),
        sa.Column("usd_saved", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("kg_co2e_avoided", sa.Numeric(precision=12, scale=3), nullable=True),
        sa.Column("policy_version", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("kind IN ('loan', 'giveaway')", name="ck_impact_event_kind"),
        sa.ForeignKeyConstraint(["item_id"], ["item.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["loan_request_id"], ["loan_request.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["beneficiary_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["provider_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("loan_request_id"),
    )
    op.create_index(
        op.f("ix_impact_event_occurred_at"), "impact_event", ["occurred_at"], unique=False
    )
    op.create_index(op.f("ix_impact_event_item_id"), "impact_event", ["item_id"], unique=False)
    op.create_index(
        op.f("ix_impact_event_beneficiary_id"), "impact_event", ["beneficiary_id"], unique=False
    )
    op.create_index(
        op.f("ix_impact_event_provider_id"), "impact_event", ["provider_id"], unique=False
    )
    op.create_index(
        "uq_impact_event_giveaway_item",
        "impact_event",
        ["item_id"],
        unique=True,
        postgresql_where=sa.text("kind = 'giveaway'"),
    )


def downgrade():
    op.drop_index("uq_impact_event_giveaway_item", table_name="impact_event")
    op.drop_index(op.f("ix_impact_event_provider_id"), table_name="impact_event")
    op.drop_index(op.f("ix_impact_event_beneficiary_id"), table_name="impact_event")
    op.drop_index(op.f("ix_impact_event_item_id"), table_name="impact_event")
    op.drop_index(op.f("ix_impact_event_occurred_at"), table_name="impact_event")
    op.drop_table("impact_event")
