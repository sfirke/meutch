"""Item read endpoints for API v1."""

from flask_jwt_extended import jwt_required

from app import db
from app.api.v1 import bp
from app.api.v1.jwt_auth import current_user
from app.api.v1.parsing import load_query_data
from app.api.v1.responses import build_collection_response
from app.api.v1.schemas.items import ItemDetailResponseSchema, ItemSummarySchema
from app.api.v1.schemas.query import ItemListQuerySchema
from app.models import GiveawayInterest, Item
from app.services.exceptions import AuthorizationError
from app.utils.item_queries import build_find_results
from app.utils.item_visibility import build_item_access_state
from app.utils.pagination import ListPagination

ITEM_LIST_QUERY_SCHEMA = ItemListQuerySchema()
ITEM_SUMMARY_SCHEMA = ItemSummarySchema(many=True)
ITEM_DETAIL_RESPONSE_SCHEMA = ItemDetailResponseSchema()


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
    access_state = build_item_access_state(item, current_user)
    if not access_state["can_view"]:
        if access_state["claimed_unavailable"]:
            raise AuthorizationError("This giveaway is no longer available.")
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
        item.api_interested_count = sum(
            1 for interest in item.giveaway_interests if interest.status == "active"
        )

    return ITEM_DETAIL_RESPONSE_SCHEMA.dump(
        {
            "item": item,
            "viewer": {
                "is_owner": access_state["is_owner"],
                "shares_circle_with_owner": access_state["shares_circle_with_owner"],
                "is_active_borrower": access_state["is_active_borrower"],
            },
        }
    )
