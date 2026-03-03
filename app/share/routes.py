from urllib.parse import urljoin

from flask import render_template, abort, redirect, url_for, request, flash
from flask_login import current_user
from app.share import bp as share
from app.models import Item, ItemRequest, Circle
from app import db
from app.utils.giveaway_visibility import can_view_claimed_giveaway, is_giveaway_party, get_unavailable_giveaway_suggestions
import random


def _absolute_image_url(image_url):
    """Return an absolute URL for OG/Twitter image tags."""
    if not image_url:
        return url_for('static', filename='img/logo_m.png', _external=True)
    if image_url.startswith('http://') or image_url.startswith('https://'):
        return image_url
    return urljoin(request.url_root, image_url.lstrip('/'))


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
        preview_image_url=_absolute_image_url(item.image_url),
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
    """Public preview page for a searchable circle (public or private, not unlisted)."""
    circle = db.session.get(Circle, circle_id)
    if not circle or circle.visibility == 'unlisted':
        abort(404)

    if current_user.is_authenticated:
        return redirect(url_for('circles.view_circle', circle_id=circle_id))

    auth_next_url = url_for('circles.view_circle', circle_id=circle.id)

    # For public circles, get a sample of members to show avatars
    # Prioritize members who have uploaded a custom avatar
    sample_members = []
    if circle.visibility == 'public' and circle.members:
        members_list = list(circle.members)
        with_avatar = [m for m in members_list if m.profile_image_url]
        without_avatar = [m for m in members_list if not m.profile_image_url]
        random.shuffle(with_avatar)
        random.shuffle(without_avatar)
        prioritized = with_avatar + without_avatar
        sample_members = prioritized[:8]

    return render_template(
        'share/circle_preview.html',
        circle=circle,
        sample_members=sample_members,
        member_count=len(circle.members),
        preview_image_url=_absolute_image_url(circle.image_url),
        auth_next_url=auth_next_url,
    )
