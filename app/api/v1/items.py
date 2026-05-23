"""Item read and write endpoints for API v1."""

from flask import abort
from flask_jwt_extended import jwt_required

from app import db
from app.api.v1 import bp
from app.api.v1.jwt_auth import current_user
from app.api.v1.parsing import load_query_data, load_request_data
from app.api.v1.responses import build_collection_response
from app.api.v1.schemas.items import (
    ItemDeleteResponseSchema,
    ItemDetailResponseSchema,
    ItemImageOrderSchema,
    ItemImagesUploadSchema,
    ItemSummarySchema,
    ItemUpdatePayloadSchema,
    ItemWritePayloadSchema,
)
from app.api.v1.schemas.query import ItemListQuerySchema
from app.models import GiveawayInterest, Item, ItemImage
from app.services import item_service
from app.services.exceptions import AuthorizationError, InformationalError
from app.utils.item_queries import build_find_results
from app.utils.item_visibility import build_item_access_state
from app.utils.pagination import ListPagination

ITEM_LIST_QUERY_SCHEMA = ItemListQuerySchema()
ITEM_SUMMARY_SCHEMA = ItemSummarySchema(many=True)
ITEM_DETAIL_RESPONSE_SCHEMA = ItemDetailResponseSchema()
ITEM_CREATE_PAYLOAD_SCHEMA = ItemWritePayloadSchema()
ITEM_UPDATE_PAYLOAD_SCHEMA = ItemUpdatePayloadSchema()
ITEM_IMAGES_UPLOAD_SCHEMA = ItemImagesUploadSchema()
ITEM_IMAGE_ORDER_SCHEMA = ItemImageOrderSchema()
ITEM_DELETE_RESPONSE_SCHEMA = ItemDeleteResponseSchema()


def _build_item_response_payload(item):
    access_state = build_item_access_state(item, current_user)
    if not access_state["can_view"]:
        if access_state["claimed_unavailable"]:
            abort(404)
        raise AuthorizationError("You are not allowed to view this item.")

    viewer_interest = None
    if item.is_giveaway:
        viewer_interest = GiveawayInterest.query.filter_by(
            item_id=item.id,
            user_id=current_user.id,
        ).first()

    item.api_viewer_interest_status = viewer_interest.status if viewer_interest else None
    item.api_interested_count = None
    if item.is_giveaway and item.owner_id == current_user.id:
        item.api_interested_count = GiveawayInterest.query.filter_by(
            item_id=item.id,
            status="active",
        ).count()

    return {
        "item": item,
        "viewer": {
            "is_owner": access_state["is_owner"],
            "shares_circle_with_owner": access_state["shares_circle_with_owner"],
            "is_active_borrower": access_state["is_active_borrower"],
        },
    }


def _serialize_item_response(item):
    return ITEM_DETAIL_RESPONSE_SCHEMA.dump(_build_item_response_payload(item))


def _ensure_current_user_owns_item(item):
    if item.owner_id != current_user.id:
        raise AuthorizationError("You can only manage your own items.")


def _raise_item_upload_error(error):
    raise InformationalError("One or more image uploads failed.") from error


@bp.get("/items")
@jwt_required()
def list_items():
    """Return discoverable items for the authenticated user."""
    query_data = load_query_data(ITEM_LIST_QUERY_SCHEMA)
    find_results = build_find_results(
        current_user,
        query=query_data["q"],
        selected_category_ids=query_data["categories"],
        selected_circle_ids=query_data["circles"],
        item_type=query_data["item_type"],
        sort_by=query_data["sort"],
        page=query_data["page"],
        per_page=query_data["per_page"],
    )

    pagination = find_results["pagination"]
    if pagination is None:
        pagination = ListPagination(
            items=find_results["items"],
            page=query_data["page"],
            per_page=query_data["per_page"],
        )

    return build_collection_response(
        "items",
        ITEM_SUMMARY_SCHEMA.dump(pagination.items),
        pagination=pagination,
    )


@bp.get("/items/<uuid:item_id>")
@jwt_required()
def get_item(item_id):
    """Return item details when the authenticated user can view them."""
    item = db.get_or_404(Item, item_id)
    return _serialize_item_response(item)


@bp.post("/items")
@jwt_required()
def create_item():
    """Create a new item owned by the authenticated user."""
    data = load_request_data(ITEM_CREATE_PAYLOAD_SCHEMA)
    try:
        creation_result = item_service.create_item(
            current_user,
            data["name"],
            data.get("description"),
            data["category_id"],
            data["is_giveaway"],
            data.get("giveaway_visibility"),
            data["tags"],
            data["images"],
        )
    except ValueError as error:
        _raise_item_upload_error(error)

    return _serialize_item_response(creation_result.item), 201


@bp.patch("/items/<uuid:item_id>")
@jwt_required()
def update_item(item_id):
    """Update an existing item owned by the authenticated user."""
    item = db.get_or_404(Item, item_id)
    _ensure_current_user_owns_item(item)
    data = load_request_data(ITEM_UPDATE_PAYLOAD_SCHEMA)
    item_service.update_item(
        item,
        data["name"],
        data.get("description"),
        data["category_id"],
        data["is_giveaway"],
        data.get("giveaway_visibility"),
        data["tags"],
        [],
        [],
        [],
    )
    return _serialize_item_response(item)


@bp.delete("/items/<uuid:item_id>")
@jwt_required()
def delete_item(item_id):
    """Delete an item owned by the authenticated user."""
    item = db.get_or_404(Item, item_id)
    deleted_item = item_service.delete_item(item, current_user)
    return ITEM_DELETE_RESPONSE_SCHEMA.dump({"deleted": True, "item_id": deleted_item.id})


@bp.post("/items/<uuid:item_id>/images")
@jwt_required()
def add_item_images(item_id):
    """Append images to an existing item owned by the authenticated user."""
    item = db.get_or_404(Item, item_id)
    data = load_request_data(ITEM_IMAGES_UPLOAD_SCHEMA)
    try:
        item_service.append_item_images(item, current_user, data["images"])
    except ValueError as error:
        _raise_item_upload_error(error)
    return _serialize_item_response(item)


@bp.patch("/items/<uuid:item_id>/images/order")
@jwt_required()
def reorder_item_images(item_id):
    """Persist a new deterministic image order for an existing item."""
    item = db.get_or_404(Item, item_id)
    data = load_request_data(ITEM_IMAGE_ORDER_SCHEMA)
    item_service.reorder_item_images(item, current_user, data["image_ids"])
    return _serialize_item_response(item)


@bp.delete("/items/<uuid:item_id>/images/<uuid:image_id>")
@jwt_required()
def delete_item_image(item_id, image_id):
    """Delete one image from an existing item owned by the authenticated user."""
    item = db.get_or_404(Item, item_id)
    image = ItemImage.query.filter_by(id=image_id, item_id=item.id).first_or_404()
    item_service.delete_item_image(item, image, current_user)
    return _serialize_item_response(item)
