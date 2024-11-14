from flask import render_template, redirect, url_for, flash, request
from flask_login import current_user, login_required
from app.circles import bp as circles_bp
from app.models import Circle, db, circle_members, CircleJoinRequest
from app.forms import CircleCreateForm, EmptyForm, CircleSearchForm, CircleJoinRequestForm
import logging
from sqlalchemy import and_
from datetime import datetime

logger = logging.getLogger(__name__)

# Circles -----------------------------------------------------

@circles_bp.route('/circles', methods=['GET', 'POST'])
@login_required
def manage_circles():
    circle_form = CircleCreateForm()
    search_form = CircleSearchForm()
    searched_circles = None

    # Get user's admin circles with pending request counts
    admin_circle_counts = db.session.query(
        Circle.id.cast(db.String).label('circle_id'),  # Convert UUID to string
        db.func.count(CircleJoinRequest.id).label('pending_count')
    ).join(
        circle_members,
        Circle.id == circle_members.c.circle_id
    ).outerjoin(
        CircleJoinRequest,
        db.and_(
            Circle.id == CircleJoinRequest.circle_id,
            CircleJoinRequest.status == 'pending'
        )
    ).filter(
        circle_members.c.user_id == current_user.id,
        circle_members.c.is_admin == True
    ).group_by(Circle.id).all()

    # Convert to dictionary with pre-converted string IDs
    user_admin_circles = {circle_id: count for circle_id, count in admin_circle_counts}


    if request.method == 'POST':
        if 'create_circle' in request.form and circle_form.validate_on_submit():
            # Handle Circle Creation
            existing_circle = Circle.query.filter(db.func.lower(Circle.name) == db.func.lower(circle_form.name.data)).first()
            if existing_circle:
                flash('A circle with this name already exists.', 'danger')
            else:
                new_circle = Circle(
                    name=circle_form.name.data,
                    description=circle_form.description.data,
                    requires_approval=circle_form.requires_approval.data
                )
                db.session.add(new_circle)
                db.session.flush()  # Ensure circle has an ID
                
                # Add creator as admin member
                stmt = circle_members.insert().values(
                    user_id=current_user.id,
                    circle_id=new_circle.id,
                    joined_at=datetime.utcnow(),
                    is_admin=True
                )
                db.session.execute(stmt)
                db.session.commit()
                
                flash('Circle created successfully.', 'success')
                return redirect(url_for('circles.manage_circles'))
            
        elif 'search_circles' in request.form and search_form.validate_on_submit():
            # Handle Circle Search
            query = search_form.search_query.data
            searched_circles = Circle.query.filter(Circle.name.ilike(f'%{query}%')).all()
            if not searched_circles:
                flash('No circles found matching your search.', 'info')

    # Fetch user's circles
    user_circles = current_user.circles  # Assuming 'circles' relationship exists in User model

    return render_template('circles/circles.html', 
                           circle_form=circle_form, 
                           search_form=search_form, 
                           user_circles=user_circles,
                           user_admin_circles=user_admin_circles,
                           searched_circles=searched_circles)


@circles_bp.route('/circles/<uuid:circle_id>', methods=['GET'])
@login_required
def view_circle(circle_id):
    circle = Circle.query.get_or_404(circle_id)
    is_member = current_user in circle.members

    # Only redirect non-members for private circles
    if circle.requires_approval and not is_member:
        join_form = CircleJoinRequestForm()
    else:
        join_form = EmptyForm()

    form = EmptyForm() if is_member else None

    return render_template(
        'circles/circle_details.html',
        circle=circle,
        is_member=is_member,
        form=form,
        join_form=join_form
    )

