"""Admin panel routes for user management and monitoring"""
from flask import render_template, redirect, url_for, flash, request, abort
from flask_login import current_user
from app.admin import bp
from app.auth.decorators import admin_required
from app.models import User, Item, AdminAction
from app.forms import EmptyForm
from app import db
from datetime import datetime, timedelta, UTC
from sqlalchemy import func
import logging

logger = logging.getLogger(__name__)


@bp.route('/')
@admin_required
def dashboard():
    """Admin dashboard with metrics and user management"""
    # Get pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # Calculate metrics
    total_users = User.query.filter_by(is_deleted=False).count()
    
    # Active users (users who have logged in within last 30 days)
    # Using created_at as proxy since we don't have last_login yet
    thirty_days_ago = datetime.now(UTC) - timedelta(days=30)
    recent_users = User.query.filter(
        User.is_deleted == False,
        User.created_at >= thirty_days_ago
    ).count()
    
    total_items = Item.query.count()
    
    # Get paginated user list with item counts
    users_query = User.query.filter_by(is_deleted=False).outerjoin(Item).group_by(User.id).order_by(User.created_at.desc())
    
    # Add item count to each user
    users_with_counts = db.session.query(
        User,
        func.count(Item.id).label('item_count')
    ).outerjoin(Item, Item.owner_id == User.id)\
     .filter(User.is_deleted == False)\
     .group_by(User.id)\
     .order_by(User.created_at.desc())\
     .paginate(page=page, per_page=per_page, error_out=False)
    
    # Create CSRF form for actions
    form = EmptyForm()
    
    return render_template('admin/dashboard.html',
                         total_users=total_users,
                         recent_users=recent_users,
                         total_items=total_items,
                         users_pagination=users_with_counts,
                         form=form)


@bp.route('/users/<uuid:user_id>/promote', methods=['POST'])
@admin_required
def promote_user(user_id):
    """Promote a user to admin"""
    form = EmptyForm()
    if not form.validate_on_submit():
        flash('Invalid request', 'danger')
        return redirect(url_for('admin.dashboard'))
    
    user = User.query.get_or_404(user_id)
    
    if user.is_deleted:
        flash('Cannot promote a deleted user', 'admin-error')
        return redirect(url_for('admin.dashboard'))
    
    if user.is_admin:
        flash(f'{user.full_name} is already an admin', 'admin-error')
        return redirect(url_for('admin.dashboard'))
    
    # Promote user
    user.is_admin = True
    
    # Log admin action
    action = AdminAction(
        action_type='promote',
        target_user_id=user.id,
        admin_user_id=current_user.id,
        details={
            'target_email': user.email,
            'target_name': user.full_name
        }
    )
    db.session.add(action)
    db.session.commit()
    
    flash(f'{user.full_name} has been promoted to admin', 'admin-success')
    logger.info(f'Admin {current_user.email} promoted {user.email} to admin')
    
    return redirect(url_for('admin.dashboard'))


@bp.route('/users/<uuid:user_id>/demote', methods=['POST'])
@admin_required
def demote_user(user_id):
    """Remove admin status from a user"""
    form = EmptyForm()
    if not form.validate_on_submit():
        flash('Invalid request', 'danger')
        return redirect(url_for('admin.dashboard'))
    
    user = User.query.get_or_404(user_id)
    
    # Prevent self-demotion
    if user.id == current_user.id:
        flash('You cannot demote yourself', 'admin-error')
        return redirect(url_for('admin.dashboard'))
    
    if not user.is_admin:
        flash(f'{user.full_name} is not an admin', 'admin-error')
        return redirect(url_for('admin.dashboard'))
    
    # Demote user
    user.is_admin = False
    
    # Log admin action
    action = AdminAction(
        action_type='demote',
        target_user_id=user.id,
        admin_user_id=current_user.id,
        details={
            'target_email': user.email,
            'target_name': user.full_name
        }
    )
    db.session.add(action)
    db.session.commit()
    
    flash(f'Admin status removed from {user.full_name}', 'admin-success')
    logger.info(f'Admin {current_user.email} demoted {user.email} from admin')
    
    return redirect(url_for('admin.dashboard'))


@bp.route('/users/<uuid:user_id>/delete', methods=['POST'])
@admin_required
def delete_user(user_id):
    """Delete a user account (soft delete)"""
    form = EmptyForm()
    if not form.validate_on_submit():
        flash('Invalid request', 'danger')
        return redirect(url_for('admin.dashboard'))
    
    user = User.query.get_or_404(user_id)
    
    # Prevent self-deletion
    if user.id == current_user.id:
        flash('You cannot delete your own account from the admin panel', 'admin-error')
        return redirect(url_for('admin.dashboard'))
    
    if user.is_deleted:
        flash('User account is already deleted', 'admin-error')
        return redirect(url_for('admin.dashboard'))
    
    # Store info before deletion
    user_email = user.email
    user_name = user.full_name
    
    # Log admin action before deletion
    action = AdminAction(
        action_type='delete',
        target_user_id=user.id,
        admin_user_id=current_user.id,
        details={
            'target_email': user_email,
            'target_name': user_name,
            'reason': 'Admin deletion'
        }
    )
    db.session.add(action)
    
    # Soft delete the user (uses existing delete_account method)
    try:
        user.delete_account()
        db.session.commit()
        
        flash(f'User account for {user_name} has been deleted', 'admin-success')
        logger.info(f'Admin {current_user.email} deleted user {user_email}')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting user: {str(e)}', 'admin-error')
        logger.error(f'Error deleting user {user_email}: {str(e)}')
    
    return redirect(url_for('admin.dashboard'))
