"""Admin panel routes for user management and monitoring"""

import logging
from datetime import UTC, datetime, timedelta

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import false, func, select, true, union_all

from app import db
from app.admin import bp
from app.auth.decorators import admin_required
from app.forms import EmptyForm
from app.models import (
    AdminAction,
    GiveawayInterest,
    Item,
    ItemRequest,
    LoanRequest,
    Message,
    User,
    circle_members,
)

logger = logging.getLogger(__name__)


def _next_month(month_start):
    """Return the first day of the next month."""
    if month_start.month == 12:
        return month_start.replace(year=month_start.year + 1, month=1)
    return month_start.replace(month=month_start.month + 1)


def _monthly_active_users_series():
    """Build monthly active user counts beginning January 2026."""
    # Pylint does not understand SQLAlchemy's dynamic func.* helpers and
    # incorrectly flags calls like func.count(...) as not-callable.
    # pylint: disable=not-callable
    first_month = datetime(2026, 1, 1, tzinfo=UTC)
    current_month = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end_month = _next_month(current_month)

    eligible_circle_ids = (
        select(circle_members.c.circle_id.label("circle_id"))
        .group_by(circle_members.c.circle_id)
        .having(func.count(circle_members.c.user_id) >= 2)
        .subquery()
    )

    eligible_users = (
        select(
            circle_members.c.user_id.label("user_id"),
            func.min(circle_members.c.joined_at).label("eligible_from"),
        )
        .join(
            eligible_circle_ids,
            eligible_circle_ids.c.circle_id == circle_members.c.circle_id,
        )
        .group_by(circle_members.c.user_id)
        .subquery()
    )

    activity = union_all(
        select(
            ItemRequest.user_id.label("user_id"),
            ItemRequest.created_at.label("event_at"),
        ),
        select(
            Item.owner_id.label("user_id"),
            Item.created_at.label("event_at"),
        ),
        select(
            LoanRequest.borrower_id.label("user_id"),
            LoanRequest.created_at.label("event_at"),
        ),
        select(
            Item.owner_id.label("user_id"),
            LoanRequest.created_at.label("event_at"),
        ).join(Item, LoanRequest.item_id == Item.id),
        select(
            Message.sender_id.label("user_id"),
            Message.timestamp.label("event_at"),
        )
        .join(ItemRequest, Message.request_id == ItemRequest.id)
        .where(Message.sender_id != ItemRequest.user_id),
        select(
            Message.sender_id.label("user_id"),
            Message.timestamp.label("event_at"),
        )
        .join(Item, Message.item_id == Item.id)
        .where(
            Item.is_giveaway.is_(true()),
            Message.sender_id != Item.owner_id,
        ),
        select(
            GiveawayInterest.user_id.label("user_id"),
            GiveawayInterest.created_at.label("event_at"),
        )
        .join(Item, GiveawayInterest.item_id == Item.id)
        .where(
            Item.is_giveaway.is_(true()),
            GiveawayInterest.user_id != Item.owner_id,
        ),
    ).subquery()

    month_start = func.date_trunc("month", activity.c.event_at)
    monthly_rows = db.session.execute(
        select(
            month_start.label("month_start"),
            func.count(func.distinct(activity.c.user_id)).label("active_users"),
        )
        .join(eligible_users, eligible_users.c.user_id == activity.c.user_id)
        .join(User, User.id == activity.c.user_id)
        .where(
            User.is_deleted.is_(false()),
            activity.c.event_at >= first_month,
            activity.c.event_at < end_month,
            activity.c.event_at >= eligible_users.c.eligible_from,
        )
        .group_by(month_start)
        .order_by(month_start)
    ).all()

    counts_by_month = {
        (row.month_start.year, row.month_start.month): row.active_users for row in monthly_rows
    }

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
        month_cursor = _next_month(month_cursor)

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

    # Soft delete the user (uses existing delete_account method)
    try:
        user.delete_account()
        db.session.commit()

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
