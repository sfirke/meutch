"""Item read and write endpoints for API v1."""

from flask import abort
from flask_jwt_extended import jwt_required
from sqlalchemy import and_, or_

from app import db
from app.api.v1 import bp
from app.api.v1.jwt_auth import current_user
from app.api.v1.operational import mutation_limit
from app.api.v1.parsing import load_query_data, load_request_data
from app.api.v1.responses import build_collection_response
from app.api.v1.schemas.items import (
    GiveawayInterestCollectionResponseSchema,
    GiveawayInterestCreateSchema,
    GiveawayInterestMutationResponseSchema,
    GiveawayInterestWithdrawResponseSchema,
    GiveawayItemResponseSchema,
    GiveawayRecipientChangeSchema,
    GiveawayRecipientMutationResponseSchema,
    GiveawayRecipientSelectionSchema,
    ItemDeleteResponseSchema,
    ItemDetailResponseSchema,
    ItemDetailSchema,
    ItemImageOrderSchema,
    ItemImagesUploadSchema,
    ItemSummarySchema,
    ItemUpdatePayloadSchema,
    ItemWritePayloadSchema,
)
from app.api.v1.schemas.query import ItemListQuerySchema
from app.models import GiveawayInterest, Item, ItemImage, Message
from app.services import giveaway_service, item_service
from app.services.exceptions import AuthorizationError, InformationalError
from app.utils.item_queries import build_find_results
from app.utils.item_visibility import build_item_access_state
from app.utils.pagination import ListPagination

ITEM_LIST_QUERY_SCHEMA = ItemListQuerySchema()
ITEM_SUMMARY_SCHEMA = ItemSummarySchema(many=True)
ITEM_DETAIL_SCHEMA = ItemDetailSchema()
ITEM_DETAIL_RESPONSE_SCHEMA = ItemDetailResponseSchema()
ITEM_CREATE_PAYLOAD_SCHEMA = ItemWritePayloadSchema()
ITEM_UPDATE_PAYLOAD_SCHEMA = ItemUpdatePayloadSchema()
ITEM_IMAGES_UPLOAD_SCHEMA = ItemImagesUploadSchema()
ITEM_IMAGE_ORDER_SCHEMA = ItemImageOrderSchema()
ITEM_DELETE_RESPONSE_SCHEMA = ItemDeleteResponseSchema()
GIVEAWAY_INTEREST_COLLECTION_RESPONSE_SCHEMA = GiveawayInterestCollectionResponseSchema()
GIVEAWAY_INTEREST_CREATE_SCHEMA = GiveawayInterestCreateSchema()
GIVEAWAY_RECIPIENT_SELECTION_SCHEMA = GiveawayRecipientSelectionSchema()
GIVEAWAY_RECIPIENT_CHANGE_SCHEMA = GiveawayRecipientChangeSchema()
GIVEAWAY_INTEREST_MUTATION_RESPONSE_SCHEMA = GiveawayInterestMutationResponseSchema()
GIVEAWAY_INTEREST_WITHDRAW_RESPONSE_SCHEMA = GiveawayInterestWithdrawResponseSchema()
GIVEAWAY_RECIPIENT_MUTATION_RESPONSE_SCHEMA = GiveawayRecipientMutationResponseSchema()
GIVEAWAY_ITEM_RESPONSE_SCHEMA = GiveawayItemResponseSchema()


def _build_item_access_state_or_raise(item):
    access_state = build_item_access_state(item, current_user)
    if not access_state["can_view"]:
        if access_state["claimed_unavailable"]:
            abort(404)
        raise AuthorizationError("You are not allowed to view this item.")

    return access_state


def _build_giveaway_interest_actions(item, interests):
    active_interest_count = sum(1 for interest in interests if interest.status == "active")
    is_pending_pickup = item.claim_status == "pending_pickup"
    return {
        "select_recipient": item.claim_status in [None, "unclaimed"] and active_interest_count > 0,
        "change_recipient": is_pending_pickup and active_interest_count > 0,
        "release_to_all": is_pending_pickup,
        "confirm_handoff": is_pending_pickup,
    }