@circles_bp.route('/circles/join/<uuid:circle_id>', methods=['POST'])
@login_required
def join_circle(circle_id):
    circle = Circle.query.get_or_404(circle_id)
    form = CircleJoinRequestForm() if circle.requires_approval else EmptyForm()

    if current_user in circle.members:
        flash('You are already a member of this circle.', 'info')
        return redirect(url_for('circles.view_circle', circle_id=circle.id))
    
    if circle.requires_approval:
        if form.validate_on_submit():
            join_request = CircleJoinRequest(
                circle_id=circle.id,
                user_id=current_user.id,
                message=form.message.data
            )
            db.session.add(join_request)
            db.session.commit()
            flash('Your request to join has been submitted.', 'success')
            return redirect(url_for('circles.view_circle', circle_id=circle.id))
        else:
            flash('There was an error with your join request.', 'danger')
            return redirect(url_for('circles.view_circle', circle_id=circle.id))
    else:
        # For circles that do not require approval
        stmt = circle_members.insert().values(
            user_id=current_user.id,
            circle_id=circle.id,
            joined_at=datetime.utcnow(),
            is_admin=False
        )
        db.session.execute(stmt)
        db.session.commit()
        flash('You have joined the circle successfully!', 'success')
        return redirect(url_for('circles.view_circle', circle_id=circle.id))


@circles_bp.route('/circles/leave/<uuid:circle_id>', methods=['POST'])
@login_required
def leave_circle(circle_id):
    circle = Circle.query.get_or_404(circle_id)
    if current_user not in circle.members:
        flash('You are not a member of this circle.', 'info')
        return redirect(url_for('circles.view_circle', circle_id=circle_id))
    
    # Check if current user is an admin and there are other members
    if circle.is_admin(current_user) and len(circle.members) > 1:
        admin_count = db.session.query(circle_members).filter_by(
            circle_id=circle.id,
            is_admin=True
        ).count()
        
        if admin_count == 1:
            # Find earliest member to assign as new admin
            next_admin_assoc = db.session.query(circle_members).filter(
                circle_members.c.circle_id == circle.id,
                circle_members.c.user_id != current_user.id
            ).order_by(circle_members.c.joined_at).first()
            
            if next_admin_assoc:
                stmt = circle_members.update().where(
                    and_(
                        circle_members.c.circle_id == circle_id,
                        circle_members.c.user_id == next_admin_assoc.user_id
                    )
                ).values(is_admin=True)
                db.session.execute(stmt)

    # Remove the member using the relationship
    circle.members.remove(current_user)
    
    # If this was the last member, delete the circle
    if len(circle.members) == 0:
        db.session.delete(circle)
        db.session.commit()
        flash('Circle has been deleted as it has no remaining members.', 'info')
        return redirect(url_for('circles.manage_circles'))
    
    db.session.commit()
    flash('You have left the circle.', 'success')
    return redirect(url_for('circles.manage_circles'))


@circles_bp.route('/circles/request/<uuid:circle_id>', methods=['POST'])
@login_required
def request_to_join(circle_id):
    circle = Circle.query.get_or_404(circle_id)
    form = CircleJoinRequestForm()
    
    if form.validate_on_submit():
        existing_request = CircleJoinRequest.query.filter_by(
            circle_id=circle.id,
            user_id=current_user.id,
            status='pending'
        ).first()
        if existing_request:
            flash('You already have a pending request to join this circle.', 'info')
        else:
            request_entry = CircleJoinRequest(
                circle_id=circle.id,
                user_id=current_user.id,
                message=form.message.data
            )
            db.session.add(request_entry)
            db.session.commit()
            flash('Your request to join has been submitted.', 'success')
    else:
        flash('There was an error with your join request.', 'danger')
    return redirect(url_for('circles.view_circle', circle_id=circle_id))


