from urllib.parse import urljoin
from datetime import datetime, timezone

from flask import render_template, abort, redirect, url_for, request, flash, session
from flask_login import current_user, login_required
from app.share import bp as share
from app.models import Item, ItemRequest, Circle
from app import db
from app.forms import EmptyForm
from app.utils.giveaway_visibility import can_view_claimed_giveaway, is_giveaway_party, get_unavailable_giveaway_suggestions
from app.utils.item_share import generate_item_share_token, verify_item_share_token, ITEM_SHARE_TOKEN_MAX_AGE_DAYS
from app.utils.circle_members import sample_circle_members


def _absolute_image_url(image_url):
    """Return an absolute URL for OG/Twitter image tags."""
    if not image_url:
        return url_for('static', filename='img/logo_m.png', _external=True)
    if image_url.startswith('http://') or image_url.startswith('https://'):
        return image_url
    return urljoin(request.url_root, image_url.lstrip('/'))


def _item_share_session_key(item_id):
    return f'generated-item-share-link:{item_id}'


@share.route('/giveaway/<uuid:item_id>')
def giveaway_preview(item_id):
    """Public preview page for a public giveaway."""
    item = db.session.get(Item, item_id)
    if not item or not item.is_giveaway or item.giveaway_visibility != 'public':
        abort(404)

    if item.claim_status == 'claimed' and not can_view_claimed_giveaway(item, current_user):
        suggestions = get_unavailable_giveaway_suggestions(current_user, exclude_item_id=item.id)
        return render_template('main/item_unavailable.html', suggestions=suggestions)

    if item.claim_status == 'pending_pickup':
        if not is_giveaway_party(item, current_user):
            suggestions = get_unavailable_giveaway_suggestions(current_user, exclude_item_id=item.id)
            return render_template('main/item_unavailable.html', suggestions=suggestions)

    if current_user.is_authenticated:
        return redirect(url_for('main.item_detail', item_id=item_id))

    auth_next_url = url_for('main.item_detail', item_id=item.id)

    return render_template(
        'share/giveaway_preview.html',
        item=item,
        preview_image_url=_absolute_image_url(item.image),
        auth_next_url=auth_next_url,
    )


@share.route('/request/<uuid:request_id>')
def request_preview(request_id):
    """Public preview page for a public item request."""
    item_request = db.session.get(ItemRequest, request_id)
    if not item_request or item_request.visibility != 'public' or item_request.status == 'deleted':
        abort(404)

    show_fulfilled_fallback = item_request.is_fulfilled and not item_request.show_in_feed

    if current_user.is_authenticated:
        if show_fulfilled_fallback:
            flash('This request has already been fulfilled and is no longer available.', 'info')
            return redirect(url_for('requests.feed'))
        return redirect(url_for('requests.detail', request_id=request_id))

    auth_next_url = (
        url_for('requests.feed')
        if item_request.is_fulfilled
        else url_for('requests.detail', request_id=item_request.id)
    )

    return render_template(
        'share/request_preview.html',
        item_request=item_request,
        preview_image_url=_absolute_image_url(item_request.user.profile_image_url),
        show_fulfilled_fallback=show_fulfilled_fallback,
        auth_next_url=auth_next_url,
    )


@share.route('/circle/<uuid:circle_id>')
def circle_preview(circle_id):
    """Public preview page for a searchable circle (open or closed, not secret)."""
    circle = db.session.get(Circle, circle_id)
    if not circle or circle.circle_type == 'secret':
        abort(404)

    if current_user.is_authenticated:
        return redirect(url_for('circles.view_circle', circle_id=circle_id))

    auth_next_url = url_for('circles.view_circle', circle_id=circle.id)

    sample_members = []
    if circle.circle_type == 'open' and circle.members:
        sample_members = sample_circle_members(circle.members, limit=8)

    return render_template(
        'share/circle_preview.html',
        circle=circle,
        sample_members=sample_members,
        member_count=len(circle.members),
        preview_image_url=_absolute_image_url(circle.image_url),
        auth_next_url=auth_next_url,
    )


@share.route('/item/<token>')
def item_preview(token):
    """Public preview page for a tokenized shared item."""
    item, error = verify_item_share_token(token)
    if error:
        abort(404)

    if current_user.is_authenticated:
        if current_user.id == item.owner_id or current_user.shares_circle_with(item.owner):
            return redirect(url_for('main.item_detail', item_id=item.id))
        return redirect(url_for('main.item_detail', item_id=item.id, share_token=token))

    auth_next_url = url_for('share.item_preview', token=token)

    return render_template(
        'share/item_preview.html',
        item=item,
        preview_image_url=_absolute_image_url(item.image),
        auth_next_url=auth_next_url,
        item_share_valid_days=ITEM_SHARE_TOKEN_MAX_AGE_DAYS,
    )


@share.route('/item/<uuid:item_id>/generate', methods=['POST'])
@login_required
def generate_item_link(item_id):
    """Generate a new share link for a regular item."""
    item = db.get_or_404(Item, item_id)
    form = EmptyForm()

    if not form.validate_on_submit():
        abort(400)

    if item.owner_id != current_user.id or item.is_giveaway:
        abort(403)

    token = generate_item_share_token(item)
    share_url = url_for('share.item_preview', token=token, _external=True)
    expires_at = (datetime.now(timezone.utc).timestamp() + ITEM_SHARE_TOKEN_MAX_AGE_DAYS * 86400)
    session[_item_share_session_key(item.id)] = {'url': share_url, 'expires_at': expires_at}

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return {'url': share_url}

    flash(
        f'Share link generated. Anyone with this link can view this item for {ITEM_SHARE_TOKEN_MAX_AGE_DAYS} days.',
        'warning',
    )
    return redirect(url_for('main.item_detail', item_id=item.id))
