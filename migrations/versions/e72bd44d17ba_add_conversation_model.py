"""add_conversation_model

Revision ID: e72bd44d17ba
Revises: 20260529_regional_circles
Create Date: 2026-07-03 15:01:08.951657

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision = "e72bd44d17ba"
down_revision = "20260529_regional_circles"
branch_labels = None
depends_on = None


def upgrade():
    # 1. Create new tables
    op.create_table(
        "conversations",
        sa.Column("id", UUID(), nullable=False),
        sa.Column("context_type", sa.String(length=20), nullable=False),
        sa.Column("context_id", UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "conversation_participants",
        sa.Column("id", UUID(), nullable=False),
        sa.Column("conversation_id", UUID(), nullable=False),
        sa.Column("user_id", UUID(), nullable=False),
        sa.Column("is_archived", sa.Boolean(), nullable=True),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("conversation_id", "user_id", name="uq_conversation_participant"),
    )

    # 2. Add nullable conversation_id to messages
    op.add_column("messages", sa.Column("conversation_id", UUID(), nullable=True))

    # 3. Data backfill via temp table
    # Step A: Create temp mapping table
    op.execute("""
        CREATE TEMP TABLE conv_mapping AS
        SELECT DISTINCT
            LEAST(sender_id, recipient_id) AS user1_id,
            GREATEST(sender_id, recipient_id) AS user2_id,
            item_id,
            request_id,
            circle_id,
            gen_random_uuid() AS new_conversation_id
        FROM messages
    """)

    # Step B: Insert conversations
    op.execute("""
        INSERT INTO conversations (id, context_type, context_id, created_at)
        SELECT
            cm.new_conversation_id,
            CASE
                WHEN cm.item_id IS NOT NULL THEN 'item'
                WHEN cm.request_id IS NOT NULL THEN 'request'
                WHEN cm.circle_id IS NOT NULL THEN 'circle'
            END,
            COALESCE(cm.item_id, cm.request_id, cm.circle_id),
            (SELECT MIN(m.timestamp) FROM messages m
             WHERE LEAST(m.sender_id, m.recipient_id) = cm.user1_id
               AND GREATEST(m.sender_id, m.recipient_id) = cm.user2_id
               AND m.item_id IS NOT DISTINCT FROM cm.item_id
               AND m.request_id IS NOT DISTINCT FROM cm.request_id
               AND m.circle_id IS NOT DISTINCT FROM cm.circle_id)
        FROM conv_mapping cm
    """)

    # Step C: Create participants (2 per conversation)
    op.execute("""
        INSERT INTO conversation_participants (id, conversation_id, user_id, created_at)
        SELECT gen_random_uuid(), new_conversation_id, user1_id, NOW()
        FROM conv_mapping
        UNION ALL
        SELECT gen_random_uuid(), new_conversation_id, user2_id, NOW()
        FROM conv_mapping
    """)

    # Step D: Set conversation_id on every message
    op.execute("""
        UPDATE messages m
        SET conversation_id = cm.new_conversation_id
        FROM conv_mapping cm
        WHERE LEAST(m.sender_id, m.recipient_id) = cm.user1_id
          AND GREATEST(m.sender_id, m.recipient_id) = cm.user2_id
          AND m.item_id IS NOT DISTINCT FROM cm.item_id
          AND m.request_id IS NOT DISTINCT FROM cm.request_id
          AND m.circle_id IS NOT DISTINCT FROM cm.circle_id
    """)

    # Step E: Drop temp table
    op.execute("DROP TABLE conv_mapping")

    # 4. Make conversation_id NOT NULL
    op.alter_column("messages", "conversation_id", nullable=False)

    # 5. Drop old foreign key constraints and columns
    with op.batch_alter_table("messages", schema=None) as batch_op:
        batch_op.drop_constraint("messages_item_id_fkey", type_="foreignkey")
        batch_op.drop_constraint("fk_messages_request_id_item_request", type_="foreignkey")
        batch_op.drop_constraint("fk_messages_circle_id_circle", type_="foreignkey")
        batch_op.drop_column("circle_id")
        batch_op.drop_column("request_id")
        batch_op.drop_column("item_id")

    # 6. Drop CHECK constraint
    op.execute("ALTER TABLE messages DROP CONSTRAINT IF EXISTS ck_messages_exactly_one_target")

    # 7. Add FK constraint on conversation_id
    with op.batch_alter_table("messages", schema=None) as batch_op:
        batch_op.create_foreign_key(None, "conversations", ["conversation_id"], ["id"])


def downgrade():
    # 1. Re-add old columns (nullable initially)
    op.add_column("messages", sa.Column("item_id", UUID(), nullable=True))
    op.add_column("messages", sa.Column("request_id", UUID(), nullable=True))
    op.add_column("messages", sa.Column("circle_id", UUID(), nullable=True))

    # 2. Backfill from conversations
    op.execute("""
        UPDATE messages m
        SET item_id = CASE WHEN c.context_type = 'item' THEN c.context_id END,
            request_id = CASE WHEN c.context_type = 'request' THEN c.context_id END,
            circle_id = CASE WHEN c.context_type = 'circle' THEN c.context_id END
        FROM conversations c
        WHERE m.conversation_id = c.id
    """)

    # 3. Re-add CHECK constraint (columns stay nullable since only one is set per row)
    op.execute("""
        ALTER TABLE messages ADD CONSTRAINT ck_messages_exactly_one_target CHECK (
            ((CASE WHEN item_id IS NOT NULL THEN 1 ELSE 0 END) +
             (CASE WHEN request_id IS NOT NULL THEN 1 ELSE 0 END) +
             (CASE WHEN circle_id IS NOT NULL THEN 1 ELSE 0 END)) = 1
        )
    """)

    # 4. Drop FK constraint and conversation_id column
    with op.batch_alter_table("messages", schema=None) as batch_op:
        batch_op.drop_constraint(None, type_="foreignkey")
        batch_op.drop_column("conversation_id")

    # 5. Re-add old FKs
    with op.batch_alter_table("messages", schema=None) as batch_op:
        batch_op.create_foreign_key("fk_messages_circle_id_circle", "circle", ["circle_id"], ["id"])
        batch_op.create_foreign_key(
            "fk_messages_request_id_item_request", "item_request", ["request_id"], ["id"]
        )
        batch_op.create_foreign_key("messages_item_id_fkey", "item", ["item_id"], ["id"])

    # 6. Drop new tables
    op.drop_table("conversation_participants")
    op.drop_table("conversations")
