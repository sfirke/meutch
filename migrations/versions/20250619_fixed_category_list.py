"""
Add and enforce canonical item categories

Revision ID: 20250619_fixed_category_list
Revises: 9e382de82369
Create Date: 2025-06-19
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column
from sqlalchemy import String
import uuid

# revision identifiers, used by Alembic.
revision = '20250619_fixed_category_list'
down_revision = '9e382de82369'
branch_labels = None
depends_on = None

# Canonical category list
CATEGORIES = [
    'Electronics',
    'Books & Media',
    'Tools & Hardware',
    'Kitchen & Dining',
    'Sports & Outdoors',
    'Clothing & Accessories',
    'Home & Garden',
    'Toys & Games',
    'Baby & Kids',
    'Health & Personal Care',
    'Office & School Supplies',
    'Musical Instruments',
    'Art & Craft Supplies',
    'Automotive',
    'Pet Supplies',
    'Miscellaneous',
]

def upgrade():
    conn = op.get_bind()
    # Insert any missing categories
    existing = set(r[0] for r in conn.execute(sa.text('SELECT name FROM category')).fetchall())
    for cat in CATEGORIES:
        if cat not in existing:
            conn.execute(
                sa.text('INSERT INTO category (id, name) VALUES (:id, :name)'),
                {'id': str(uuid.uuid4()), 'name': cat}
            )
    # Optionally, remove categories not in canonical list (uncomment to enforce strictness)
    # conn.execute(sa.text('DELETE FROM category WHERE name NOT IN :catlist'), {'catlist': tuple(CATEGORIES)})

def downgrade():
    conn = op.get_bind()
    for cat in CATEGORIES:
        conn.execute(sa.text('DELETE FROM category WHERE name = :name'), {'name': cat})
