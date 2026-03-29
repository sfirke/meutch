"""Routes for the Requests (community asks) blueprint."""
from datetime import datetime, UTC, timedelta
from flask import render_template, request, flash, redirect, url_for, abort, current_app
from flask_login import login_required, current_user
from sqlalchemy import or_, and_
from app import db
from app.models import ItemRequest, User, Message
from app.forms import ItemRequestForm, EmptyForm, MessageForm
from app.requests import bp as requests_bp
from app.utils.email import send_message_notification_email


@requests_bp.route('/')
@login_required
def feed():
    """Requests feed now redirects to the homepage activity feed."""
    return redirect(url_for('main.index'))


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

    # Get conversations about this request (for the author only)
    conversations = []
    if current_user.id == item_request.user_id:
        # Get all messages about this request, ordered by timestamp
        messages = Message.query.filter(
            Message.request_id == item_request.id,
            Message.item_id.is_(None),
        ).order_by(Message.timestamp.desc()).all()
        
        # Group by unique (sender, recipient) pairs to get conversation threads
        conversation_map = {}
        for msg in messages:
            # Normalize key so same conversation appears only once
            pair = tuple(sorted([msg.sender_id, msg.recipient_id]))
            if pair not in conversation_map:
                conversation_map[pair] = msg
        
        # Convert to list with the other person's info
        for pair, latest_msg in conversation_map.items():
            other_user_id = pair[0] if pair[1] == current_user.id else pair[1]
            other_user = db.session.get(User, other_user_id)
            conversations.append({
                'other_user': other_user,
                'latest_message': latest_msg,
            })

    return render_template('requests/detail.html',
                           item_request=item_request,
                           conversations=conversations,
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

    flash('Request marked as fulfilled! 🎉 It will remain visible for a week.', 'success')
    return redirect(url_for('requests.feed'))


@requests_bp.route('/<uuid:request_id>/conversation', methods=['GET', 'POST'])
@login_required
def conversation(request_id):
    """Start or continue a conversation with a request author."""
    item_request = db.session.get(ItemRequest, request_id)
    if not item_request or item_request.status == 'deleted':
        abort(404)

    if item_request.user_id == current_user.id:
        flash('You cannot message yourself about your own request.', 'warning')
        return redirect(url_for('requests.detail', request_id=item_request.id))

    if item_request.visibility == 'circles' and not current_user.shares_circle_with(item_request.user):
        abort(403)

    existing_message = Message.query.filter(
        Message.request_id == item_request.id,
        Message.item_id.is_(None),
        or_(
            and_(Message.sender_id == current_user.id, Message.recipient_id == item_request.user_id),
            and_(Message.sender_id == item_request.user_id, Message.recipient_id == current_user.id),
        )
    ).order_by(Message.timestamp.asc()).first()

    if existing_message:
        return redirect(url_for('main.view_conversation', message_id=existing_message.id))

    form = MessageForm()
    if form.validate_on_submit():
        message = Message(
            sender_id=current_user.id,
            recipient_id=item_request.user_id,
            item_id=None,
            request_id=item_request.id,
            body=form.body.data,
            is_read=False,
        )
        db.session.add(message)
        db.session.commit()

        try:
            send_message_notification_email(message)
        except Exception as e:
            current_app.logger.error(f"Failed to send email notification for request message {message.id}: {str(e)}")

        flash('Your message has been sent.', 'success')
        return redirect(url_for('main.view_conversation', message_id=message.id))

    return render_template('requests/conversation_start.html', form=form, item_request=item_request)
