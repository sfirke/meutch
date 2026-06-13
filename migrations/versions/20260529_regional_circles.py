"""add_regional_circle_fields

Revision ID: 20260529_regional_circles
Revises: 20260520_item_creation_token
Create Date: 2026-05-29 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260529_regional_circles"
down_revision = "20260520_item_creation_token"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "circle",
        sa.Column("is_regional", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("circle", sa.Column("regional_radius_miles", sa.Integer(), nullable=True))

    op.create_check_constraint(
        "ck_circle_regional_radius",
        "circle",
        "(NOT is_regional AND regional_radius_miles IS NULL) OR "
        "(is_regional AND regional_radius_miles BETWEEN 1 AND 100)",
    )
    op.create_check_constraint(
        "ck_circle_regional_requires_open",
        "circle",
        "NOT is_regional OR circle_type = 'open'",
    )
    op.create_check_constraint(
        "ck_circle_regional_requires_coordinates",
        "circle",
        "NOT is_regional OR (latitude IS NOT NULL AND longitude IS NOT NULL)",
    )

    op.alter_column("circle", "is_regional", server_default=None)


def downgrade():
    op.drop_constraint("ck_circle_regional_requires_coordinates", "circle", type_="check")
    op.drop_constraint("ck_circle_regional_requires_open", "circle", type_="check")
    op.drop_constraint("ck_circle_regional_radius", "circle", type_="check")
    op.drop_column("circle", "regional_radius_miles")
    op.drop_column("circle", "is_regional")
