from flask import render_template, redirect, url_for, flash, request
from flask_login import current_user, login_required
from app.circles import bp as circles_bp
from app.models import User, Circle, db
from app.forms import CreateCircleForm, EmptyForm, SearchCircleForm
import logging

logger = logging.getLogger(__name__)

@circles_bp.route('/create-circle', methods=['GET', 'POST'])
@login_required
def create_circle():
    form = CreateCircleForm()
    if form.validate_on_submit():
        circle_name = form.name.data.strip()
        existing_circle = Circle.query.filter_by(name=circle_name).first()
        if existing_circle:
            flash('A circle with that name already exists. Please choose a different name.', 'danger')
            return render_template('circles/create_circle.html', form=form)
        
        new_circle = Circle(
            name=circle_name,
            description=form.description.data.strip(),
            requires_approval=form.requires_approval.data
        )
        new_circle.members.append(current_user)  # Add creator as a member
        db.session.add(new_circle)
        db.session.commit()
        
        flash(f'Circle "{new_circle.name}" has been created successfully!', 'success')
        return redirect(url_for('circles.view_circle', circle_id=new_circle.id))
    return render_template('circles/create_circle.html', form=form)

@circles_bp.route('/search-circles', methods=['GET', 'POST'])
@login_required
def search_circles():
    form = SearchCircleForm()
    circles = []
    if form.validate_on_submit():
        query = form.search_query.data.strip()
        circles = Circle.query.filter(Circle.name.ilike(f'%{query}%')).all()
        if not circles:
            flash('No circles found matching your search criteria.', 'info')
    return render_template('circles/search_circles.html', form=form, circles=circles)

@circles_bp.route('/circle/<int:circle_id>', methods=['GET'])
@login_required
def view_circle(circle_id):
    circle = Circle.query.get_or_404(circle_id)
    is_member = current_user in circle.members
    form = EmptyForm()  # Instantiate EmptyForm
    return render_template('circles/view_circle.html', circle=circle, is_member=is_member, form=form)

@circles_bp.route('/join-circle/<int:circle_id>', methods=['POST'])
@login_required
def join_circle(circle_id):
    circle = Circle.query.get_or_404(circle_id)
    if current_user in circle.members:
        flash('You are already a member of this circle.', 'info')
        return redirect(url_for('circles.view_circle', circle_id=circle.id))
    
    if circle.requires_approval:
        # Placeholder for approval logic
        flash('This circle requires administrator approval to join. Your request has been submitted.', 'warning')
        # Here, you would create a join request entry in the database
    else:
        circle.members.append(current_user)
        db.session.commit()
        flash(f'You have successfully joined the circle "{circle.name}".', 'success')
    
    return redirect(url_for('circles.view_circle', circle_id=circle.id))

@circles_bp.route('/leave-circle/<int:circle_id>', methods=['POST'])
@login_required
def leave_circle(circle_id):
    circle = Circle.query.get_or_404(circle_id)
    if current_user not in circle.members:
        flash('You are not a member of this circle.', 'info')
        return redirect(url_for('circles.view_circle', circle_id=circle.id))
    
    circle.members.remove(current_user)
    db.session.commit()
    flash(f'You have successfully left the circle "{circle.name}".', 'success')
    
    return redirect(url_for('main.index'))