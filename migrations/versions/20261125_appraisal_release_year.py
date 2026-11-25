"""add release_year to item_appraisal and impact_event

Revision ID: 20261125_appraisal_release_year
Revises: 20261122_impact_event
Create Date: 2026-11-25 12:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20261125_appraisal_release_year"
down_revision = "20261122_impact_event"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("item_appraisal", sa.Column("release_year", sa.Integer(), nullable=True))
    op.add_column("impact_event", sa.Column("release_year", sa.Integer(), nullable=True))


def downgrade():
    op.drop_column("impact_event", "release_year")
    op.drop_column("item_appraisal", "release_year")
