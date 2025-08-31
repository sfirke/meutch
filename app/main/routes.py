from uuid import UUID
from flask import render_template, current_app, request, flash, redirect, url_for
from flask_login import login_required, current_user, logout_user
from sqlalchemy import or_, and_, func
from sqlalchemy.orm import joinedload
from app import db
from app.models import Item, LoanRequest, Tag, User, Message, Circle, circle_members, Category
from app.forms import ListItemForm, EditProfileForm, DeleteItemForm, MessageForm, LoanRequestForm, DeleteAccountForm, UpdateLocationForm
from app.main import bp as main_bp
from app.utils.storage import delete_file, upload_item_image, upload_profile_image, is_valid_file_upload

@main_bp.route('/')
def index():
    # Only show items whose owner is in at least one public circle
    public_circle_ids = db.session.query(Circle.id).filter(Circle.requires_approval == False).subquery()
    # Find user IDs who are in at least one public circle
    public_user_ids = db.session.query(circle_members.c.user_id).filter(
        circle_members.c.circle_id.in_(public_circle_ids)
    ).distinct().subquery()
    
    # Base query for items in public circles, ordered by newest first
    base_query = Item.query.filter(Item.owner_id.in_(public_user_ids)).order_by(Item.created_at.desc())
    
    circles = []
    items = []
    pagination = None
    total_items = 0
    remaining_items = 0
    
    if current_user.is_authenticated:
        circles = current_user.circles
        # For logged-in users: show paginated results
        page = request.args.get('page', 1, type=int)
        per_page = 12  # Items per page for logged-in users
        pagination = base_query.paginate(page=page, per_page=per_page, error_out=False)
        items = pagination.items
    else:
        # For anonymous users: show limited items with count
        preview_limit = 12  # Items to show for preview
        total_items = base_query.count()
        items = base_query.limit(preview_limit).all()
        remaining_items = max(0, total_items - preview_limit)
        
    return render_template('main/index.html', 
                         items=items,
                         circles=circles, 
                         pagination=pagination,
                         total_items=total_items,
                         remaining_items=remaining_items)

@main_bp.route('/list-item', methods=['GET', 'POST'])
@login_required
def list_item():
    form = ListItemForm()
    if form.validate_on_submit():
        # Handle image upload first, if provided
        image_url = None
        if form.image.data:
            image_url = upload_item_image(form.image.data)
            if image_url is None:
                flash('Image upload failed. Please ensure you upload a valid image file (JPG, PNG, GIF, etc.).', 'error')
                return render_template('main/list_item.html', form=form)
        
        # Create the item only if image upload succeeded (or no image was provided)
        new_item = Item(
            name=form.name.data.strip(),
            description=form.description.data.strip(),
            owner=current_user,
            category_id=form.category.data,
            image_url=image_url
        )

        db.session.add(new_item)
        
        tag_input = form.tags.data.strip()
        if tag_input:
            tag_names = [tag.strip().lower() for tag in tag_input.split(',') if tag.strip()]
            for tag_name in tag_names:
                tag = Tag.query.filter_by(name=tag_name).first()
                if not tag:
                    tag = Tag(name=tag_name)
                    db.session.add(tag)
                new_item.tags.append(tag)

        db.session.commit()
        
        # Create flash message with link to the item
        from markupsafe import Markup
        item_link = url_for('main.item_detail', item_id=new_item.id)
        message = Markup(f'Item "<a href="{item_link}" class="alert-link">{new_item.name}</a>" has been listed successfully!')
        
        # Check which button was pressed
        if form.submit_and_create_another.data:
            flash(message, 'success')
            return redirect(url_for('main.list_item'))
        else:
            flash(message, 'success')
            return redirect(url_for('main.index'))
    
    return render_template('main/list_item.html', form=form)

@main_bp.route('/search', methods=['GET', 'POST'])
def search():
    query = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = 12  # Number of items per page (consistent with other pages)

    if request.method == 'GET' and not query:
        # Display the search form
        return render_template('search_items.html')

    if not query:
        flash('Please enter a search term.', 'warning')
        return redirect(url_for('main.search'))
    
    # Perform case-insensitive search on name and description
    # Also search tags by joining the Tag model
    items_pagination = Item.query.outerjoin(Item.tags).outerjoin(Item.category).filter(
        or_(
            Item.name.ilike(f'%{query}%'),
            Item.description.ilike(f'%{query}%'),
            Tag.name.ilike(f'%{query}%')
        )
    ).distinct().order_by(Item.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)

    items = items_pagination.items

    return render_template('search_results.html', items=items, query=query, pagination=items_pagination)

