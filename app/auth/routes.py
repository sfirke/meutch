import logging
from urllib.parse import urljoin, urlparse

from flask import flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_user, logout_user

from app.auth import bp as auth
from app.auth import bp as auth_bp
from app.forms import (
    ForgotPasswordForm,
    LoginForm,
    RegistrationForm,
    ResendConfirmationForm,
    ResetPasswordForm,
)
from app.services import auth_service

logger = logging.getLogger(__name__)
logger.debug("Loading app.auth.routes")

CONFIRMATION_PAGE_SESSION_KEY = "confirmation_page"
CONFIRMATION_SOURCE_EXPIRED = "expired"
CONFIRMATION_SOURCE_LOGIN = "login"
CONFIRMATION_SOURCE_MANUAL = "manual"
CONFIRMATION_SOURCE_REGISTER = "registration"
CONFIRMATION_SOURCE_RESENT = "resent"
CONFIRMATION_SOURCES = {
    CONFIRMATION_SOURCE_EXPIRED,
    CONFIRMATION_SOURCE_LOGIN,
    CONFIRMATION_SOURCE_MANUAL,
    CONFIRMATION_SOURCE_REGISTER,
    CONFIRMATION_SOURCE_RESENT,
}


def _is_safe_url(target):
    """
    Check if a URL is safe for redirects (prevents open redirect vulnerabilities).
    A URL is safe if it's relative or points to the same host as the application.
    """
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ("http", "https") and ref_url.netloc == test_url.netloc


def _clear_confirmation_page_state():
    session.pop(CONFIRMATION_PAGE_SESSION_KEY, None)


def _set_confirmation_page_state(*, email=None, source, email_sent=None, show_resend=False):
    state = {
        "email": email.lower() if email else None,
        "source": source,
        "show_resend": show_resend,
    }
    if email_sent is not None:
        state["email_sent"] = email_sent
    session[CONFIRMATION_PAGE_SESSION_KEY] = state


def _get_confirmation_page_state():
    state = session.get(CONFIRMATION_PAGE_SESSION_KEY)
    if not isinstance(state, dict):
        return {
            "email": None,
            "email_sent": None,
            "show_resend": True,
            "source": CONFIRMATION_SOURCE_MANUAL,
        }

    source = state.get("source")
    if source not in CONFIRMATION_SOURCES:
        source = CONFIRMATION_SOURCE_MANUAL

    email_sent = state.get("email_sent")
    if email_sent not in (True, False):
        email_sent = None

    default_show_resend = source != CONFIRMATION_SOURCE_REGISTER or email_sent is False
    return {
        "email": state.get("email"),
        "email_sent": email_sent,
        "show_resend": bool(state.get("show_resend", default_show_resend)),
        "source": source,
    }


def _build_confirmation_page_context(form, *, force_show_resend=False):
    page_state = _get_confirmation_page_state()
    if page_state["email"] and not form.email.data:
        form.email.data = page_state["email"]

    show_resend = page_state["show_resend"] or force_show_resend or bool(form.errors)
    return {
        "confirmation_email": form.email.data or page_state["email"],
        "confirmation_source": page_state["source"],
        "email_delivery_status": page_state["email_sent"],
        "show_resend": show_resend,
    }


@auth.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    form = RegistrationForm()
    if form.validate_on_submit():
        next_page = request.args.get("next")
        safe_next = next_page if (next_page and _is_safe_url(next_page)) else None
        registration_result = auth_service.register_user(
            email=form.email.data,
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            password=form.password.data,
            digest_frequency=form.digest_frequency.data,
            location_method=form.location_method.data,
            next_url=safe_next,
            street=form.street.data,
            city=form.city.data,
            state=form.state.data,
            zip_code=form.zip_code.data,
            country=form.country.data,
            latitude=form.latitude.data,
            longitude=form.longitude.data,
        )

        if registration_result.location_method == "skip":
            flash(
                "Your account has been created! You can add your location later on your profile page "
                "to see distances to items and help others find items near you.",
                "info",
            )
        elif registration_result.geocoding_failed:
            flash(
                "Your account has been created, but we couldn't determine your location from the address provided. "
                "You can try the option to enter coordinates directly, or update your location later on your profile page to see distances to items.",
                "warning",
            )

        _set_confirmation_page_state(
            email=registration_result.user.email,
            source=CONFIRMATION_SOURCE_REGISTER,
            email_sent=registration_result.email_sent,
            show_resend=not registration_result.email_sent,
        )

        if not registration_result.email_sent:
            flash(
                "Your account has been created, but we could not send the confirmation email yet. You can try again below.",
                "warning",
            )

        return redirect(url_for("auth.resend_confirmation"))

    return render_template("auth/register.html", title="Register", form=form)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        authentication_result = auth_service.authenticate_user(
            form.email.data,
            form.password.data,
        )
        if authentication_result.status == auth_service.LOGIN_STATUS_SUCCESS:
            _clear_confirmation_page_state()
            login_user(authentication_result.user, remember=form.remember_device.data)
            next_page = request.args.get("next")
            if next_page and _is_safe_url(next_page):
                return redirect(next_page)
            return redirect(url_for("main.index"))

        if authentication_result.status == auth_service.LOGIN_STATUS_UNCONFIRMED:
            _set_confirmation_page_state(
                email=authentication_result.user.email,
                source=CONFIRMATION_SOURCE_LOGIN,
                show_resend=True,
            )
            return redirect(url_for("auth.resend_confirmation"))

        flash("Invalid email or password", "danger")
    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout")
