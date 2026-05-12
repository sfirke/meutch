import logging
from urllib.parse import urljoin, urlparse

from flask import flash, redirect, render_template, request, url_for
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


def _is_safe_url(target):
    """
    Check if a URL is safe for redirects (prevents open redirect vulnerabilities).
    A URL is safe if it's relative or points to the same host as the application.
    """
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ("http", "https") and ref_url.netloc == test_url.netloc


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

        if registration_result.email_sent:
            flash("A confirmation email has been sent to you by email.", "info")
        else:
            flash("Error sending confirmation email. Please try again.", "error")

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
            login_user(authentication_result.user, remember=form.remember_device.data)
            next_page = request.args.get("next")
            if next_page and _is_safe_url(next_page):
                return redirect(next_page)
            return redirect(url_for("main.index"))

        if authentication_result.status == auth_service.LOGIN_STATUS_UNCONFIRMED:
            flash(
                "Please confirm your email address before logging in. Check your email for the confirmation link.",
                "warning",
            )
            return render_template("auth/login.html", form=form)

        flash("Invalid email or password", "danger")
    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout")
def logout():
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
        flash("Confirmation link has expired. Please request a new one.", "danger")
        return redirect(url_for("auth.resend_confirmation"))

    if confirmation_result.status == auth_service.CONFIRM_EMAIL_STATUS_CONFIRMED:
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

    if form.validate_on_submit():
        resend_result = auth_service.resend_confirmation_email_for_user(form.email.data)
        if resend_result.status == auth_service.RESEND_CONFIRMATION_STATUS_NOT_FOUND:
            flash("No account found with that email address.", "danger")
            return render_template("auth/resend_confirmation.html", form=form)

        if resend_result.status == auth_service.RESEND_CONFIRMATION_STATUS_ALREADY_CONFIRMED:
            flash("Your email is already confirmed. You can log in.", "info")
            return redirect(url_for("auth.login"))

        if resend_result.status == auth_service.RESEND_CONFIRMATION_STATUS_SENT:
            flash("A new confirmation email has been sent. Please check your email.", "success")
        else:
            flash("Error sending confirmation email. Please try again later.", "danger")

        return render_template("auth/resend_confirmation.html", form=form)

    return render_template("auth/resend_confirmation.html", form=form)


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
