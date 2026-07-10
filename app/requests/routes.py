"""Routes for the Requests (community asks) blueprint."""

from datetime import datetime, timedelta

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import db
from app.forms import EmptyForm, ItemRequestForm, MessageForm
from app.models import Item, ItemRequest
from app.requests import bp as requests_bp
from app.services import item_service, message_service, request_service
from app.services.exceptions import (
    AuthorizationError,
    ConflictError,
    InformationalError,
    InvalidActionError,
)
from app.utils.messaging_queries import (
    build_request_conversation_summaries,
    find_context_conversation,
)
from app.utils.request_queries import can_view_request


@requests_bp.route("/")
@login_required
def feed():
    """Requests feed now redirects to the homepage activity feed."""
    return redirect(url_for("main.index"))


@requests_bp.route("/new", methods=["GET", "POST"])
@login_required
def new():
    """Create a new item request."""
    form = ItemRequestForm()

    # Set default expiration to 30 days from now
    if request.method == "GET" and not form.expires_at.data:
        form.expires_at.data = (datetime.now() + timedelta(days=30)).date()

    if form.validate_on_submit():
        try:
            request_service.create_request(
                current_user,
                form.title.data,
                form.description.data,
                form.expires_at.data,
                form.seeking.data,
                form.visibility.data,
            )
        except InformationalError as exc:
            form.visibility.errors.append(str(exc))
            return render_template("requests/new.html", form=form)

        flash("Your request has been posted!", "success")
        return redirect(url_for("requests.feed"))

    return render_template("requests/new.html", form=form)


@requests_bp.route("/<uuid:request_id>/edit", methods=["GET", "POST"])
@login_required
def edit(request_id):
    """Edit an existing item request."""
    item_request = db.session.get(ItemRequest, request_id)
    if not item_request:
        abort(404)
    if item_request.user_id != current_user.id:
        abort(403)
    if item_request.status == "deleted":
        abort(404)

    form = ItemRequestForm(obj=item_request)

    # Convert datetime to date for the form field on GET
    if request.method == "GET" and item_request.expires_at:
        form.expires_at.data = (
            item_request.expires_at.date()
            if hasattr(item_request.expires_at, "date")
            else item_request.expires_at
        )

    if form.validate_on_submit():
        try:
            request_service.update_request(
                item_request,
                current_user,
                form.title.data,
                form.description.data,
                form.expires_at.data,
                form.seeking.data,
                form.visibility.data,
            )
        except AuthorizationError:
            abort(403)
        except ConflictError:
            abort(404)
        except InformationalError as exc:
            form.visibility.errors.append(str(exc))
            return render_template(
                "requests/edit.html", form=form, item_request=item_request, fulfill_form=EmptyForm()
            )

        flash("Your request has been updated.", "success")
        return redirect(url_for("requests.feed"))

    return render_template(
        "requests/edit.html", form=form, item_request=item_request, fulfill_form=EmptyForm()
    )


@requests_bp.route("/<uuid:request_id>/detail")
@login_required
def detail(request_id):
    """View a single request in detail."""
    item_request = db.session.get(ItemRequest, request_id)
    if not item_request or item_request.status == "deleted":
        abort(404)
    if not can_view_request(item_request, current_user):
        abort(403)

    # Get conversations about this request (for the author only)
    conversations = []
    if current_user.id == item_request.user_id:
        conversations = build_request_conversation_summaries(item_request.id, current_user.id)

    return render_template(
        "requests/detail.html",
        item_request=item_request,
        conversations=conversations,
        fulfill_form=EmptyForm(),
        delete_form=EmptyForm(),
    )


@requests_bp.route("/<uuid:request_id>/delete", methods=["POST"])
@login_required
def delete(request_id):
    """Soft-delete a request."""
    form = EmptyForm()
    if not form.validate_on_submit():
        abort(400)

    item_request = db.session.get(ItemRequest, request_id)
    if not item_request:
        abort(404)

    try:
        request_service.delete_request(item_request, current_user)
    except AuthorizationError:
        abort(403)
    except ConflictError:
        abort(404)

    flash("Your request has been removed.", "success")
    return redirect(url_for("requests.feed"))


@requests_bp.route("/<uuid:request_id>/fulfill", methods=["POST"])
@login_required
def fulfill(request_id):
    """Mark a request as fulfilled."""
    form = EmptyForm()
    if not form.validate_on_submit():
        abort(400)

    item_request = db.session.get(ItemRequest, request_id)
    if not item_request:
        abort(404)

    try:
        request_service.fulfill_request(item_request, current_user)
    except AuthorizationError:
        abort(403)
    except ConflictError:
        abort(404)

    flash("Request marked as fulfilled! 🎉 It will remain visible for a week.", "success")
    return redirect(url_for("requests.feed"))


