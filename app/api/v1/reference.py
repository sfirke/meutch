"""Reference-data endpoints for API v1."""

from flask_jwt_extended import jwt_required

from app.api.v1 import bp
from app.api.v1.responses import build_collection_response
from app.api.v1.schemas.reference import CategorySchema, TagSchema
from app.models import Category, Tag

CATEGORY_SCHEMA = CategorySchema(many=True)
TAG_SCHEMA = TagSchema(many=True)


@bp.get("/categories")
@jwt_required()
def list_categories():
    """Return categories for authenticated API clients."""
    categories = Category.query.order_by(Category.name.asc()).all()
    return build_collection_response("categories", CATEGORY_SCHEMA.dump(categories))


@bp.get("/tags")
@jwt_required()
def list_tags():
    """Return tags for authenticated API clients."""
    tags = Tag.query.order_by(Tag.name.asc()).all()
    return build_collection_response("tags", TAG_SCHEMA.dump(tags))
