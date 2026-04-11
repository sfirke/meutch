"""Add item_image table for multiple photos per item

Revision ID: 20260405_item_images
Revises: 20260313_digest_fields
Create Date: 2026-04-05
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '20260405_item_images'
down_revision = '20260313_digest_fields'
branch_labels = None
depends_on = None


def upgrade():
    # Create item_image table
    op.create_table('item_image',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('item_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('url', sa.String(length=500), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['item_id'], ['item.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('id')
    )

    # Migrate existing image_url data to item_image rows
    op.execute("""
        INSERT INTO item_image (id, item_id, url, position, created_at)
        SELECT gen_random_uuid(), id, image_url, 0, COALESCE(created_at, NOW())
        FROM item
        WHERE image_url IS NOT NULL AND image_url != ''
    """)

    # Drop image_url column from item table
    op.drop_column('item', 'image_url')


def downgrade():
    # Re-add image_url column
    op.add_column('item', sa.Column('image_url', sa.String(length=500), nullable=True))

    # Copy first image (position 0) back to item.image_url
    op.execute("""
        UPDATE item SET image_url = (
            SELECT url FROM item_image
            WHERE item_image.item_id = item.id
            ORDER BY position ASC
            LIMIT 1
        )
    """)

    op.drop_table('item_image')
