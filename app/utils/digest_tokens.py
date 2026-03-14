from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from flask import current_app

from app import db
from app.models import User


DIGEST_MANAGE_TOKEN_SALT = 'digest-manage'
DIGEST_MANAGE_TOKEN_MAX_AGE_SECONDS = 60 * 60 * 24 * 30


def _get_serializer():
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'])


def generate_digest_manage_token(user):
    serializer = _get_serializer()
    return serializer.dumps({'user_id': str(user.id), 'email': user.email}, salt=DIGEST_MANAGE_TOKEN_SALT)


def verify_digest_manage_token(token, max_age_seconds=DIGEST_MANAGE_TOKEN_MAX_AGE_SECONDS):
    serializer = _get_serializer()

    try:
        payload = serializer.loads(token, salt=DIGEST_MANAGE_TOKEN_SALT, max_age=max_age_seconds)
    except SignatureExpired:
        return None, 'expired'
    except BadSignature:
        return None, 'invalid'

    user_id = payload.get('user_id')
    email = payload.get('email')
    if not user_id or not email:
        return None, 'invalid'

    user = db.session.get(User, user_id)
    if not user:
        return None, 'invalid'

    if user.email != email:
        return None, 'invalid'

    return user, None