def logout():
    _clear_confirmation_page_state()
    logout_user()
    return redirect(url_for("main.index"))


@auth_bp.route("/confirm/<token>")
def confirm_email(token):
    """Confirm user email with token"""

    confirmation_result = auth_service.confirm_email_token(token)
    if confirmation_result.status == auth_service.CONFIRM_EMAIL_STATUS_INVALID_LINK:
        flash("Invalid or expired confirmation link.", "danger")
        return redirect(url_for("auth.login"))

    if confirmation_result.status == auth_service.CONFIRM_EMAIL_STATUS_EXPIRED:
        _set_confirmation_page_state(
            email=confirmation_result.user.email,
            source=CONFIRMATION_SOURCE_EXPIRED,
            email_sent=True,
            show_resend=True,
        )
        return redirect(url_for("auth.resend_confirmation"))

    if confirmation_result.status == auth_service.CONFIRM_EMAIL_STATUS_CONFIRMED:
        _clear_confirmation_page_state()
        flash("Your email has been confirmed! You can now log in.", "success")
        next_page = request.args.get("next")
        if next_page and _is_safe_url(next_page):
            return redirect(url_for("auth.login", next=next_page))
        return redirect(url_for("auth.login"))
    else:
        flash("Invalid confirmation link.", "danger")
        return redirect(url_for("auth.login"))


@auth_bp.route("/resend-confirmation", methods=["GET", "POST"])
def resend_confirmation():
    """Resend confirmation email"""
    form = ResendConfirmationForm()
    render_context = _build_confirmation_page_context(form)

    if form.validate_on_submit():
        resend_result = auth_service.resend_confirmation_email_for_user(form.email.data)
        if resend_result.status == auth_service.RESEND_CONFIRMATION_STATUS_NOT_FOUND:
            _set_confirmation_page_state(
                email=form.email.data,
                source=CONFIRMATION_SOURCE_MANUAL,
                show_resend=True,
            )
            flash("We could not find an account with that email address.", "danger")
            return redirect(url_for("auth.resend_confirmation"))

        if resend_result.status == auth_service.RESEND_CONFIRMATION_STATUS_ALREADY_CONFIRMED:
            _clear_confirmation_page_state()
            flash("That email address is already confirmed. You can log in.", "info")
            return redirect(url_for("auth.login"))

        if resend_result.status == auth_service.RESEND_CONFIRMATION_STATUS_SENT:
            _set_confirmation_page_state(
                email=resend_result.user.email,
                source=CONFIRMATION_SOURCE_RESENT,
                email_sent=True,
                show_resend=True,
            )
            flash("We sent a new confirmation email. Check your email for the link.", "success")
        else:
            _set_confirmation_page_state(
                email=form.email.data,
                source=CONFIRMATION_SOURCE_MANUAL,
                email_sent=False,
                show_resend=True,
            )
            flash(
                "We could not send a confirmation email right now. Please try again.",
                "danger",
            )

        return redirect(url_for("auth.resend_confirmation"))

    if request.method == "POST":
        render_context = _build_confirmation_page_context(form, force_show_resend=True)

    return render_template("auth/resend_confirmation.html", form=form, **render_context)


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    """Request password reset"""
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    form = ForgotPasswordForm()
    if form.validate_on_submit():
        password_reset_request = auth_service.request_password_reset(form.email.data)
        if password_reset_request.status == auth_service.PASSWORD_RESET_REQUEST_STATUS_SENT:
            flash("Password reset instructions have been sent to your email.", "info")
        elif (
            password_reset_request.status == auth_service.PASSWORD_RESET_REQUEST_STATUS_SEND_FAILED
        ):
            flash("Error sending password reset email. Please try again later.", "error")
        else:
            flash(
                "If an account with that email exists, password reset instructions have been sent.",
                "info",
            )

        return redirect(url_for("auth.login"))

    return render_template("auth/forgot_password.html", form=form)


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    """Reset password with token"""
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    password_reset_token = auth_service.get_password_reset_token_status(token)
    if password_reset_token.status == auth_service.PASSWORD_RESET_TOKEN_STATUS_INVALID:
        flash("Invalid or expired reset link.", "danger")
        return redirect(url_for("auth.forgot_password"))

    if password_reset_token.status == auth_service.PASSWORD_RESET_TOKEN_STATUS_EXPIRED:
        flash("Reset link has expired. Please request a new one.", "danger")
        return redirect(url_for("auth.forgot_password"))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        reset_result = auth_service.reset_password(token, form.password.data)
        if reset_result.status == auth_service.PASSWORD_RESET_STATUS_SUCCESS:
            flash("Your password has been reset successfully. You can now log in.", "success")
            return redirect(url_for("auth.login"))

        flash("Invalid reset token. Please request a new password reset.", "danger")
        return redirect(url_for("auth.forgot_password"))

    return render_template("auth/reset_password.html", form=form)