@circles_bp.route('/circles/<uuid:circle_id>/request/<uuid:request_id>/<action>', methods=['POST'])
@login_required
def handle_join_request(circle_id, request_id, action):
    circle = Circle.query.get_or_404(circle_id)
    if not circle.is_admin(current_user):
        flash('You must be an admin to perform this action.', 'danger')
        return redirect(url_for('circles.view_circle', circle_id=circle_id))
        
    join_request = CircleJoinRequest.query.get_or_404(request_id)
    
    if join_request.circle_id != circle.id:
        flash('Invalid join request.', 'danger')
        return redirect(url_for('circles.view_circle', circle_id=circle_id))
    
    if action == 'approve':
        # Add user to circle_members with is_admin=False
        stmt = circle_members.insert().values(
            user_id=join_request.user_id,
            circle_id=circle.id,
            joined_at=datetime.utcnow(),
            is_admin=False
        )
        db.session.execute(stmt)
        join_request.status = 'approved'
        flash('User has been approved to join the circle.', 'success')
        
    elif action == 'reject':
        join_request.status = 'rejected'
        flash('User request has been rejected.', 'info')
    else:
        flash('Invalid action.', 'danger')
        return redirect(url_for('circles.view_circle', circle_id=circle_id))
    
    db.session.commit()
    return redirect(url_for('circles.view_circle', circle_id=circle_id))


@circles_bp.route('/circles/<uuid:circle_id>/admin/<uuid:user_id>/<action>', methods=['POST'])
@login_required
def toggle_admin(circle_id, user_id, action):
    circle = Circle.query.get_or_404(circle_id)
    if not circle.is_admin(current_user):
        flash('You must be an admin to perform this action.', 'danger')
        return redirect(url_for('circles.view_circle', circle_id=circle_id))
        
    user_member = db.session.query(circle_members).filter_by(
        circle_id=circle_id,
        user_id=user_id
    ).first()
    
    if not user_member:
        flash('User is not a member of this circle.', 'warning')
        return redirect(url_for('circles.view_circle', circle_id=circle_id))
    
    if action == 'add':
        is_admin = True
        flash_message = 'Admin status granted to user.'
    elif action == 'remove':
        is_admin = False
        flash_message = 'Admin status removed from user.'
    else:
        flash('Invalid action.', 'danger')
        return redirect(url_for('circles.view_circle', circle_id=circle_id))
    
    stmt = circle_members.update().where(
        and_(
            circle_members.c.circle_id == circle_id,
            circle_members.c.user_id == user_id
        )
    ).values(is_admin=is_admin)
    
    db.session.execute(stmt)
    db.session.commit()
    
    flash(flash_message, 'success')
    return redirect(url_for('circles.view_circle', circle_id=circle_id))


@circles_bp.route('/create-circle', methods=['GET', 'POST'])
@login_required
def create_circle():
    form = CircleCreateForm()
    if form.validate_on_submit():
        circle_name = form.name.data.strip()
        existing_circle = Circle.query.filter(db.func.lower(Circle.name) == db.func.lower(circle_name)).first()
        if existing_circle:
            flash('A circle with that name already exists. Please choose a different name.', 'danger')
            return render_template('circles/create_circle.html', form=form)
        
        new_circle = Circle(
            name=circle_name,
            description=form.description.data.strip(),
            requires_approval=form.requires_approval.data
        )
        db.session.add(new_circle)
        db.session.flush()
        
        stmt = circle_members.insert().values(
            user_id=current_user.id,
            circle_id=new_circle.id,
            joined_at=datetime.utcnow(),
            is_admin=True
        )
        db.session.execute(stmt)
        db.session.commit()
        
        flash(f'Circle "{new_circle.name}" has been created successfully!', 'success')
        return redirect(url_for('circles.view_circle', circle_id=new_circle.id))
    return render_template('circles/create_circle.html', form=form)



@circles_bp.route('/search-circles', methods=['GET', 'POST'])
@login_required
def search_circles():
    form = CircleSearchForm()
    circles = []
    if form.validate_on_submit():
        query = form.search_query.data.strip()
        circles = Circle.query.filter(Circle.name.ilike(f'%{query}%')).all()
        if not circles:
            flash('No circles found matching your search criteria.', 'info')
    return render_template('circles/search_circles.html', form=form, circles=circles)