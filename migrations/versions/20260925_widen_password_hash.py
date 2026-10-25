"""widen users.password_hash for scrypt hashes

Revision ID: 20260925_widen_password_hash
Revises: 20260908_activity_log
Create Date: 2026-09-25 12:00:00.000000

Werkzeug 3 hashes new passwords with scrypt, which produces ~162-character strings.
Existing pbkdf2 hashes keep working unchanged. Widening a varchar in Postgres only
updates the catalog, so this does not rewrite or lock the table for long.

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260925_widen_password_hash"
down_revision = "20260908_activity_log"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "users",
        "password_hash",
        existing_type=sa.String(length=128),
        type_=sa.String(length=256),
        existing_nullable=False,
    )


def downgrade():
    # Fails once any scrypt hash has been stored, which is the safe outcome:
    # truncating a hash would lock that user out.
    op.alter_column(
        "users",
        "password_hash",
        existing_type=sa.String(length=256),
        type_=sa.String(length=128),
        existing_nullable=False,
    )