@requests_bp.route("/<uuid:request_id>/conversation", methods=["GET", "POST"])
@login_required
def conversation(request_id):
    """Start or continue a conversation with a request author."""
    item_request = db.session.get(ItemRequest, request_id)
    if not item_request or item_request.status == "deleted":
        abort(404)

    try:
        recipient_id = message_service.get_request_conversation_recipient_id(
            item_request,
            current_user,
        )
    except InvalidActionError as exc:
        flash(str(exc), "warning")
        return redirect(url_for("requests.detail", request_id=item_request.id))
    except AuthorizationError:
        abort(403)

    existing_conv = find_context_conversation(
        "request",
        item_request.id,
        current_user.id,
        recipient_id,
    )

    if existing_conv:
        return redirect(
            url_for(
                "main.view_conversation",
                conversation_id=existing_conv.id,
            )
        )

    form = MessageForm()
    if form.validate_on_submit():
        message = message_service.start_request_conversation(
            item_request,
            current_user,
            form.body.data,
        )

        flash("Your message has been sent.", "success")
        return redirect(url_for("main.view_conversation", conversation_id=message.conversation_id))

    return render_template("requests/conversation_start.html", form=form, item_request=item_request)


@requests_bp.route("/<uuid:request_id>/respond")
@login_required
def respond(request_id):
    """Browse the current user's items to respond to a request."""
    item_request = db.session.get(ItemRequest, request_id)
    if not item_request or item_request.status == "deleted":
        abort(404)

    if item_request.user_id == current_user.id:
        flash("You cannot respond to your own request.", "warning")
        return redirect(url_for("requests.detail", request_id=item_request.id))

    if item_request.status != "open" or item_request.is_expired:
        flash("This request is no longer open.", "warning")
        return redirect(url_for("requests.detail", request_id=item_request.id))

    try:
        message_service.get_request_conversation_recipient_id(item_request, current_user)
    except (InvalidActionError, AuthorizationError):
        abort(403)

    search_query = request.args.get("q", "").strip() or None
    page = request.args.get("page", 1, type=int)
    per_page = 12

    pagination = item_service.list_user_items(
        current_user,
        search_query=search_query,
        page=page,
        per_page=per_page,
    )

    return render_template(
        "requests/respond.html",
        item_request=item_request,
        pagination=pagination,
        search_query=search_query or "",
    )


@requests_bp.route("/<uuid:request_id>/respond/<uuid:item_id>", methods=["GET", "POST"])
@login_required
def respond_with_item(request_id, item_id):
    """Compose a message responding to a request with a specific item."""
    item_request = db.session.get(ItemRequest, request_id)
    if not item_request or item_request.status == "deleted":
        abort(404)

    if item_request.user_id == current_user.id:
        flash("You cannot respond to your own request.", "warning")
        return redirect(url_for("requests.detail", request_id=item_request.id))

    if item_request.status != "open" or item_request.is_expired:
        flash("This request is no longer open.", "warning")
        return redirect(url_for("requests.detail", request_id=item_request.id))

    item = db.session.get(Item, item_id)
    if not item or item.owner_id != current_user.id:
        abort(404)

    try:
        message_service.get_request_conversation_recipient_id(item_request, current_user)
    except (InvalidActionError, AuthorizationError):
        abort(403)

    form = MessageForm()
    if form.validate_on_submit():
        try:
            message = message_service.respond_to_request_with_item(
                item_request,
                current_user,
                item,
                body=form.body.data,
            )
        except (InvalidActionError, AuthorizationError) as exc:
            flash(str(exc), "warning")
            return redirect(url_for("requests.respond", request_id=item_request.id))

        flash("Your message has been sent.", "success")
        return redirect(url_for("main.view_conversation", message_id=message.id))

    # Pre-fill the message body on GET
    if request.method == "GET":
        from app.services.message_service import (
            _RESPOND_BODY_TEMPLATE,
            _build_item_url_for_requester,
        )

        item_url = _build_item_url_for_requester(item, current_user, item_request.user)
        form.body.data = _RESPOND_BODY_TEMPLATE.format(
            requester_name=item_request.user.full_name,
            item_name=item.name,
            request_title=item_request.title,
            item_url=item_url,
        )

    return render_template(
        "requests/respond_message.html",
        form=form,
        item_request=item_request,
        item=item,
    )
