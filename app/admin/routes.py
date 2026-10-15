"""Admin panel routes for user management and monitoring"""

import logging
from datetime import UTC, datetime, timedelta

from flask import current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import false, func
from sqlalchemy.orm import joinedload

from app import db
from app.admin import bp
from app.auth.decorators import admin_required
from app.forms import EmptyForm
from app.models import ActivityLog, AdminAction, Item, User
from app.services import account_service, active_months_service
from app.utils.activity_log import oldest_entry_at

logger = logging.getLogger(__name__)


def _monthly_active_users_series():
    """Build monthly active user counts beginning January 2026."""
    first_month = datetime(2026, 1, 1, tzinfo=UTC)
    current_month = active_months_service.month_start(datetime.now(UTC))
    counts_by_month = active_months_service.monthly_active_user_counts(
        first_month, active_months_service.next_month(current_month)
    )

    series = []
    month_cursor = first_month
    while month_cursor <= current_month:
        series.append(
            {
                "label": month_cursor.strftime("%b %Y"),
                "month_start": month_cursor.date().isoformat(),
                "count": counts_by_month.get((month_cursor.year, month_cursor.month), 0),
            }
        )
        month_cursor = active_months_service.next_month(month_cursor)

    return series


@bp.route("/")
@admin_required
def dashboard():
    """Admin dashboard with metrics and user management"""
    active_tab = request.args.get("active_tab", "users", type=str)
    # Get pagination and sorting parameters
    page = request.args.get("page", 1, type=int)
    sort_by = request.args.get("sort_by", "created_at", type=str)
    order = request.args.get("order", "desc", type=str)
    per_page = 20

    if active_tab not in ["users", "analytics"]:
        active_tab = "users"

    # Validate sort parameters
    valid_sorts = ["email", "created_at", "last_login", "full_name"]
    if sort_by not in valid_sorts:
        sort_by = "created_at"
    if order not in ["asc", "desc"]:
        order = "desc"

    # Calculate metrics
    total_users = User.query.filter_by(is_deleted=False).count()

    # Recently active users (users who have logged in within last 30 days)
    thirty_days_ago = datetime.now(UTC) - timedelta(days=30)
    recent_users = User.query.filter(
        User.is_deleted.is_(false()), User.last_login >= thirty_days_ago
    ).count()

    total_items = Item.query.count()
    mau_series = _monthly_active_users_series()
    secondary_sort = User.last_name.desc()

    # Build sort order
    if sort_by == "email":
        sort_column = User.email
    elif sort_by == "last_login":
        # Sort nulls last for last_login
        if order == "desc":
            sort_column = User.last_login.desc().nullslast()
        else:
            sort_column = User.last_login.asc().nullslast()
    elif sort_by == "full_name":
        # Sort by first name then last name
        if order == "desc":
            sort_column = User.first_name.desc()
            secondary_sort = User.last_name.desc()
        else:
            sort_column = User.first_name.asc()
            secondary_sort = User.last_name.asc()
    else:  # created_at
        sort_column = User.created_at

    # Apply ascending/descending order (unless already done for last_login or full_name)
    if sort_by not in ["last_login", "full_name"]:
        if order == "desc":
            sort_column = sort_column.desc()
        else:
            sort_column = sort_column.asc()

    # Add item count to each user with dynamic sorting
    # pylint: disable=not-callable
    query = (
        db.session.query(User, func.count(Item.id).label("item_count"))
        .outerjoin(Item, Item.owner_id == User.id)
        .filter(User.is_deleted.is_(false()))
        .group_by(User.id)
    )

    if sort_by == "full_name":
        query = query.order_by(sort_column, secondary_sort)
    else:
        query = query.order_by(sort_column)

    users_with_counts = query.paginate(page=page, per_page=per_page, error_out=False)

    # Create CSRF form for actions
    form = EmptyForm()

    return render_template(
        "admin/dashboard.html",
        total_users=total_users,
        recent_users=recent_users,
        total_items=total_items,
        mau_series=mau_series,
        users_pagination=users_with_counts,
        form=form,
        active_tab=active_tab,
        current_sort=sort_by,
        current_order=order,
    )


ACTIVITY_PER_PAGE = 50

# How far past the retention window the oldest surviving row has to be before the page
# says the prune job is not running. Wide enough that a job which ran yesterday never
# trips it, narrow enough to notice within a couple of weeks.
PRUNE_OVERDUE_GRACE_DAYS = 10


