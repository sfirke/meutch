import time

from app.utils.item_share import generate_item_share_token, verify_item_share_token
from tests.factories import ItemFactory


def test_verify_item_share_token_valid(app):
    with app.app_context():
        item = ItemFactory()
        token = generate_item_share_token(item)

        resolved_item, error = verify_item_share_token(token)

        assert error is None
        assert resolved_item.id == item.id


def test_verify_item_share_token_invalid(app):
    with app.app_context():
        resolved_item, error = verify_item_share_token('invalid-token')

        assert resolved_item is None
        assert error == 'invalid'


def test_verify_item_share_token_expired(app):
    with app.app_context():
        item = ItemFactory()
        token = generate_item_share_token(item)

        time.sleep(1)
        resolved_item, error = verify_item_share_token(token, max_age_seconds=0)

        assert resolved_item is None
        assert error == 'expired'



