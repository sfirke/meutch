"""make conversation_participants.is_archived non-nullable

Revision ID: 20260922_is_archived_not_null
Revises: 20260908_activity_log
Create Date: 2026-09-22 10:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260922_is_archived_not_null"
down_revision = "20260908_activity_log"
branch_labels = None
depends_on = None


def upgrade():
    # Participant rows backfilled by the conversations migration never set
    # is_archived. A row with archived_at set was archived, so keep that.
    op.execute(
        "UPDATE conversation_participants "
        "SET is_archived = (archived_at IS NOT NULL) "
        "WHERE is_archived IS NULL"
    )
    op.alter_column(
        "conversation_participants",
        "is_archived",
        existing_type=sa.Boolean(),
        nullable=False,
        server_default="false",
    )


def downgrade():
    op.alter_column(
        "conversation_participants",
        "is_archived",
        existing_type=sa.Boolean(),
        nullable=True,
        server_default=None,
    )
