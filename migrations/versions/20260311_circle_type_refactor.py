"""refactor_circle_visibility_to_circle_type

Revision ID: 20260311_circle_type_refactor
Revises: 20260223_circle_id_messages
Create Date: 2026-03-11 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260311_circle_type_refactor'
down_revision = '20260223_circle_id_messages'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    op.alter_column('circle', 'visibility', new_column_name='circle_type')

    conn.execute(sa.text("""
        UPDATE circle
        SET circle_type = CASE
            WHEN circle_type IN ('public', 'public-open') THEN 'open'
            WHEN circle_type IN ('private', 'public-approval') THEN 'closed'
            WHEN circle_type = 'unlisted' THEN 'secret'
            WHEN circle_type IS NULL THEN 'open'
            ELSE 'open'
        END
    """))

    op.drop_column('circle', 'requires_approval')

    op.alter_column(
        'circle',
        'circle_type',
        existing_type=sa.String(length=20),
        nullable=False,
        server_default=sa.text("'open'")
    )


def downgrade():
    conn = op.get_bind()

    op.add_column('circle', sa.Column('requires_approval', sa.Boolean(), nullable=True, server_default=sa.false()))

    conn.execute(sa.text("""
        UPDATE circle
        SET requires_approval = CASE
            WHEN circle_type IN ('closed', 'secret') THEN TRUE
            ELSE FALSE
        END
    """))

    conn.execute(sa.text("""
        UPDATE circle
        SET circle_type = CASE
            WHEN circle_type = 'open' THEN 'public'
            WHEN circle_type = 'closed' THEN 'private'
            WHEN circle_type = 'secret' THEN 'unlisted'
            WHEN circle_type IS NULL THEN 'public'
            ELSE 'public'
        END
    """))

    op.alter_column(
        'circle',
        'circle_type',
        existing_type=sa.String(length=20),
        nullable=False,
        server_default=sa.text("'public'")
    )

    op.alter_column('circle', 'circle_type', new_column_name='visibility')
