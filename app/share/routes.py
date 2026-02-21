from flask import render_template, abort
from app.share import bp as share
from app.models import Item, ItemRequest, Circle
from app import db
import random


@share.route('/giveaway/<uuid:item_id>')
def giveaway_preview(item_id):
    """Public preview page for a public giveaway."""
    item = db.session.get(Item, item_id)
    if not item or not item.is_giveaway or item.giveaway_visibility != 'public':
        abort(404)

    return render_template('share/giveaway_preview.html', item=item)


@share.route('/request/<uuid:request_id>')
def request_preview(request_id):
    """Public preview page for a public item request."""
    item_request = db.session.get(ItemRequest, request_id)
    if not item_request or item_request.visibility != 'public' or item_request.status == 'deleted':
        abort(404)

    return render_template('share/request_preview.html', item_request=item_request)


@share.route('/circle/<uuid:circle_id>')
def circle_preview(circle_id):
    """Public preview page for a searchable circle (public or private, not unlisted)."""
    circle = db.session.get(Circle, circle_id)
    if not circle or circle.visibility == 'unlisted':
        abort(404)

    # For public circles, get a sample of members to show avatars
    sample_members = []
    if circle.visibility == 'public' and circle.members:
        members_list = list(circle.members)
        sample_size = min(8, len(members_list))
        sample_members = random.sample(members_list, sample_size)

    return render_template('share/circle_preview.html',
                           circle=circle,
                           sample_members=sample_members,
                           member_count=len(circle.members))