def _prune_is_overdue(oldest_occurred_at, retention_days):
    """Return True when the oldest entry is well past the retention window.

    The retention window is enforced by a scheduled job outside the app, so the app
    cannot tell whether that job exists. If nobody ever schedules it the table grows
    without bound and, worse, keeps holding typed email addresses that should have
    aged out -- so the page says so where an admin will actually see it.
    """
    if oldest_occurred_at is None:
        return False

    # occurred_at is stored without a timezone, so compare against a naive UTC now.
    now = datetime.now(UTC).replace(tzinfo=None)
    return oldest_occurred_at < now - timedelta(days=retention_days + PRUNE_OVERDUE_GRACE_DAYS)


@bp.route("/activity")
@admin_required
def activity():
    """Read-only view of the activity log, newest first.

    Its own route rather than a third pane on the dashboard: the dashboard already
    owns `page`, `sort_by` and `order` for the Users tab, and it runs the monthly
    active users rollup on every load, which this page has no reason to pay for.
    """
    page = request.args.get("page", 1, type=int)

    entries = (
        ActivityLog.query.options(
            joinedload(ActivityLog.actor),
            joinedload(ActivityLog.subject),
        )
        # The id tiebreak matters: a single sign-in writes several rows in the same
        # millisecond, and without it Postgres is free to return one of them on two
        # consecutive pages and drop another entirely.
        .order_by(ActivityLog.occurred_at.desc(), ActivityLog.id.desc())
        .paginate(page=page, per_page=ACTIVITY_PER_PAGE, error_out=False)
    )

    # A page past the end, e.g. after a prune shortened the log.
    if not entries.items and entries.total:
        return redirect(url_for("admin.activity", page=entries.pages))

    retention_days = current_app.config["ACTIVITY_LOG_RETENTION_DAYS"]
    oldest_occurred_at = oldest_entry_at()

    return render_template(
        "admin/activity.html",
        active_tab="activity",
        entries=entries,
        retention_days=retention_days,
        oldest_occurred_at=oldest_occurred_at,
        prune_overdue=_prune_is_overdue(oldest_occurred_at, retention_days),
    )


@bp.route("/users/<uuid:user_id>/promote", methods=["POST"])
@admin_required
def promote_user(user_id):
    """Promote a user to admin"""
    form = EmptyForm()
    if not form.validate_on_submit():
        flash("Invalid request", "danger")
        return redirect(url_for("admin.dashboard"))

    user = db.get_or_404(User, user_id)

    if user.is_deleted:
        flash("Cannot promote a deleted user", "admin-error")
        return redirect(url_for("admin.dashboard"))

    if user.is_admin:
        flash(f"{user.full_name} is already an admin", "admin-error")
        return redirect(url_for("admin.dashboard"))

    # Promote user
    user.is_admin = True

    # Log admin action
    action = AdminAction(
        action_type="promote",
        target_user_id=user.id,
        admin_user_id=current_user.id,
        details={"target_email": user.email, "target_name": user.full_name},
    )
    db.session.add(action)
    db.session.commit()

    flash(f"{user.full_name} has been promoted to admin", "admin-success")
    logger.info(f"Admin {current_user.email} promoted {user.email} to admin")

    return redirect(url_for("admin.dashboard"))


@bp.route("/users/<uuid:user_id>/demote", methods=["POST"])
@admin_required
def demote_user(user_id):
    """Remove admin status from a user"""
    form = EmptyForm()
    if not form.validate_on_submit():
        flash("Invalid request", "danger")
        return redirect(url_for("admin.dashboard"))

    user = db.get_or_404(User, user_id)

    # Prevent self-demotion
    if user.id == current_user.id:
        flash("You cannot demote yourself", "admin-error")
        return redirect(url_for("admin.dashboard"))

    if not user.is_admin:
        flash(f"{user.full_name} is not an admin", "admin-error")
        return redirect(url_for("admin.dashboard"))

    # Demote user
    user.is_admin = False

    # Log admin action
    action = AdminAction(
        action_type="demote",
        target_user_id=user.id,
        admin_user_id=current_user.id,
        details={"target_email": user.email, "target_name": user.full_name},
    )
    db.session.add(action)
    db.session.commit()

    flash(f"Admin status removed from {user.full_name}", "admin-success")
    logger.info(f"Admin {current_user.email} demoted {user.email} from admin")

    return redirect(url_for("admin.dashboard"))


