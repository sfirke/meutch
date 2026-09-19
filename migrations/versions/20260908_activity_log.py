"""add activity_log table

Revision ID: 20260908_activity_log
Revises: 20260912_ext_request_message
Create Date: 2026-09-08 10:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260908_activity_log"
down_revision = "20260912_ext_request_message"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "activity_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("subject_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("target_type", sa.String(length=32), nullable=True),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column("user_agent", sa.String(length=400), nullable=True),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("context", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["subject_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    # All six indexes are created here, with the table, even though the filtering they
    # serve arrives in later changes. Creating them on an empty table is free; adding
    # them later means either locking a populated table or a CONCURRENTLY build in an
    # autocommit block.
    op.create_index("ix_activity_log_occurred_at_id", "activity_log", ["occurred_at", "id"])
    op.create_index(
        "ix_activity_log_event_type_occurred_at", "activity_log", ["event_type", "occurred_at"]
    )
    op.create_index(
        "ix_activity_log_actor_occurred_at",
        "activity_log",
        ["actor_user_id", "occurred_at"],
        postgresql_where=sa.text("actor_user_id IS NOT NULL"),
    )
    op.create_index(
        "ix_activity_log_subject_occurred_at",
        "activity_log",
        ["subject_user_id", "occurred_at"],
        postgresql_where=sa.text("subject_user_id IS NOT NULL"),
    )
    op.create_index(
        "ix_activity_log_target_occurred_at",
        "activity_log",
        ["target_type", "target_id", "occurred_at"],
        postgresql_where=sa.text("target_id IS NOT NULL"),
    )
    # Expression index behind the attempted-email search. The address is stored as
    # typed, so the index is on lower() and the search compares lower() to lower().
    # `->> ... IS NOT NULL` is used instead of the `?` key-exists operator so the
    # predicate reads the same way as the expression.
    op.create_index(
        "ix_activity_log_attempted_email",
        "activity_log",
        [sa.text("lower(context->>'attempted_email')")],
        postgresql_where=sa.text("(context->>'attempted_email') IS NOT NULL"),
    )


def downgrade():
    op.drop_index("ix_activity_log_attempted_email", table_name="activity_log")
    op.drop_index("ix_activity_log_target_occurred_at", table_name="activity_log")
    op.drop_index("ix_activity_log_subject_occurred_at", table_name="activity_log")
    op.drop_index("ix_activity_log_actor_occurred_at", table_name="activity_log")
    op.drop_index("ix_activity_log_event_type_occurred_at", table_name="activity_log")
    op.drop_index("ix_activity_log_occurred_at_id", table_name="activity_log")
    op.drop_table("activity_log")
