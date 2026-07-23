import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError

from app import db
from app.models import User
from app.services import location_service
from app.services.exceptions import ConflictError
from app.utils.email import send_confirmation_email, send_password_reset_email

logger = logging.getLogger(__name__)

CONFIRMATION_TOKEN_TTL = timedelta(hours=24)
PASSWORD_RESET_TOKEN_TTL = timedelta(hours=1)

LOGIN_STATUS_SUCCESS = "success"
LOGIN_STATUS_INVALID_CREDENTIALS = "invalid_credentials"
LOGIN_STATUS_UNCONFIRMED = "unconfirmed"

CONFIRM_EMAIL_STATUS_CONFIRMED = "confirmed"
CONFIRM_EMAIL_STATUS_EXPIRED = "expired"
CONFIRM_EMAIL_STATUS_INVALID_LINK = "invalid_link"
CONFIRM_EMAIL_STATUS_INVALID_TOKEN = "invalid_token"

RESEND_CONFIRMATION_STATUS_SENT = "sent"
RESEND_CONFIRMATION_STATUS_ALREADY_CONFIRMED = "already_confirmed"
RESEND_CONFIRMATION_STATUS_NOT_FOUND = "not_found"
RESEND_CONFIRMATION_STATUS_SEND_FAILED = "send_failed"

PASSWORD_RESET_REQUEST_STATUS_SENT = "sent"
PASSWORD_RESET_REQUEST_STATUS_NOT_FOUND = "not_found"
PASSWORD_RESET_REQUEST_STATUS_SEND_FAILED = "send_failed"

PASSWORD_RESET_TOKEN_STATUS_VALID = "valid"
PASSWORD_RESET_TOKEN_STATUS_INVALID = "invalid"
PASSWORD_RESET_TOKEN_STATUS_EXPIRED = "expired"

PASSWORD_RESET_STATUS_SUCCESS = "success"
PASSWORD_RESET_STATUS_INVALID = "invalid"
PASSWORD_RESET_STATUS_EXPIRED = "expired"


@dataclass(frozen=True)
class ExistingEmailResult:
    exists: bool
    is_confirmed: bool = False


def check_existing_email(email):
    """Check if an email is already registered and whether the user is confirmed.

    Returns an ExistingEmailResult with:
    - exists: whether the email is registered
    - is_confirmed: whether the existing user has confirmed their email
        (only meaningful if exists is True)
    """
    user = _get_user_by_email(email)
    if user is None:
        return ExistingEmailResult(exists=False)
    return ExistingEmailResult(exists=True, is_confirmed=user.is_confirmed())


@dataclass
class RegistrationResult:
    user: User
    email_sent: bool
    location_method: str
    geocoding_failed: bool


@dataclass
class AuthenticationResult:
    status: str
    user: User | None = None


@dataclass
class AuthWorkflowResult:
    status: str
    user: User | None = None
    email_sent: bool | None = None


def _get_user_by_email(email):
    return User.query.filter(db.func.lower(User.email) == db.func.lower(email)).first()


def _normalize_utc(timestamp):
    if timestamp is None:
        return None

    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=UTC)

    return timestamp


def _is_expired(sent_at, ttl):
    normalized_sent_at = _normalize_utc(sent_at)
    if normalized_sent_at is None:
        return False

    return datetime.now(UTC) - normalized_sent_at > ttl


def register_user(
    *,
    email,
    first_name,
    last_name,
    password,
    digest_frequency,
    location_method,
    next_url=None,
    street=None,
    city=None,
    state=None,
    zip_code=None,
    country=None,
    latitude=None,
    longitude=None,
):
    user = User(
        email=email.lower(),
        first_name=first_name,
        last_name=last_name,
        digest_frequency=digest_frequency,
    )
    user.set_password(password)

    location_status = location_service.apply_registration_location(
        user,
        location_method=location_method,
        street=street,
        city=city,
        state=state,
        zip_code=zip_code,
        country=country,
        latitude=latitude,
        longitude=longitude,
    )

    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        existing = check_existing_email(email)
        if existing.is_confirmed:
            raise ConflictError(
                "An account with this email is already registered. "
                "If this is your account, use the forgot password link to regain access.",
                details={"email_status": "confirmed"},
            ) from None
        else:
            raise ConflictError(
                "An account with this email exists but hasn't been confirmed yet. "
                "Please check your email for the confirmation link or request a new one.",
                details={"email_status": "unconfirmed"},
            ) from None
    email_sent = send_confirmation_email(user, next_url=next_url)
    return RegistrationResult(
        user=user,
        email_sent=email_sent,
        location_method=location_method,
        geocoding_failed=(
            location_status != location_service.LOCATION_UPDATE_STATUS_SUCCESS
            and location_method == "address"
        ),
    )