def _annotate_giveaway_interests(item, owner_id):
    interests = (
        GiveawayInterest.query.filter(
            GiveawayInterest.item_id == item.id,
            GiveawayInterest.status.in_(["active", "selected"]),
        )
        .order_by(GiveawayInterest.created_at)
        .all()
    )

    interest_user_ids = {interest.user_id for interest in interests}
    all_messages = (
        Message.query.filter(
            Message.item_id == item.id,
            or_(
                and_(
                    Message.sender_id == owner_id,
                    Message.recipient_id.in_(interest_user_ids),
                ),
                and_(
                    Message.sender_id.in_(interest_user_ids),
                    Message.recipient_id == owner_id,
                ),
            ),
        )
        .order_by(Message.timestamp)
        .all()
    )
    messages_by_user = {}
    for message in all_messages:
        counterpart_id = (
            message.recipient_id if message.sender_id == owner_id else message.sender_id
        )
        messages_by_user.setdefault(counterpart_id, []).append(message)

    for interest in interests:
        conversation_messages = messages_by_user.get(interest.user_id, [])
        latest_message = conversation_messages[-1] if conversation_messages else None
        interest.api_conversation_message_id = latest_message.id if latest_message else None
        interest.api_unread_count = sum(
            1
            for message in conversation_messages
            if message.recipient_id == owner_id and not message.is_read
        )
        interest.api_message_count = len(conversation_messages)

    return interests


def _serialize_giveaway_interest_collection(item):
    interests = _annotate_giveaway_interests(item, current_user.id)
    item.api_interest_pool_count = len(interests)
    return GIVEAWAY_INTEREST_COLLECTION_RESPONSE_SCHEMA.dump(
        {
            "item": item,
            "actions": _build_giveaway_interest_actions(item, interests),
            "interests": interests,
        }
    )


def _build_item_response_payload(item):
    access_state = _build_item_access_state_or_raise(item)

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


def _prepare_item_resource(item):
    return _build_item_response_payload(item)["item"]


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
@mutation_limit()
def create_item():
    """Create a new item owned by the authenticated user."""
    data = load_request_data(ITEM_CREATE_PAYLOAD_SCHEMA)
    try:
        creation_result = item_service.create_item(
            current_user,
            data["name"],
            data["description"],
            data["category_id"],
            data["is_giveaway"],
            data["giveaway_visibility"],
            data["tags"],
            data["images"],
        )
    except ValueError as error:
        _raise_item_upload_error(error)

    return _serialize_item_response(creation_result.item), 201


@bp.patch("/items/<uuid:item_id>")
@jwt_required()
@mutation_limit()
def update_item(item_id):
    """Update an existing item owned by the authenticated user."""
    item = db.get_or_404(Item, item_id)
    _ensure_current_user_owns_item(item)
    data = load_request_data(ITEM_UPDATE_PAYLOAD_SCHEMA)
    item_service.update_item(
        item,
        data["name"],
        data["description"],
        data["category_id"],
        data["is_giveaway"],
        data["giveaway_visibility"],
        data["tags"],
        [],
        [],
        [],
    )
    return _serialize_item_response(item)


@bp.delete("/items/<uuid:item_id>")
@jwt_required()
@mutation_limit()
def delete_item(item_id):
    """Delete an item owned by the authenticated user."""
    item = db.get_or_404(Item, item_id)
    deleted_item = item_service.delete_item(item, current_user)
    return ITEM_DELETE_RESPONSE_SCHEMA.dump({"deleted": True, "item_id": deleted_item.id})


@bp.post("/items/<uuid:item_id>/images")
@jwt_required()
@mutation_limit("API_V1_IMAGE_WRITE_RATE_LIMIT")
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
@mutation_limit("API_V1_IMAGE_WRITE_RATE_LIMIT")
def reorder_item_images(item_id):
    """Persist a new deterministic image order for an existing item."""
    item = db.get_or_404(Item, item_id)
    data = load_request_data(ITEM_IMAGE_ORDER_SCHEMA)
    item_service.reorder_item_images(item, current_user, data["image_ids"])
    return _serialize_item_response(item)


