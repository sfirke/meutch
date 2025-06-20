"""
Add image_url to Circle
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20250619_add_circle_image_url'
down_revision = '20250619_fixed_category_list'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('circle', sa.Column('image_url', sa.String(length=500), nullable=True))

def downgrade():
    op.drop_column('circle', 'image_url')