def authenticate_user(email, password):
    user = _get_user_by_email(email)
    if not user or not user.check_password(password):
        return AuthenticationResult(status=LOGIN_STATUS_INVALID_CREDENTIALS)

    if not user.is_confirmed():
        return AuthenticationResult(status=LOGIN_STATUS_UNCONFIRMED, user=user)

    user.last_login = datetime.now(UTC)
    db.session.commit()
    return AuthenticationResult(status=LOGIN_STATUS_SUCCESS, user=user)


def confirm_email_token(token):
    user = User.query.filter_by(email_confirmation_token=token).first()
    if not user:
        return AuthWorkflowResult(status=CONFIRM_EMAIL_STATUS_INVALID_LINK)

    if _is_expired(user.email_confirmation_sent_at, CONFIRMATION_TOKEN_TTL):
        return AuthWorkflowResult(status=CONFIRM_EMAIL_STATUS_EXPIRED, user=user)

    if user.confirm_email(token):
        db.session.commit()
        return AuthWorkflowResult(status=CONFIRM_EMAIL_STATUS_CONFIRMED, user=user)

    return AuthWorkflowResult(status=CONFIRM_EMAIL_STATUS_INVALID_TOKEN, user=user)


def resend_confirmation_email_for_user(email):
    user = _get_user_by_email(email)
    if not user:
        return AuthWorkflowResult(status=RESEND_CONFIRMATION_STATUS_NOT_FOUND)

    if user.is_confirmed():
        return AuthWorkflowResult(
            status=RESEND_CONFIRMATION_STATUS_ALREADY_CONFIRMED,
            user=user,
        )

    email_sent = send_confirmation_email(user)
    status = (
        RESEND_CONFIRMATION_STATUS_SENT if email_sent else RESEND_CONFIRMATION_STATUS_SEND_FAILED
    )
    return AuthWorkflowResult(status=status, user=user, email_sent=email_sent)


def request_password_reset(email):
    user = _get_user_by_email(email)
    if not user:
        return AuthWorkflowResult(status=PASSWORD_RESET_REQUEST_STATUS_NOT_FOUND)

    email_sent = send_password_reset_email(user)
    status = (
        PASSWORD_RESET_REQUEST_STATUS_SENT
        if email_sent
        else PASSWORD_RESET_REQUEST_STATUS_SEND_FAILED
    )
    return AuthWorkflowResult(status=status, user=user, email_sent=email_sent)


def get_password_reset_token_status(token):
    user = User.query.filter_by(password_reset_token=token).first()
    if not user:
        return AuthWorkflowResult(status=PASSWORD_RESET_TOKEN_STATUS_INVALID)

    if _is_expired(user.password_reset_sent_at, PASSWORD_RESET_TOKEN_TTL):
        return AuthWorkflowResult(status=PASSWORD_RESET_TOKEN_STATUS_EXPIRED, user=user)

    return AuthWorkflowResult(status=PASSWORD_RESET_TOKEN_STATUS_VALID, user=user)


def reset_password(token, new_password):
    token_status = get_password_reset_token_status(token)
    if token_status.status == PASSWORD_RESET_TOKEN_STATUS_INVALID:
        return AuthWorkflowResult(status=PASSWORD_RESET_STATUS_INVALID)

    if token_status.status == PASSWORD_RESET_TOKEN_STATUS_EXPIRED:
        return AuthWorkflowResult(status=PASSWORD_RESET_STATUS_EXPIRED, user=token_status.user)

    user = token_status.user
    if user.reset_password(token, new_password):
        db.session.commit()
        return AuthWorkflowResult(status=PASSWORD_RESET_STATUS_SUCCESS, user=user)

    return AuthWorkflowResult(status=PASSWORD_RESET_STATUS_INVALID, user=user)