@main_bp.route('/item/<uuid:item_id>', methods=['GET', 'POST'])
@login_required
def item_detail(item_id):
    item = Item.query.get_or_404(item_id)
    
    # Initialize the MessageForm
    form = MessageForm()
    
    # Process form submission
    if form.validate_on_submit():

        # Create a new message
        message = Message(
            sender_id=current_user.id,
            recipient_id=item.owner.id,
            item_id=item.id,
            body=form.body.data
        )
        db.session.add(message)
        db.session.commit()
        
        # Send email notification to recipient
        try:
            from app.utils.email import send_message_notification_email
            send_message_notification_email(message)
        except Exception as e:
            current_app.logger.error(f"Failed to send email notification for message {message.id}: {str(e)}")
        
        flash("Your message has been sent.", "success")
        return redirect(url_for('main.item_detail', item_id=item.id))
    
    # Retrieve messages related to this item (optional)
    messages = Message.query.filter_by(item_id=item.id, recipient_id=current_user.id).order_by(Message.timestamp.desc()).all()
    
    from app.forms import DeleteItemForm
    delete_form = DeleteItemForm()
    return render_template('main/item_detail.html', item=item, form=form, messages=messages, delete_form=delete_form)

@main_bp.route('/items/<uuid:item_id>/request', methods=['GET', 'POST'])
@login_required
def request_item(item_id):
    item = Item.query.get_or_404(item_id)
    
    if item.owner == current_user:
        flash('You cannot request your own items.', 'warning')
        return redirect(url_for('main.item_detail', item_id=item.id))
    
    existing_request = LoanRequest.query.filter_by(
        item_id=item.id,
        borrower_id=current_user.id,
        status='pending'
    ).first()
    
    if existing_request:
        flash('You already have a pending request for this item.', 'info')
        return redirect(url_for('main.item_detail', item_id=item.id))

    form = LoanRequestForm()
    if form.validate_on_submit():
        # Create loan request
        loan_request = LoanRequest(
            item_id=item.id,
            borrower_id=current_user.id,
            start_date=form.start_date.data,
            end_date=form.end_date.data,
            status='pending'
        )
        db.session.add(loan_request)
        
        # Create associated message with loan request reference
        message = Message(
            sender_id=current_user.id,
            recipient_id=item.owner_id,
            item_id=item.id,
            body=form.message.data,
            loan_request=loan_request  # Associate message with loan request
        )
        db.session.add(message)
        
        try:
            db.session.commit()
            
            # Send email notification to recipient
            try:
                from app.utils.email import send_message_notification_email
                send_message_notification_email(message)
            except Exception as e:
                current_app.logger.error(f"Failed to send email notification for loan request message {message.id}: {str(e)}")
            
            flash('Your loan request has been submitted.', 'success')
            return redirect(url_for('main.view_conversation', message_id=message.id))
        except:
            db.session.rollback()
            flash('An error occurred. Please try again.', 'danger')
    
    return render_template('main/request_loan.html', form=form, item=item)

