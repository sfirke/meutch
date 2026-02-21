from urllib.parse import urljoin

from flask import render_template, abort, redirect, url_for, request
from flask_login import current_user
from app.share import bp as share
from app.models import Item, ItemRequest, Circle
from app import db
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

    if current_user.is_authenticated:
        return redirect(url_for('main.item_detail', item_id=item_id))

    return render_template(
        'share/giveaway_preview.html',
        item=item,
        preview_image_url=_absolute_image_url(item.image_url)
    )


@share.route('/request/<uuid:request_id>')
def request_preview(request_id):
    """Public preview page for a public item request."""
    item_request = db.session.get(ItemRequest, request_id)
    if not item_request or item_request.visibility != 'public' or item_request.status == 'deleted':
        abort(404)

    if current_user.is_authenticated:
        return redirect(url_for('requests.detail', request_id=request_id))

    return render_template(
        'share/request_preview.html',
        item_request=item_request,
        preview_image_url=_absolute_image_url(item_request.user.profile_image_url)
    )


@share.route('/circle/<uuid:circle_id>')
def circle_preview(circle_id):
    """Public preview page for a searchable circle (public or private, not unlisted)."""
    circle = db.session.get(Circle, circle_id)
    if not circle or circle.visibility == 'unlisted':
        abort(404)

    if current_user.is_authenticated:
        return redirect(url_for('circles.view_circle', circle_id=circle_id))

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
        preview_image_url=_absolute_image_url(circle.image_url)
    )
