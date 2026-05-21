"""add item creation token for idempotent listing

Revision ID: 20260520_item_creation_token
Revises: 20260516_api_jwt_auth
Create Date: 2026-05-20 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260520_item_creation_token"
down_revision = "20260516_api_jwt_auth"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "item",
        sa.Column("creation_token", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_unique_constraint("uq_item_creation_token", "item", ["creation_token"])


def downgrade():
    op.drop_constraint("uq_item_creation_token", "item", type_="unique")
    op.drop_column("item", "creation_token")