@main_bp.route('/item/<uuid:item_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_item(item_id):
    item = Item.query.get_or_404(item_id)
    if item.owner != current_user:
        flash('You do not have permission to edit this item.', 'danger')
        return redirect(url_for('main.profile'))
    
    form = ListItemForm(obj=item)

    if request.method == 'GET':
        form.category.data = str(item.category_id)

    if form.validate_on_submit():
        item.name = form.name.data
        item.description = form.description.data
        item.category_id = form.category.data
        
        # Update tags
        tag_input = form.tags.data.strip()
        if tag_input:
            tag_names = [tag.strip().lower() for tag in tag_input.split(',') if tag.strip()]
            item.tags.clear()
            for tag_name in tag_names:
                tag = Tag.query.filter_by(name=tag_name).first()
                if not tag:
                    tag = Tag(name=tag_name)
                    db.session.add(tag)
                item.tags.append(tag)

        # Handle image deletion
        if form.delete_image.data:
            if item.image_url:
                current_app.logger.debug("Deleting existing image")
                delete_file(item.image_url)
                item.image_url = None
                current_app.logger.debug("Set item.image_url to None")
                flash('Image has been removed.', 'success')
 
        # Handle image upload - only process if a valid file is provided
        if form.image.data:
            # Check if a file was actually selected (not just an empty FileStorage object)
            if hasattr(form.image.data, 'filename') and form.image.data.filename and form.image.data.filename.strip():
                if is_valid_file_upload(form.image.data):
                    if item.image_url:
                        delete_file(item.image_url)
                    image_url = upload_item_image(form.image.data)
                    if image_url:
                        item.image_url = image_url
                    else:
                        flash('Image upload failed. Please ensure you upload a valid image file (JPG, PNG, GIF, etc.).', 'warning')
                else:
                    flash('Invalid file upload. Please select a valid image file.', 'warning')

        db.session.commit()
        flash('Item has been updated.', 'success')
        return redirect(url_for('main.profile'))
    
    # Prepopulate tags field
    form.tags.data = ', '.join([tag.name for tag in item.tags])
    
    return render_template('main/edit_item.html', form=form, item=item)


@main_bp.route('/item/<uuid:item_id>/delete', methods=['POST'])
@login_required
def delete_item(item_id):
    item = Item.query.get_or_404(item_id)
    
    # Check if user owns the item
    if item.owner != current_user:
        flash('You can only delete your own items.', 'danger')
        return redirect(url_for('main.profile'))
    
    try:
        # Start by deleting messages associated with loan requests
        Message.query.filter(
            Message.item_id == item_id
        ).delete()

        # Delete all loan requests for this item
        LoanRequest.query.filter_by(item_id=item_id).delete()
        
        # Clear item-tag associations
        item.tags.clear()
        
        # Delete image from storage if it exists
        if item.image_url:
            delete_file(item.image_url)
        # Now delete the item
        db.session.delete(item)
        db.session.commit()
        
        flash('Item deleted successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting item {item_id}: {str(e)}")
        flash('An error occurred while deleting the item.', 'danger')
    
    return redirect(url_for('main.profile'))

@main_bp.route('/loan/<uuid:loan_id>/<string:action>', methods=['POST'])
@login_required
def process_loan(loan_id, action):
    loan = LoanRequest.query.get_or_404(loan_id)
    
    if loan.item.owner_id != current_user.id:
        flash("You are not authorized to perform this action.", "danger")
        return redirect(url_for('main.messages'))
    
    if action.lower() not in ['approve', 'deny']:
        flash("Invalid action.", "danger")
        return redirect(url_for('main.messages'))
    
    if loan.status != 'pending':
        flash("This loan request has already been processed.", "warning")
        return redirect(url_for('main.messages'))
    
    if action.lower() == 'approve':
        loan.status = 'approved'
        loan.item.available = False
        message_body = f"The loan request for '{loan.item.name}' has been approved."
    else:
        loan.status = 'denied'
        message_body = f"The loan request for '{loan.item.name}' has been denied."
    
    # Create notification message
    message = Message(
        sender_id=current_user.id,
        recipient_id=loan.borrower_id,
        item_id=loan.item_id,
        body=message_body,
        loan_request_id=loan.id
    )
    db.session.add(message)
    
    try:
        db.session.commit()
        
        # Send email notification to recipient
        try:
            from app.utils.email import send_message_notification_email
            send_message_notification_email(message)
        except Exception as e:
            current_app.logger.error(f"Failed to send email notification for loan decision message {message.id}: {str(e)}")
        
        flash(f"Loan request has been {loan.status}.", "success")
    except:
        db.session.rollback()
        flash("An error occurred processing the request.", "danger")
    
    # Redirect back to the conversation
    original_message = Message.query.filter_by(loan_request_id=loan.id).order_by(Message.timestamp.asc()).first()
    return redirect(url_for('main.view_conversation', message_id=original_message.id))

@main_bp.route('/loan/<uuid:loan_id>/cancel', methods=['POST'])
@login_required
def cancel_loan_request(loan_id):
    loan = LoanRequest.query.get_or_404(loan_id)
    
    if loan.borrower_id != current_user.id:
        flash("You are not authorized to cancel this request.", "danger")
        return redirect(url_for('main.messages'))
    
    if loan.status != 'pending':
        flash("This loan request cannot be canceled.", "warning")
        return redirect(url_for('main.messages'))
    
    # Create cancellation message
    message = Message(
        sender_id=current_user.id,
        recipient_id=loan.item.owner_id,
        item_id=loan.item_id,
        body="Loan request has been canceled by the borrower.",
        loan_request_id=loan.id
    )
    db.session.add(message)
    
    # Update loan request status
    loan.status = 'canceled'
    
    try:
        db.session.commit()
        
        # Send email notification to recipient
        try:
            from app.utils.email import send_message_notification_email
            send_message_notification_email(message)
        except Exception as e:
            current_app.logger.error(f"Failed to send email notification for loan cancellation message {message.id}: {str(e)}")
        
        flash("Loan request has been canceled.", "success")
    except:
        db.session.rollback()
        flash("An error occurred canceling the request.", "danger")
    
    # Find original conversation
    original_message = Message.query.filter_by(loan_request_id=loan.id).order_by(Message.timestamp.asc()).first()
    return redirect(url_for('main.view_conversation', message_id=original_message.id))

@main_bp.route('/loan/<uuid:loan_id>/complete', methods=['POST'])
@login_required
def complete_loan(loan_id):
    loan = LoanRequest.query.get_or_404(loan_id)
    
    if loan.item.owner_id != current_user.id:
        flash("You are not authorized to perform this action.", "danger")
        return redirect(url_for('main.messages'))
    
    if loan.status != 'approved':
        flash("This loan is not currently active.", "warning")
        return redirect(url_for('main.messages'))
    
    # Update loan status and item availability
    loan.status = 'completed'
    loan.item.available = True
    
    # Create completion message
    message = Message(
        sender_id=current_user.id,
        recipient_id=loan.borrower_id,
        item_id=loan.item_id,
        body="The item has been marked as returned. Thank you for borrowing!",
        loan_request_id=loan.id
    )
    db.session.add(message)
    
    try:
        db.session.commit()
        
        # Send email notification to recipient
        try:
            from app.utils.email import send_message_notification_email
            send_message_notification_email(message)
        except Exception as e:
            current_app.logger.error(f"Failed to send email notification for loan completion message {message.id}: {str(e)}")
        
        flash("Loan has been marked as completed.", "success")
    except:
        db.session.rollback()
        flash("An error occurred completing the loan.", "danger")
    
    # Find original conversation
    original_message = Message.query.filter_by(loan_request_id=loan.id).order_by(Message.timestamp.asc()).first()
    return redirect(url_for('main.view_conversation', message_id=original_message.id))

@main_bp.route('/loan/<uuid:loan_id>/owner_cancel', methods=['POST'])
@login_required
def owner_cancel_loan(loan_id):
    loan = LoanRequest.query.get_or_404(loan_id)
    
    # Check if the current user is the owner of the item
    if loan.item.owner_id != current_user.id:
        flash("You are not authorized to perform this action.", "danger")
        return redirect(url_for('main.messages'))
    
    # Ensure the loan status is 'approved' before cancellation
    if loan.status != 'approved':
        flash("Only approved loans can be canceled.", "warning")
        return redirect(url_for('main.view_conversation', message_id=loan.messages[0].id))
    
    # Update loan status and item availability
    loan.status = 'canceled'
    loan.item.available = True
    
    # Create a cancellation message to notify the borrower
    message = Message(
        sender_id=current_user.id,
        recipient_id=loan.borrower_id,
        item_id=loan.item_id,
        body="The loan has been canceled by the owner. The item is now available.",
        loan_request_id=loan.id
    )
    db.session.add(message)
    
    try:
        db.session.commit()
        
        # Send email notification to recipient
        try:
            from app.utils.email import send_message_notification_email
            send_message_notification_email(message)
        except Exception as e:
            current_app.logger.error(f"Failed to send email notification for owner loan cancellation message {message.id}: {str(e)}")
        
        flash("Loan has been canceled.", "success")
    except Exception as e:
        db.session.rollback()
        flash("An error occurred while canceling the loan.", "danger")
        current_app.logger.error(f"Error canceling loan {loan_id}: {e}")
    
    # Redirect back to the original conversation
    original_message = Message.query.filter_by(loan_request_id=loan.id).order_by(Message.timestamp.asc()).first()
    return redirect(url_for('main.view_conversation', message_id=original_message.id))

@main_bp.route('/tag/<uuid:tag_id>')
@login_required
def tag_items(tag_id):
    # Retrieve the tag or return 404 if not found
    tag = Tag.query.get_or_404(tag_id)

    # Get pagination parameters from the request
    page = request.args.get('page', 1, type=int)
    per_page = 12  # Number of items per page (consistent with other pages)

    # Perform a paginated query to retrieve items associated with the tag
    items_pagination = (
        Item.query
        .join(Item.tags)  # Join with tags
        .filter(Tag.id == tag_id)  # Filter by the specific tag
        .options(
            joinedload(Item.owner),
            joinedload(Item.category),
            joinedload(Item.tags)
        )
        .order_by(Item.created_at.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )

    # Extract items from the pagination object
    items = items_pagination.items

    return render_template(
        'main/tag_items.html',
        tag=tag,
        items=items,
        pagination=items_pagination
    )

@main_bp.route('/category/<uuid:category_id>')
@login_required
def category_items(category_id):
    # Retrieve the category or return 404 if not found
    category = Category.query.get_or_404(category_id)

    # Get pagination parameters from the request
    page = request.args.get('page', 1, type=int)
    per_page = 12  # Number of items per page (consistent with other pages)

    # Perform a paginated query to retrieve items associated with the category
    items_pagination = (
        Item.query
        .filter(Item.category_id == category_id)  # Filter by the specific category
        .options(
            joinedload(Item.owner),
            joinedload(Item.category),
            joinedload(Item.tags)
        )
        .order_by(Item.created_at.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )

    # Extract items from the pagination object
    items = items_pagination.items

    return render_template(
        'main/category_items.html',
        category=category,
        items=items,
        pagination=items_pagination
    )

@main_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    form = EditProfileForm()
    if form.validate_on_submit():
        # Handle profile image deletion
        if form.delete_image.data and current_user.profile_image_url:
            delete_file(current_user.profile_image_url)
            current_user.profile_image_url = None
        
        # Handle profile image upload
        if form.profile_image.data:
            if current_user.profile_image_url:
                delete_file(current_user.profile_image_url)
            image_url = upload_profile_image(form.profile_image.data)
            if image_url:
                current_user.profile_image_url = image_url
            else:
                flash('Profile image upload failed. Please ensure you upload a valid image file (JPG, PNG, GIF, etc.).', 'warning')
        
        current_user.about_me = form.about_me.data
        current_user.email_notifications_enabled = form.email_notifications_enabled.data
        db.session.commit()
        flash('Your profile has been updated.', 'success')
        return redirect(url_for('main.profile'))
    elif request.method == 'GET':
        form.about_me.data = current_user.about_me
        form.email_notifications_enabled.data = current_user.email_notifications_enabled
 
    # Pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = 12  # Items per page for logged-in users (same as index page)
    
    # Fetch user's items with pagination (newest first)
    items_pagination = Item.query.filter_by(owner_id=current_user.id).order_by(Item.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    user_items = items_pagination.items
    
    # Create a DeleteItemForm for each item
    delete_forms = {item.id: DeleteItemForm() for item in user_items}
    
    borrowing = current_user.get_active_loans_as_borrower()
    lending = current_user.get_active_loans_as_owner()
    
    return render_template('main/profile.html', 
                         form=form, 
                         user=current_user, 
                         items=user_items, 
                         delete_forms=delete_forms,
                         borrowing=borrowing,
                         lending=lending,
                         pagination=items_pagination)

@main_bp.route('/update-location', methods=['GET', 'POST'])
@login_required
def update_location():
    """Allow users to update their location coordinates"""
    from app.utils.geocoding import geocode_address, build_address_string, GeocodingError
    from datetime import datetime
    
    # Check if user can update location (daily limit)
    if not current_user.can_update_location():
        flash('You can only update your location once per day. Please try again tomorrow.', 'warning')
        return redirect(url_for('main.profile'))
    
    form = UpdateLocationForm()
    
    if form.validate_on_submit():
        # Handle location based on input method
        if form.location_method.data == 'coordinates':
            # Direct coordinate input
            current_user.latitude = form.latitude.data
            current_user.longitude = form.longitude.data
            current_user.geocoded_at = datetime.utcnow()
            current_user.geocoding_failed = False
            db.session.commit()
            flash('Your location has been updated successfully!', 'success')
            return redirect(url_for('main.profile'))
        else:
            # Address geocoding
            address = build_address_string(
                form.street.data, form.city.data, form.state.data, 
                form.zip_code.data, form.country.data
            )
            
            try:
                coordinates = geocode_address(address)
                if coordinates:
                    current_user.latitude, current_user.longitude = coordinates
                    current_user.geocoded_at = datetime.utcnow()
                    current_user.geocoding_failed = False
                    db.session.commit()
                    flash('Your location has been updated successfully!', 'success')
                    return redirect(url_for('main.profile'))
                else:
                    current_user.geocoding_failed = True
                    db.session.commit()
                    flash('We couldn\'t determine your location from that address. '
                          'You can try entering coordinates directly using the second option below.', 'warning')
            except GeocodingError as e:
                current_user.geocoding_failed = True
                db.session.commit()
                current_app.logger.error(f"Geocoding error for user {current_user.email}: {e}")
                flash('There was an error determining your location from that address. '
                      'You can try entering coordinates directly using the second option below.', 'warning')
            except Exception as e:
                current_user.geocoding_failed = True
                db.session.commit()
                current_app.logger.error(f"Unexpected error during geocoding for user {current_user.email}: {e}")
                flash('There was an error determining your location. '
                      'You can try entering coordinates directly using the second option below.', 'error')
    
    return render_template('main/update_location.html', form=form)

@main_bp.route('/user/<uuid:user_id>')
def user_profile(user_id):
    if not current_user.is_authenticated:
        flash('You must be logged in to view user profiles.', 'warning')
        return redirect(url_for('auth.login', next=request.url))
    user = User.query.get_or_404(user_id)
    
    # Pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = 12  # Items per page (consistent with profile and index pages)
    
    # Fetch user's items with pagination (newest first)
    items_pagination = Item.query.filter_by(owner_id=user.id).order_by(Item.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    items = items_pagination.items
    
    # Create DeleteItemForm for each item if the current user is the owner
    delete_forms = {}
    if current_user.is_authenticated and current_user.id == user.id:
        delete_forms = {item.id: DeleteItemForm() for item in items}
    
    return render_template(
        'main/user_profile.html',
        user=user,
        items=items,
        pagination=items_pagination,
        delete_forms=delete_forms
    )

@main_bp.route('/about')
def about():
    return render_template('main/about.html')

# Messaging -----------------------------------------------------

@main_bp.route('/messages')
@login_required
def messages():
    # Subquery to determine the latest message timestamp per conversation
    latest_messages_subquery = db.session.query(
        func.least(Message.sender_id, Message.recipient_id).label('user1_id'),
        func.greatest(Message.sender_id, Message.recipient_id).label('user2_id'),
        Message.item_id,
        func.max(Message.timestamp).label('latest_timestamp')
    ).filter(
        or_(Message.sender_id == current_user.id, Message.recipient_id == current_user.id)
    ).group_by(
        func.least(Message.sender_id, Message.recipient_id),
        func.greatest(Message.sender_id, Message.recipient_id),
        Message.item_id
    ).subquery()

    # Join the subquery with the Message table to get the latest message per conversation
    latest_conversations = db.session.query(Message).join(
        latest_messages_subquery,
        and_(
            func.least(Message.sender_id, Message.recipient_id) == latest_messages_subquery.c.user1_id,
            func.greatest(Message.sender_id, Message.recipient_id) == latest_messages_subquery.c.user2_id,
            Message.item_id == latest_messages_subquery.c.item_id,
            Message.timestamp == latest_messages_subquery.c.latest_timestamp
        )
    ).order_by(Message.timestamp.desc()).all()

    # Prepare conversation summaries
    conversation_summaries = []
    for convo in latest_conversations:
        # Identify the other participant
        if convo.sender_id == current_user.id:
            other_user = User.query.get(convo.recipient_id)
        else:
            other_user = User.query.get(convo.sender_id)
        
        # Calculate unread messages where current_user is the recipient
        unread_count = Message.query.filter(
            Message.item_id == convo.item_id,
            Message.recipient_id == current_user.id,
            Message.sender_id == other_user.id,
            Message.is_read == False
        ).count()
        
        conversation_summaries.append({
            'conversation_id': f"{min(convo.sender_id, convo.recipient_id)}_{max(convo.sender_id, convo.recipient_id)}_{convo.item_id}",
            'other_user': other_user,
            'item': Item.query.get(convo.item_id),
            'latest_message': convo,
            'unread_count': unread_count
        })

    return render_template('messaging/messages.html', conversations=conversation_summaries)

@main_bp.route('/message/<uuid:message_id>', methods=['GET', 'POST'])
@login_required
def view_conversation(message_id):
    message = Message.query.get_or_404(message_id)

    if message.sender_id == current_user.id:
        other_user = User.query.get(message.recipient_id)
    else:
        other_user = User.query.get(message.sender_id)

    # Ensure that only the recipient can view the message
    if message.recipient_id != current_user.id and message.sender_id != current_user.id:
        flash("You do not have permission to view this message.", "danger")
        return redirect(url_for('main.messages'))
    
    # Fetch thread messages
    thread_messages = Message.query.filter(
        Message.item_id == message.item_id,
        or_(
            and_(Message.sender_id == message.sender_id, 
                 Message.recipient_id == message.recipient_id),
            and_(Message.sender_id == message.recipient_id, 
                 Message.recipient_id == message.sender_id)
        )
    ).order_by(Message.timestamp).all()

    # Add other_user to each message
    for msg in thread_messages:
        msg.other_user = msg.recipient if msg.sender_id == current_user.id else msg.sender

    # Mark messages as read, excluding pending loan requests that require action
    unread_messages = Message.query.filter(
        Message.item_id == message.item_id,
        or_(
            and_(
                Message.sender_id == message.sender_id,
                Message.recipient_id == message.recipient_id
            ),
            and_(
                Message.sender_id == message.recipient_id,
                Message.recipient_id == message.sender_id
            )
        ),
        Message.recipient_id == current_user.id,
        Message.is_read == False,
        # Don't mark as read if it's a pending loan request message that needs action
        or_(
            Message.loan_request_id.is_(None),  # Regular messages
            ~Message.loan_request.has(LoanRequest.status == 'pending')  # Non-pending loan requests
        )
    ).all()
    
    for msg in unread_messages:
        msg.is_read = True
    
    try:
        db.session.commit()
    except:
        db.session.rollback()

    # Handle reply form
    form = MessageForm()
    if form.validate_on_submit():
        reply = Message(
            sender_id=current_user.id,
            recipient_id=other_user.id,
            item_id=message.item_id,
            body=form.body.data,
            is_read=False,
            parent_id=message.id
        )
        db.session.add(reply)
        db.session.commit()
        
        # Send email notification to recipient
        try:
            from app.utils.email import send_message_notification_email
            send_message_notification_email(reply)
        except Exception as e:
            current_app.logger.error(f"Failed to send email notification for reply message {reply.id}: {str(e)}")
        
        flash("Your reply has been sent.", "success")
        return redirect(url_for('main.view_conversation', message_id=message_id))

    return render_template('messaging/view_conversation.html', message=message, thread_messages=thread_messages, form=form)


@main_bp.route('/delete_account', methods=['GET', 'POST'])
@login_required
def delete_account():
    """Handle user account deletion with confirmation"""
    form = DeleteAccountForm()
    
    # Get outstanding loans summary for warning
    loans_summary = current_user.get_outstanding_loans_summary()
    
    if form.validate_on_submit():
        try:
            # Perform the cascading deletion
            current_user.delete_account()
            
            # Log the user out since their account is now deleted
            logout_user()
            flash('Your account has been successfully deleted.', 'info')
            return redirect(url_for('main.index'))  # Redirect to home page
        except Exception as e:
            db.session.rollback()
            flash('An error occurred while deleting your account. Please try again or contact support.', 'danger')
            return redirect(url_for('main.delete_account'))
    
    return render_template('main/delete_account.html', form=form, loans_summary=loans_summary)