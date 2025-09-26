"""
Backfill circle.visibility values and normalize legacy states.

Revision ID: ba9f5a2b7c1e
Revises: f6a8553521db
Create Date: 2025-09-25
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'ba9f5a2b7c1e'
down_revision = 'f6a8553521db'
branch_labels = None
depends_on = None

def upgrade():
    conn = op.get_bind()

    # Normalize legacy values if they exist
    conn.execute(sa.text("""UPDATE circle SET visibility = 'public', requires_approval = COALESCE(requires_approval, FALSE) WHERE visibility = 'public-open'"""))
    conn.execute(sa.text("""UPDATE circle SET visibility = 'public', requires_approval = TRUE WHERE visibility = 'public-approval'"""))
    conn.execute(sa.text("""UPDATE circle SET requires_approval = TRUE WHERE visibility = 'private'"""))

    # Infer visibility where NULL
    conn.execute(sa.text("""UPDATE circle SET visibility = 'private' WHERE visibility IS NULL AND COALESCE(requires_approval, FALSE) = TRUE"""))
    conn.execute(sa.text("""UPDATE circle SET visibility = 'public' WHERE visibility IS NULL"""))

    with op.batch_alter_table('circle') as batch_op:
        batch_op.alter_column('visibility', existing_type=sa.String(length=20), server_default='public', nullable=False)


def downgrade():
    with op.batch_alter_table('circle') as batch_op:
        batch_op.alter_column('visibility', existing_type=sa.String(length=20), server_default=None, nullable=True)
    conn = op.get_bind()
    conn.execute(sa.text("""UPDATE circle SET visibility = NULL WHERE visibility IN ('public','private')"""))
