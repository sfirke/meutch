"""Routes for the Requests (community asks) blueprint."""
from datetime import datetime, UTC, timedelta
from dateutil.relativedelta import relativedelta
from flask import render_template, request, flash, redirect, url_for, abort
from flask_login import login_required, current_user
from sqlalchemy import or_, and_, select
from app import db
from app.models import ItemRequest, User, circle_members
from app.forms import ItemRequestForm, EmptyForm
from app.requests import bp as requests_bp
from app.utils.pagination import ListPagination


@requests_bp.route('/')
@login_required
def feed():
    """Display the requests feed with filtering options."""
    page = request.args.get('page', 1, type=int)
    scope = request.args.get('scope', 'circles')  # 'circles' or 'public'
    max_distance = request.args.get('distance', type=int)
    per_page = 12

    now = datetime.now(UTC)
    seven_days_ago = now - timedelta(days=7)

    has_circles = len(current_user.circles) > 0

    # My own requests (open or recently fulfilled) — always shown at top
    my_requests = ItemRequest.query.filter(
        ItemRequest.user_id == current_user.id,
        ItemRequest.status != 'deleted',
    ).order_by(ItemRequest.created_at.desc()).all()

    # Filter to those that should display (open+not-expired, or fulfilled within 7 days)
    my_requests = [r for r in my_requests if r.show_in_feed or r.is_expired]

    # Build the base query for others' requests
    base_query = ItemRequest.query.join(User, ItemRequest.user_id == User.id).filter(
        ItemRequest.user_id != current_user.id,
        User.is_deleted == False,
        User.vacation_mode == False,
        or_(
            # Open and not expired
            and_(
                ItemRequest.status == 'open',
                ItemRequest.expires_at > now,
            ),
            # Fulfilled within the last 7 days
            and_(
                ItemRequest.status == 'fulfilled',
                ItemRequest.fulfilled_at > seven_days_ago,
            ),
        ),
    )

    if scope == 'public':
        # Public requests from any user who is in at least one circle
        all_circle_user_ids = select(circle_members.c.user_id).distinct()
        base_query = base_query.filter(
            ItemRequest.visibility == 'public',
            ItemRequest.user_id.in_(all_circle_user_ids),
        )
    else:
        # Circles scope: requests from users who share circles with current user
        if not has_circles:
            return render_template('requests/feed.html',
                                   requests_list=[],
                                   my_requests=my_requests,
                                   pagination=None,
                                   scope=scope,
                                   max_distance=max_distance,
                                   no_circles=True,
                                   fulfill_form=EmptyForm(),
                                   delete_form=EmptyForm())

        shared_circle_user_ids = current_user.get_shared_circle_user_ids_query()
        base_query = base_query.filter(
            ItemRequest.user_id.in_(shared_circle_user_ids),
        )

    # Distance filtering (only for public scope when user is geocoded)
    if scope == 'public' and max_distance and current_user.is_geocoded:
        all_requests = base_query.all()

        filtered = []
        for req in all_requests:
            if req.user.is_geocoded:
                distance = current_user.distance_to(req.user)
                if distance is not None and distance <= max_distance:
                    filtered.append(req)

        # Sort by newest first
        filtered.sort(key=lambda r: r.created_at, reverse=True)

        pagination = ListPagination(filtered, page, per_page)
        requests_list = pagination.items
    elif scope == 'public' and current_user.is_geocoded:
        # Public, no distance filter — still sort by date via DB
        base_query = base_query.order_by(ItemRequest.created_at.desc())
        pagination = base_query.paginate(page=page, per_page=per_page, error_out=False)
        requests_list = pagination.items
    else:
        # Circles scope or non-geocoded public — sort by date
        base_query = base_query.order_by(ItemRequest.created_at.desc())
        pagination = base_query.paginate(page=page, per_page=per_page, error_out=False)
        requests_list = pagination.items

    return render_template('requests/feed.html',
                           requests_list=requests_list,
                           my_requests=my_requests,
                           pagination=pagination,
                           scope=scope,
                           max_distance=max_distance,
                           no_circles=False,
                           fulfill_form=EmptyForm(),
                           delete_form=EmptyForm())


@requests_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    """Create a new item request."""
    form = ItemRequestForm()

    # Set default expiration to 30 days from now
    if request.method == 'GET' and not form.expires_at.data:
        form.expires_at.data = (datetime.now() + timedelta(days=30)).date()

    if form.validate_on_submit():
        item_request = ItemRequest(
            user_id=current_user.id,
            title=form.title.data.strip(),
            description=form.description.data.strip() if form.description.data else None,
            expires_at=datetime.combine(form.expires_at.data, datetime.min.time()),
            seeking=form.seeking.data,
            visibility=form.visibility.data,
        )
        db.session.add(item_request)
        db.session.commit()

        flash('Your request has been posted!', 'success')
        return redirect(url_for('requests.feed'))

    return render_template('requests/new.html', form=form)


@requests_bp.route('/<uuid:request_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(request_id):
    """Edit an existing item request."""
    item_request = db.session.get(ItemRequest, request_id)
    if not item_request:
        abort(404)
    if item_request.user_id != current_user.id:
        abort(403)
    if item_request.status == 'deleted':
        abort(404)

    form = ItemRequestForm(obj=item_request)

    # Convert datetime to date for the form field on GET
    if request.method == 'GET' and item_request.expires_at:
        form.expires_at.data = item_request.expires_at.date() if hasattr(item_request.expires_at, 'date') else item_request.expires_at

    if form.validate_on_submit():
        item_request.title = form.title.data.strip()
        item_request.description = form.description.data.strip() if form.description.data else None
        item_request.expires_at = datetime.combine(form.expires_at.data, datetime.min.time())
        item_request.seeking = form.seeking.data
        item_request.visibility = form.visibility.data
        db.session.commit()

        flash('Your request has been updated.', 'success')
        return redirect(url_for('requests.feed'))

    return render_template('requests/edit.html', form=form, item_request=item_request)


@requests_bp.route('/<uuid:request_id>/detail')
@login_required
def detail(request_id):
    """View a single request in detail."""
    item_request = db.session.get(ItemRequest, request_id)
    if not item_request or item_request.status == 'deleted':
        abort(404)

    return render_template('requests/detail.html',
                           item_request=item_request,
                           fulfill_form=EmptyForm(),
                           delete_form=EmptyForm())


@requests_bp.route('/<uuid:request_id>/delete', methods=['POST'])
@login_required
def delete(request_id):
    """Soft-delete a request."""
    form = EmptyForm()
    if not form.validate_on_submit():
        abort(400)

    item_request = db.session.get(ItemRequest, request_id)
    if not item_request:
        abort(404)
    if item_request.user_id != current_user.id:
        abort(403)

    item_request.status = 'deleted'
    db.session.commit()

    flash('Your request has been removed.', 'success')
    return redirect(url_for('requests.feed'))


@requests_bp.route('/<uuid:request_id>/fulfill', methods=['POST'])
@login_required
def fulfill(request_id):
    """Mark a request as fulfilled."""
    form = EmptyForm()
    if not form.validate_on_submit():
        abort(400)

    item_request = db.session.get(ItemRequest, request_id)
    if not item_request:
        abort(404)
    if item_request.user_id != current_user.id:
        abort(403)

    item_request.status = 'fulfilled'
    item_request.fulfilled_at = datetime.now(UTC)
    db.session.commit()

    flash('Request marked as fulfilled! 🎉 It will remain visible for a week as social proof.', 'success')
    return redirect(url_for('requests.feed'))

