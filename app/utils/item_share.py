from app import db
from app.models import Item
from app.utils.digest_tokens import generate_signed_token, verify_signed_token


ITEM_SHARE_TOKEN_SALT = 'item-share'
ITEM_SHARE_TOKEN_MAX_AGE_DAYS = 30
ITEM_SHARE_TOKEN_MAX_AGE_SECONDS = 60 * 60 * 24 * ITEM_SHARE_TOKEN_MAX_AGE_DAYS


def item_supports_share_links(item):
    return bool(item and item.owner_id and not item.is_giveaway)


def generate_item_share_token(item):
    if not item_supports_share_links(item):
        raise ValueError('Only regular items can be shared with item share links.')

    return generate_signed_token(
        {'item_id': str(item.id)},
        salt=ITEM_SHARE_TOKEN_SALT,
    )


def verify_item_share_token(token, max_age_seconds=ITEM_SHARE_TOKEN_MAX_AGE_SECONDS):
    payload, error = verify_signed_token(
        token,
        salt=ITEM_SHARE_TOKEN_SALT,
        max_age_seconds=max_age_seconds,
    )
    if error:
        return None, error

    item_id = payload.get('item_id')
    if not item_id:
        return None, 'invalid'

    item = db.session.get(Item, item_id)
    if not item or not item_supports_share_links(item):
        return None, 'invalid'

    return item, None


def token_grants_item_access(token, item):
    if not token or not item_supports_share_links(item):
        return False

    shared_item, error = verify_item_share_token(token)
    return error is None and shared_item.id == item.id
