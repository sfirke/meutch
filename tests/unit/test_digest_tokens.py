import time

from tests.factories import UserFactory
from app.utils.digest_tokens import generate_digest_manage_token, verify_digest_manage_token


def test_verify_digest_manage_token_valid(app):
    with app.app_context():
        user = UserFactory()
        token = generate_digest_manage_token(user)

        resolved_user, error = verify_digest_manage_token(token)

        assert error is None
        assert resolved_user.id == user.id


def test_verify_digest_manage_token_invalid(app):
    with app.app_context():
        resolved_user, error = verify_digest_manage_token('invalid-token')

        assert resolved_user is None
        assert error == 'invalid'


def test_verify_digest_manage_token_expired(app):
    with app.app_context():
        user = UserFactory()
        token = generate_digest_manage_token(user)

        time.sleep(1)
        resolved_user, error = verify_digest_manage_token(token, max_age_seconds=0)

        assert resolved_user is None
        assert error == 'expired'
