from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import login_required, current_user
from app.models import Item, Circle
from app import db

bp = Blueprint('main', __name__)

@bp.route('/')
def index():
    public_circles = Circle.query.filter_by(visibility='public-open').all()
    items = Item.query.join(User).join(
        CircleMembership,
        (CircleMembership.user_id == Item.owner_id)
    ).filter(
        CircleMembership.circle_id.in_([c.id for c in public_circles]),
        Item.available == True
    ).limit(10).all()
    return render_template('main/index.html', items=items)

@bp.route('/list-item', methods=['GET', 'POST'])
@login_required
def list_item():
    if request.method == 'POST':
        item = Item(
            name=request.form['name'],
            description=request.form['description'],
            owner=current_user
        )
        db.session.add(item)
        db.session.commit()
        return redirect(url_for('main.index'))
    return render_template('main/list_item.html')