@bp.route("/users/<uuid:user_id>/delete", methods=["POST"])
@admin_required
def delete_user(user_id):
    """Delete a user account (soft delete)"""
    form = EmptyForm()
    if not form.validate_on_submit():
        flash("Invalid request", "danger")
        return redirect(url_for("admin.dashboard"))

    user = db.get_or_404(User, user_id)

    # Prevent self-deletion
    if user.id == current_user.id:
        flash("You cannot delete your own account from the admin panel", "admin-error")
        return redirect(url_for("admin.dashboard"))

    if user.is_deleted:
        flash("User account is already deleted", "admin-error")
        return redirect(url_for("admin.dashboard"))

    # Store info before deletion
    user_email = user.email
    user_name = user.full_name

    # Log admin action before deletion
    action = AdminAction(
        action_type="delete",
        target_user_id=user.id,
        admin_user_id=current_user.id,
        details={"target_email": user_email, "target_name": user_name, "reason": "Admin deletion"},
    )
    db.session.add(action)

    # Soft delete the user using the shared account workflow service.
    try:
        account_service.delete_user_account(user)

        flash(f"User account for {user_name} has been deleted", "admin-success")
        logger.info(f"Admin {current_user.email} deleted user {user_email}")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting user: {str(e)}", "admin-error")
        logger.error(f"Error deleting user {user_email}: {str(e)}")

    return redirect(url_for("admin.dashboard"))


@bp.route("/users/<uuid:user_id>/enable-showcase", methods=["POST"])
@admin_required
def enable_showcase(user_id):
    """Enable public showcase for a user's items"""
    form = EmptyForm()
    if not form.validate_on_submit():
        flash("Invalid request", "danger")
        return redirect(url_for("admin.dashboard"))

    user = db.get_or_404(User, user_id)

    if user.is_deleted:
        flash("Cannot enable showcase for a deleted user", "admin-error")
        return redirect(url_for("admin.dashboard"))

    if user.is_public_showcase:
        flash(f"{user.full_name} already has public showcase enabled", "admin-error")
        return redirect(url_for("admin.dashboard"))

    # Enable showcase
    user.is_public_showcase = True

    # Log admin action
    action = AdminAction(
        action_type="enable_showcase",
        target_user_id=user.id,
        admin_user_id=current_user.id,
        details={"target_email": user.email, "target_name": user.full_name},
    )
    db.session.add(action)
    db.session.commit()

    flash(f"Public showcase enabled for {user.full_name}", "admin-success")
    logger.info(f"Admin {current_user.email} enabled showcase for {user.email}")

    return redirect(url_for("admin.dashboard"))


@bp.route("/users/<uuid:user_id>/disable-showcase", methods=["POST"])
@admin_required
def disable_showcase(user_id):
    """Disable public showcase for a user's items"""
    form = EmptyForm()
    if not form.validate_on_submit():
        flash("Invalid request", "danger")
        return redirect(url_for("admin.dashboard"))

    user = db.get_or_404(User, user_id)

    if not user.is_public_showcase:
        flash(f"{user.full_name} does not have public showcase enabled", "admin-error")
        return redirect(url_for("admin.dashboard"))

    # Disable showcase
    user.is_public_showcase = False

    # Log admin action
    action = AdminAction(
        action_type="disable_showcase",
        target_user_id=user.id,
        admin_user_id=current_user.id,
        details={"target_email": user.email, "target_name": user.full_name},
    )
    db.session.add(action)
    db.session.commit()

    flash(f"Public showcase disabled for {user.full_name}", "admin-success")
    logger.info(f"Admin {current_user.email} disabled showcase for {user.email}")

    return redirect(url_for("admin.dashboard"))


@bp.route("/users/<uuid:user_id>/digest-frequency", methods=["POST"])
@admin_required
def update_digest_frequency(user_id):
    """Update digest frequency for a user."""
    form = EmptyForm()
    if not form.validate_on_submit():
        flash("Invalid request", "danger")
        return redirect(url_for("admin.dashboard"))

    user = db.get_or_404(User, user_id)

    if user.is_deleted:
        flash("Cannot update digest settings for a deleted user", "admin-error")
        return redirect(url_for("admin.dashboard"))

    digest_frequency = request.form.get("digest_frequency")
    if digest_frequency not in User.DIGEST_FREQUENCY_CHOICES:
        flash("Invalid digest frequency", "admin-error")
        return redirect(url_for("admin.dashboard"))

    previous_frequency = user.digest_frequency
    user.digest_frequency = digest_frequency

    action = AdminAction(
        action_type="set_digest_frequency",
        target_user_id=user.id,
        admin_user_id=current_user.id,
        details={
            "target_email": user.email,
            "target_name": user.full_name,
            "from": previous_frequency,
            "to": digest_frequency,
        },
    )
    db.session.add(action)
    db.session.commit()

    flash(f"Digest frequency updated for {user.full_name}", "admin-success")
    logger.info(
        f"Admin {current_user.email} changed digest frequency for {user.email} from {previous_frequency} to {digest_frequency}"
    )

    return redirect(url_for("admin.dashboard"))