@bp.delete("/items/<uuid:item_id>/images/<uuid:image_id>")
@jwt_required()
@mutation_limit("API_V1_IMAGE_WRITE_RATE_LIMIT")
def delete_item_image(item_id, image_id):
    """Delete one image from an existing item owned by the authenticated user."""
    item = db.get_or_404(Item, item_id)
    image = ItemImage.query.filter_by(id=image_id, item_id=item.id).first_or_404()
    item_service.delete_item_image(item, image, current_user)
    return _serialize_item_response(item)


@bp.get("/items/<uuid:item_id>/giveaway-interests")
@jwt_required()
def list_giveaway_interests(item_id):
    """Return owner-only giveaway interest-management state for one item."""
    item = db.get_or_404(Item, item_id)
    if not item.is_giveaway:
        abort(404)
    if item.owner_id != current_user.id:
        raise AuthorizationError("You do not have permission to manage this giveaway.")

    return _serialize_giveaway_interest_collection(item)


@bp.post("/items/<uuid:item_id>/interest")
@jwt_required()
@mutation_limit()
def express_interest(item_id):
    """Express interest in a giveaway item visible to the authenticated user."""
    item = db.get_or_404(Item, item_id)
    _build_item_access_state_or_raise(item)
    data = load_request_data(GIVEAWAY_INTEREST_CREATE_SCHEMA)
    interest = giveaway_service.express_interest(item, current_user.id, data["message"])
    return GIVEAWAY_INTEREST_MUTATION_RESPONSE_SCHEMA.dump(
        {"interest": interest, "item": _prepare_item_resource(item)}
    ), 201


@bp.delete("/items/<uuid:item_id>/interest")
@jwt_required()
@mutation_limit()
def withdraw_interest(item_id):
    """Withdraw the authenticated user's existing giveaway interest."""
    item = db.get_or_404(Item, item_id)
    _build_item_access_state_or_raise(item)
    giveaway_service.withdraw_interest(item, current_user.id)
    return GIVEAWAY_INTEREST_WITHDRAW_RESPONSE_SCHEMA.dump(
        {"withdrawn": True, "item": _prepare_item_resource(item)}
    )


@bp.post("/items/<uuid:item_id>/recipient/select")
@jwt_required()
@mutation_limit()
def select_giveaway_recipient(item_id):
    """Select a giveaway recipient as the item owner."""
    item = db.get_or_404(Item, item_id)
    data = load_request_data(GIVEAWAY_RECIPIENT_SELECTION_SCHEMA)
    selected_interest = giveaway_service.select_recipient(
        item,
        current_user.id,
        data["selection_method"],
        data["user_id"],
    )
    return GIVEAWAY_RECIPIENT_MUTATION_RESPONSE_SCHEMA.dump(
        {
            "item": _prepare_item_resource(item),
            "selected_interest": selected_interest,
        }
    )


@bp.post("/items/<uuid:item_id>/recipient/change")
@jwt_required()
@mutation_limit()
def change_giveaway_recipient(item_id):
    """Change the currently selected giveaway recipient as the item owner."""
    item = db.get_or_404(Item, item_id)
    data = load_request_data(GIVEAWAY_RECIPIENT_CHANGE_SCHEMA)
    selected_interest = giveaway_service.change_recipient(
        item,
        current_user.id,
        data["selection_method"],
        data["user_id"],
    )
    return GIVEAWAY_RECIPIENT_MUTATION_RESPONSE_SCHEMA.dump(
        {
            "item": _prepare_item_resource(item),
            "selected_interest": selected_interest,
        }
    )


@bp.post("/items/<uuid:item_id>/release-to-all")
@jwt_required()
@mutation_limit()
def release_giveaway_to_all(item_id):
    """Return a pending-pickup giveaway to the active interest pool."""
    item = db.get_or_404(Item, item_id)
    giveaway_service.release_to_all(item, current_user.id)
    return GIVEAWAY_ITEM_RESPONSE_SCHEMA.dump({"item": _prepare_item_resource(item)})


@bp.post("/items/<uuid:item_id>/confirm-handoff")
@jwt_required()
@mutation_limit()
def confirm_giveaway_handoff(item_id):
    """Mark a pending-pickup giveaway handed off as the item owner."""
    item = db.get_or_404(Item, item_id)
    giveaway_service.confirm_handoff(item, current_user.id)
    return GIVEAWAY_ITEM_RESPONSE_SCHEMA.dump({"item": _prepare_item_resource(item)})
