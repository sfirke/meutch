import random
from flask import render_template, current_app, request, flash, redirect, url_for
from flask_login import login_required, current_user, logout_user
from sqlalchemy import or_, and_, func, select
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import IntegrityError
from datetime import datetime, UTC, timedelta
from app import db
from app.models import Item, LoanRequest, Tag, User, Message, Category, GiveawayInterest, UserWebLink, circle_members
from app.forms import ListItemForm, EditProfileForm, DeleteItemForm, MessageForm, LoanRequestForm, ExtendLoanForm, DeleteAccountForm, UpdateLocationForm, ExpressInterestForm, WithdrawInterestForm, SelectRecipientForm, ChangeRecipientForm, ReleaseToAllForm, ConfirmHandoffForm, EmptyForm
from app.main import bp as main_bp
from app.utils.storage import delete_file, upload_item_image, upload_profile_image, is_valid_file_upload
from app.utils.geocoding import sort_items_by_owner_distance
from app.utils.pagination import ListPagination
from app.utils.email import send_message_notification_email

@main_bp.route('/')
def index():
    circles = []
    items = []
    pagination = None
    total_items = 0
    remaining_items = 0
    
    if current_user.is_authenticated:
        circles = current_user.circles
        
        # For logged-in users: show items from users who share circles with them
        has_circles = len(current_user.circles) > 0
        
        if has_circles:
            shared_circle_user_ids = current_user.get_shared_circle_user_ids_query()
            # Query items from those users, excluding own items, ordered by newest first
            base_query = Item.query.filter(
                Item.owner_id.in_(shared_circle_user_ids),
                Item.owner_id != current_user.id
            ).order_by(Item.created_at.desc())
            
            # Paginate results
            page = request.args.get('page', 1, type=int)
            per_page = 12  # Items per page for logged-in users
            pagination = base_query.paginate(page=page, per_page=per_page, error_out=False)
            items = pagination.items
        # else: user has no circles, items list stays empty
        
    else:
        # For anonymous users: show items from public showcase users only
        showcase_user_ids = select(User.id).where(User.is_public_showcase == True)
        
        base_query = Item.query.filter(Item.owner_id.in_(showcase_user_ids))
        
        # Show limited items with count
        preview_limit = 12  # Items to show for preview
        total_items = base_query.count()
        # Random selection for variety instead of newest first
        items = base_query.order_by(func.random()).limit(preview_limit).all()
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
            image_url=image_url,
            is_giveaway=form.is_giveaway.data,
            giveaway_visibility=form.giveaway_visibility.data if form.is_giveaway.data else None,
            claim_status='unclaimed' if form.is_giveaway.data else None
        )

        db.session.add(new_item)
        
        tag_input = form.tags.data.strip() if form.tags.data else ''
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

@main_bp.route('/giveaways')
@login_required
def giveaways():
    """Display feed of available giveaways with sorting and filtering options"""
    page = request.args.get('page', 1, type=int)
    sort_by = request.args.get('sort', 'date')  # 'date' or 'distance'
    max_distance = request.args.get('distance', type=int)  # Optional distance filter in miles
    per_page = 12
    
    # Check if user has any circles
    has_circles = len(current_user.circles) > 0
    
    # Get user's own active giveaways (unclaimed or pending_pickup, always show these regardless of circle status)
    my_giveaways = Item.query.filter(
        Item.owner_id == current_user.id,
        Item.is_giveaway == True,
        or_(Item.claim_status == 'unclaimed', Item.claim_status == 'pending_pickup', Item.claim_status.is_(None))
    ).order_by(Item.created_at.desc()).all()
    
    if not has_circles:
        return render_template('main/giveaways.html', 
                             items=[], 
                             my_giveaways=my_giveaways,
                             pagination=None, 
                             no_circles=True,
                             sort_by=sort_by,
                             max_distance=max_distance)
    
    # Get users who share circles with current user
    shared_circle_user_ids = current_user.get_shared_circle_user_ids_query()
    
    # Get all users who belong to any circle (for public giveaways)
    all_circle_user_ids = select(circle_members.c.user_id).distinct()
    
    # Base query: giveaways that are unclaimed, excluding own items
    # Include items that meet either condition:
    # 1. Default visibility from shared circle users
    # 2. Public visibility from any circle member
    base_query = Item.query.filter(
        Item.is_giveaway == True,
        and_(
            or_(Item.claim_status == 'unclaimed', Item.claim_status.is_(None)),
            or_(
                # Default visibility: must share circles with owner
                and_(
                    or_(Item.giveaway_visibility == 'default', Item.giveaway_visibility.is_(None)),
                    Item.owner_id.in_(shared_circle_user_ids)
                ),
                # Public visibility: owner just needs to be in any circle
                and_(
                    Item.giveaway_visibility == 'public',
                    Item.owner_id.in_(all_circle_user_ids)
                )
            ),
            Item.owner_id != current_user.id
        )
    ).join(Item.owner)
    
    # Apply distance filtering if requested and both users are geocoded
    if max_distance and current_user.is_geocoded:
        # We need to filter after getting all items since distance calculation requires
        # comparing user coordinates. Get all matching items first.
        all_items = base_query.all()
        
        # Filter by distance
        filtered_items = []
        for item in all_items:
            if item.owner.is_geocoded:
                distance = current_user.distance_to(item.owner)
                if distance and distance <= max_distance:
                    filtered_items.append(item)
        
        # Sort based on sort_by parameter
        if sort_by == 'distance':
            # Sort by distance (already calculated)
            filtered_items.sort(key=lambda item: current_user.distance_to(item.owner) or float('inf'))
        else:  # sort_by == 'date'
            # Sort by newest first
            filtered_items.sort(key=lambda item: item.created_at, reverse=True)
        
        # Manual pagination for distance-filtered results
        # ListPagination handles slicing internally
        pagination = ListPagination(filtered_items, page, per_page)
        items = pagination.items
    
    else:
        # No distance filter - can use database sorting and pagination
        if sort_by == 'distance' and current_user.is_geocoded:
            # Get all items and sort by distance
            all_items = base_query.all()
            sorted_items = sort_items_by_owner_distance(all_items, current_user)
            
            # Manual pagination
            # ListPagination handles slicing internally
            pagination = ListPagination(sorted_items, page, per_page)
            items = pagination.items
        else:
            # Date sort - use database ordering
            base_query = base_query.order_by(Item.created_at.desc())
            pagination = base_query.paginate(page=page, per_page=per_page, error_out=False)
            items = pagination.items
    
    return render_template('main/giveaways.html',
                         items=items,
                         my_giveaways=my_giveaways,
                         pagination=pagination,
                         no_circles=False,
                         sort_by=sort_by,
                         max_distance=max_distance)

@main_bp.route('/search', methods=['GET', 'POST'])
@login_required
def search():
    query = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)
    item_type = request.args.get('item_type', 'both')  # 'loans', 'giveaways', or 'both'
    per_page = 12  # Number of items per page (consistent with other pages)

    # Check if user has any circles
    has_circles = len(current_user.circles) > 0
    shared_circle_user_ids = current_user.get_shared_circle_user_ids_query() if has_circles else None

    if request.method == 'GET' and not query:
        # Display the search form
        return render_template('search_items.html', has_circles=has_circles, item_type=item_type)

    if not query:
        flash('Please enter a search term.', 'warning')
        return redirect(url_for('main.search'))
    
    # If user has no circles, show empty results with prompt
    if not has_circles:
        return render_template('search_results.html', items=[], query=query, pagination=None, has_circles=False, item_type=item_type)
    
    # Get all users who belong to any circle (for public giveaways)
    all_circle_user_ids = select(circle_members.c.user_id).distinct()
    
    # Perform case-insensitive search on name, description, and tags
    # Include items that meet search criteria AND either:
    # 1. Are from shared circle users (for default visibility items and loans)
    # 2. Are public giveaways from any circle member
    items_query = Item.query.outerjoin(Item.tags).outerjoin(Item.category).filter(
        and_(
            or_(
                # Default items (loans and default-visibility giveaways): must share circles
                and_(
                    or_(Item.giveaway_visibility == 'default', Item.giveaway_visibility.is_(None)),
                    Item.owner_id.in_(shared_circle_user_ids)
                ),
                # Public giveaways: owner just needs to be in any circle
                and_(
                    Item.giveaway_visibility == 'public',
                    Item.owner_id.in_(all_circle_user_ids)
                )
            ),
            or_(
                Item.name.ilike(f'%{query}%'),
                Item.description.ilike(f'%{query}%'),
                Tag.name.ilike(f'%{query}%')
            )
        )
    )
    
    # Apply item_type filter
    if item_type == 'loans':
        items_query = items_query.filter(Item.is_giveaway == False)
    elif item_type == 'giveaways':
        items_query = items_query.filter(
            Item.is_giveaway == True,
            or_(Item.claim_status == 'unclaimed', Item.claim_status.is_(None))
        )
    # 'both' - no additional filtering needed
    
    items_query = items_query.distinct()
    
    # Get all matching items for distance sorting
    all_items = items_query.all()
    
    # Sort by distance from current user
    sorted_items = sort_items_by_owner_distance(all_items, current_user)
    
    # Paginate the sorted results
    pagination = ListPagination(items=sorted_items, page=page, per_page=per_page)

    return render_template('search_results.html', items=pagination.items, query=query, pagination=pagination, has_circles=True, item_type=item_type)

@main_bp.route('/item/<uuid:item_id>', methods=['GET', 'POST'])
@login_required
def item_detail(item_id):
    item = db.get_or_404(Item, item_id)
    
    # Initialize forms
    form = MessageForm()
    express_interest_form = ExpressInterestForm()
    withdraw_interest_form = WithdrawInterestForm()
    
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
            send_message_notification_email(message)
        except Exception as e:
            current_app.logger.error(f"Failed to send email notification for message {message.id}: {str(e)}")
        
        flash("Your message has been sent.", "success")
        return redirect(url_for('main.item_detail', item_id=item.id))
    
    # Retrieve messages related to this item (optional)
    messages = Message.query.filter_by(item_id=item.id, recipient_id=current_user.id).order_by(Message.timestamp.desc()).all()
    
    # Check if current user has expressed interest in this giveaway
    user_interest = None
    if item.is_giveaway:
        user_interest = GiveawayInterest.query.filter_by(
            item_id=item.id,
            user_id=current_user.id
        ).first()
    
    # Get count of interested users for owner
    interested_count = 0
    if item.is_giveaway and item.owner_id == current_user.id:
        interested_count = GiveawayInterest.query.filter_by(
            item_id=item.id,
            status='active'
        ).count()
    
    delete_form = DeleteItemForm()
    release_to_all_form = ReleaseToAllForm()
    confirm_handoff_form = ConfirmHandoffForm()
    return render_template('main/item_detail.html', 
                         item=item, 
                         form=form, 
                         messages=messages, 
                         delete_form=delete_form,
                         user_interest=user_interest,
                         interested_count=interested_count,
                         express_interest_form=express_interest_form,
                         withdraw_interest_form=withdraw_interest_form,
                         release_to_all_form=release_to_all_form,
                         confirm_handoff_form=confirm_handoff_form)


@main_bp.route('/item/<uuid:item_id>/express-interest', methods=['POST'])
@login_required
def express_interest(item_id):
    """Allow a user to express interest in claiming a giveaway"""
    item = db.get_or_404(Item, item_id)
    form = ExpressInterestForm()
    
    # Validation: item must be a giveaway
    if not item.is_giveaway:
        flash('This item is not a giveaway.', 'danger')
        return redirect(url_for('main.item_detail', item_id=item.id))
    
    # Validation: item must be unclaimed
    if item.claim_status not in [None, 'unclaimed']:
        flash('This giveaway is no longer available.', 'warning')
        return redirect(url_for('main.item_detail', item_id=item.id))
    
    # Validation: user cannot express interest in own item
    if item.owner_id == current_user.id:
        flash('You cannot express interest in your own giveaway.', 'warning')
        return redirect(url_for('main.item_detail', item_id=item.id))
    
    if form.validate_on_submit():
        # Get optional message from form
        message_text = form.message.data.strip() if form.message.data else None
        
        # Create GiveawayInterest record
        try:
            interest = GiveawayInterest(
                item_id=item.id,
                user_id=current_user.id,
                message=message_text,
                status='active'
            )
            db.session.add(interest)
            db.session.commit()
            flash('Your interest has been recorded! The owner will contact you if you are selected.', 'success')
        except IntegrityError:
            db.session.rollback()
            flash('You have already expressed interest in this giveaway.', 'info')
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error expressing interest in giveaway {item_id}: {str(e)}")
            flash('An error occurred. Please try again.', 'danger')
    
    return redirect(url_for('main.item_detail', item_id=item.id))


@main_bp.route('/item/<uuid:item_id>/withdraw-interest', methods=['POST'])
@login_required
def withdraw_interest(item_id):
    """Allow a user to withdraw their interest in a giveaway"""
    item = db.get_or_404(Item, item_id)
    form = WithdrawInterestForm()
    
    if not form.validate_on_submit():
        flash('Invalid request.', 'danger')
        return redirect(url_for('main.item_detail', item_id=item.id))
    
    # Find the user's interest record
    interest = GiveawayInterest.query.filter_by(
        item_id=item.id,
        user_id=current_user.id
    ).first()
    
    if not interest:
        flash('You have not expressed interest in this giveaway.', 'warning')
        return redirect(url_for('main.item_detail', item_id=item.id))
    
    # Delete the interest record
    try:
        db.session.delete(interest)
        db.session.commit()
        flash('Your interest has been withdrawn.', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error withdrawing interest from giveaway {item_id}: {str(e)}")
        flash('An error occurred. Please try again.', 'danger')
    
    return redirect(url_for('main.item_detail', item_id=item.id))


@main_bp.route('/item/<uuid:item_id>/select-recipient', methods=['GET', 'POST'])
@login_required
def select_recipient(item_id):
    """Owner views interested users and selects a recipient for a giveaway"""
    item = db.get_or_404(Item, item_id)
    
    # Validation: user must be owner
    if item.owner_id != current_user.id:
        flash('You do not have permission to manage this giveaway.', 'danger')
        return redirect(url_for('main.item_detail', item_id=item.id))
    
    # Validation: item must be a giveaway
    if not item.is_giveaway:
        flash('This item is not a giveaway.', 'danger')
        return redirect(url_for('main.item_detail', item_id=item.id))
    
    # Validation: item must be unclaimed or pending_pickup
    if item.claim_status not in [None, 'unclaimed', 'pending_pickup']:
        flash('This giveaway has already been claimed.', 'warning')
        return redirect(url_for('main.item_detail', item_id=item.id))
    
    # Create forms for each selection method
    first_form = SelectRecipientForm(selection_method='first')
    random_form = SelectRecipientForm(selection_method='random')
    manual_form = SelectRecipientForm(selection_method='manual')
    
    # Handle POST request (recipient selection)
    if request.method == 'POST':
        # Determine which form was submitted and validate it
        selection_method = request.form.get('selection_method')
        
        if selection_method == 'first' and first_form.validate_on_submit():
            form = first_form
        elif selection_method == 'random' and random_form.validate_on_submit():
            form = random_form
        elif selection_method == 'manual' and manual_form.validate_on_submit():
            form = manual_form
        else:
            flash('Invalid selection. Please try again.', 'danger')
            return redirect(url_for('main.select_recipient', item_id=item.id))
        
        # Get all active interests
        active_interests = GiveawayInterest.query.filter_by(
            item_id=item.id,
            status='active'
        ).order_by(GiveawayInterest.created_at).all()
        
        if not active_interests:
            flash('No interested users found.', 'warning')
            return redirect(url_for('main.item_detail', item_id=item.id))
        
        # Determine selected user based on method
        selected_interest = None
        if selection_method == 'first':
            selected_interest = active_interests[0]
        elif selection_method == 'random':
            selected_interest = random.choice(active_interests)
        elif selection_method == 'manual':
            manual_user_id = form.user_id.data
            selected_interest = GiveawayInterest.query.filter_by(
                item_id=item.id,
                user_id=manual_user_id,
                status='active'
            ).first()
        
        if not selected_interest:
            flash('Invalid selection. Please try again.', 'danger')
            return redirect(url_for('main.select_recipient', item_id=item.id))
        
        try:
            # Update item status
            item.claim_status = 'pending_pickup'
            item.claimed_by_id = selected_interest.user_id
            item.available = False
            # claimed_at remains NULL until handoff is confirmed
            
            # Update the selected interest status
            selected_interest.status = 'selected'
            
            # Create notification message to selected user
            notification_message = Message(
                sender_id=current_user.id,
                recipient_id=selected_interest.user_id,
                item_id=item.id,
                body=f"Good news! You've been selected for the giveaway '{item.name}'! Please coordinate pickup with the owner."
            )
            db.session.add(notification_message)
            
            db.session.commit()
            
            # Send email notification
            try:
                send_message_notification_email(notification_message)
            except Exception as e:
                current_app.logger.error(f"Failed to send email notification for giveaway selection: {str(e)}")
            
            flash(f'{selected_interest.user.full_name} has been selected! They will be notified.', 'success')
            return redirect(url_for('main.item_detail', item_id=item.id))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error selecting recipient for giveaway {item_id}: {str(e)}")
            flash('An error occurred. Please try again.', 'danger')
            return redirect(url_for('main.select_recipient', item_id=item.id))
    
    # GET request - show selection page
    is_reassignment = (item.claim_status == 'pending_pickup')
    
    # Show active interests and any selected interest (for reassignment case)
    # When not reassigning, there won't be any selected interests, so this works for both cases
    interested_users = GiveawayInterest.query.filter(
        GiveawayInterest.item_id == item.id,
        GiveawayInterest.status.in_(['active', 'selected'])
    ).order_by(GiveawayInterest.created_at).all()
    
    if not interested_users:
        flash('No users have expressed interest in this giveaway yet.', 'info')
        return redirect(url_for('main.item_detail', item_id=item.id))
    
    # Gather messaging information for each interested user
    user_messaging_info = {}
    for interest in interested_users:
        # Check for existing conversation between owner and this user about this item
        conversation_messages = Message.query.filter(
            Message.item_id == item.id,
            or_(
                and_(Message.sender_id == current_user.id, 
                     Message.recipient_id == interest.user_id),
                and_(Message.sender_id == interest.user_id, 
                     Message.recipient_id == current_user.id)
            )
        ).order_by(Message.timestamp).all()
        
        has_conversation = len(conversation_messages) > 0
        
        # Count unread messages from this user to the owner
        unread_count = sum(1 for msg in conversation_messages 
                          if msg.recipient_id == current_user.id and not msg.is_read)
        
        # Get the most recent message for preview
        latest_message = conversation_messages[-1] if conversation_messages else None
        
        user_messaging_info[str(interest.user_id)] = {
            'has_conversation': has_conversation,
            'unread_count': unread_count,
            'message_count': len(conversation_messages),
            'latest_message': latest_message
        }
    
    # Create forms for change-recipient (used when is_reassignment=True)
    next_form = ChangeRecipientForm(selection_method='next')
    random_reassign_form = ChangeRecipientForm(selection_method='random')
    manual_reassign_form = ChangeRecipientForm(selection_method='manual')
    
    return render_template('main/select_recipient.html', 
                         item=item, 
                         interested_users=interested_users,
                         user_messaging_info=user_messaging_info,
                         is_reassignment=is_reassignment,
                         first_form=first_form,
                         random_form=random_form,
                         manual_form=manual_form,
                         next_form=next_form,
                         random_reassign_form=random_reassign_form,
                         manual_reassign_form=manual_reassign_form)


@main_bp.route('/item/<uuid:item_id>/message-requester/<uuid:user_id>', methods=['GET', 'POST'])
@login_required
def message_giveaway_requester(item_id, user_id):
    """Allow giveaway owner to initiate a message with an interested user"""
    item = db.get_or_404(Item, item_id)
    
    # Validation: user must be owner
    if item.owner_id != current_user.id:
        flash('You do not have permission to message requesters for this item.', 'danger')
        return redirect(url_for('main.item_detail', item_id=item.id))
    
    # Validation: item must be a giveaway
    if not item.is_giveaway:
        flash('This item is not a giveaway.', 'danger')
        return redirect(url_for('main.item_detail', item_id=item.id))
    
    # Get the target user
    target_user = db.get_or_404(User, user_id)
    
    # Validation: target user must have expressed interest
    interest = GiveawayInterest.query.filter_by(
        item_id=item.id,
        user_id=user_id
    ).first()
    
    if not interest:
        flash('This user has not expressed interest in this giveaway.', 'warning')
        return redirect(url_for('main.select_recipient', item_id=item.id))
    
    # Check if a conversation already exists
    existing_message = Message.query.filter(
        Message.item_id == item.id,
        or_(
            and_(Message.sender_id == current_user.id, Message.recipient_id == user_id),
            and_(Message.sender_id == user_id, Message.recipient_id == current_user.id)
        )
    ).first()
    
    if existing_message:
        # Redirect to existing conversation
        return redirect(url_for('main.view_conversation', message_id=existing_message.id))
    
    # Handle form submission
    form = MessageForm()
    if form.validate_on_submit():
        # Create new message
        message = Message(
            sender_id=current_user.id,
            recipient_id=user_id,
            item_id=item.id,
            body=form.body.data
        )
        db.session.add(message)
        
        try:
            db.session.commit()
            
            # Send email notification to recipient
            try:
                send_message_notification_email(message)
            except Exception as e:
                current_app.logger.error(f"Failed to send email notification for message {message.id}: {str(e)}")
            
            flash('Your message has been sent.', 'success')
            return redirect(url_for('main.view_conversation', message_id=message.id))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error sending message for giveaway {item_id}: {str(e)}")
            flash('An error occurred. Please try again.', 'danger')
    
    return render_template('main/message_requester.html', 
                         form=form, 
                         item=item, 
                         target_user=target_user,
                         interest=interest)


@main_bp.route('/item/<uuid:item_id>/change-recipient', methods=['POST'])
@login_required
def change_recipient(item_id):
    """Owner changes the recipient of a giveaway that's pending pickup."""
    item = db.get_or_404(Item, item_id)
    
    # Validation: user must be owner
    if item.owner_id != current_user.id:
        flash('You do not have permission to manage this giveaway.', 'danger')
        return redirect(url_for('main.item_detail', item_id=item.id))
    
    # Validation: item must be a giveaway
    if not item.is_giveaway:
        flash('This item is not a giveaway.', 'danger')
        return redirect(url_for('main.item_detail', item_id=item.id))
    
    # Validation: item must be pending_pickup
    if item.claim_status != 'pending_pickup':
        flash('This giveaway is not pending pickup.', 'warning')
        return redirect(url_for('main.item_detail', item_id=item.id))
    
    form = ChangeRecipientForm()
    
    if not form.validate_on_submit():
        flash('Invalid request.', 'danger')
        return redirect(url_for('main.select_recipient', item_id=item.id))
    
    selection_method = form.selection_method.data
    
    # Get the current claimed_by_id to exclude from selection
    previous_claimed_by_id = item.claimed_by_id
    
    # Get all active interests, excluding the previous recipient
    active_interests = GiveawayInterest.query.filter(
        GiveawayInterest.item_id == item.id,
        GiveawayInterest.status == 'active',
        GiveawayInterest.user_id != previous_claimed_by_id
    ).order_by(GiveawayInterest.created_at).all()
    
    if not active_interests:
        flash('No other interested users available to select.', 'warning')
        return redirect(url_for('main.select_recipient', item_id=item.id))
    
    # Determine selected user based on method
    selected_interest = None
    if selection_method == 'next':
        selected_interest = active_interests[0]
    elif selection_method == 'random':
        selected_interest = random.choice(active_interests)
    elif selection_method == 'manual':
        manual_user_id = form.user_id.data
        # Check if they selected the current recipient (convert to string for comparison)
        if str(manual_user_id) == str(previous_claimed_by_id):
            flash('That recipient is currently selected.', 'warning')
            return redirect(url_for('main.select_recipient', item_id=item.id))
        selected_interest = GiveawayInterest.query.filter(
            GiveawayInterest.item_id == item.id,
            GiveawayInterest.user_id == manual_user_id,
            GiveawayInterest.status == 'active',
            GiveawayInterest.user_id != previous_claimed_by_id
        ).first()
    
    if not selected_interest:
        flash('Invalid selection. Please try again.', 'danger')
        return redirect(url_for('main.select_recipient', item_id=item.id))
    
    try:
        # Reset previous recipient's interest status to active
        previous_interest = GiveawayInterest.query.filter_by(
            item_id=item.id,
            user_id=previous_claimed_by_id
        ).first()
        if previous_interest:
            previous_interest.status = 'active'
        
        # Notify previous recipient that they are no longer selected
        previous_recipient = db.session.get(User, previous_claimed_by_id)
        if previous_recipient:
            previous_notification = Message(
                sender_id=current_user.id,
                recipient_id=previous_recipient.id,
                item_id=item.id,
                body=f"The owner has selected a different recipient for the giveaway '{item.name}'. Your interest remains active and you may still be selected in the future."
            )
            db.session.add(previous_notification)
        
        # Update item status - keep pending_pickup, update claimed_by_id
        item.claimed_by_id = selected_interest.user_id
        # claimed_at remains NULL until handoff is confirmed
        
        # Update the selected interest status
        selected_interest.status = 'selected'
        
        # Create notification message to newly selected user
        notification_message = Message(
            sender_id=current_user.id,
            recipient_id=selected_interest.user_id,
            item_id=item.id,
            body=f"Good news! You've been selected for the giveaway '{item.name}'! Please coordinate pickup with the owner."
        )
        db.session.add(notification_message)
        
        db.session.commit()
        
        # Send email notification
        try:
            send_message_notification_email(notification_message)
        except Exception as e:
            current_app.logger.error(f"Failed to send email notification for giveaway reassignment: {str(e)}")
        
        flash(f'{selected_interest.user.full_name} has been selected! They will be notified.', 'success')
        return redirect(url_for('main.item_detail', item_id=item.id))
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error changing recipient for giveaway {item_id}: {str(e)}")
        flash('An error occurred. Please try again.', 'danger')
        return redirect(url_for('main.select_recipient', item_id=item.id))


@main_bp.route('/item/<uuid:item_id>/release-to-all', methods=['POST'])
@login_required
def release_to_all(item_id):
    """Owner releases a giveaway back to unclaimed status."""
    item = db.get_or_404(Item, item_id)
    
    # Validation: user must be owner
    if item.owner_id != current_user.id:
        flash('You do not have permission to manage this giveaway.', 'danger')
        return redirect(url_for('main.item_detail', item_id=item.id))
    
    # Validation: item must be a giveaway
    if not item.is_giveaway:
        flash('This item is not a giveaway.', 'danger')
        return redirect(url_for('main.item_detail', item_id=item.id))
    
    # Validation: item must be pending_pickup
    if item.claim_status != 'pending_pickup':
        flash('This giveaway is not pending pickup.', 'warning')
        return redirect(url_for('main.item_detail', item_id=item.id))
    
    form = ReleaseToAllForm()
    
    if not form.validate_on_submit():
        flash('Invalid request.', 'danger')
        return redirect(url_for('main.item_detail', item_id=item.id))
    
    try:
        # Reset the previously selected user's interest status to active
        previous_recipient_id = item.claimed_by_id
        if previous_recipient_id:
            previous_interest = GiveawayInterest.query.filter_by(
                item_id=item.id,
                user_id=previous_recipient_id
            ).first()
            if previous_interest:
                previous_interest.status = 'active'
            
            # Notify previous recipient that the giveaway has been released back to everyone
            release_notification = Message(
                sender_id=current_user.id,
                recipient_id=previous_recipient_id,
                item_id=item.id,
                body=f"The owner has released the giveaway '{item.name}' back to everyone. Your interest remains active and you may still be selected."
            )
            db.session.add(release_notification)
        
        # Update item status
        item.claim_status = 'unclaimed'
        item.claimed_by_id = None
        # claimed_at stays NULL
        item.available = True
        
        db.session.commit()
        
        flash('The giveaway has been released and will reappear in the feed. All interested users remain in the pool.', 'success')
        return redirect(url_for('main.item_detail', item_id=item.id))
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error releasing giveaway {item_id} to all: {str(e)}")
        flash('An error occurred. Please try again.', 'danger')
        return redirect(url_for('main.item_detail', item_id=item.id))


@main_bp.route('/item/<uuid:item_id>/confirm-handoff', methods=['POST'])
@login_required
def confirm_handoff(item_id):
    """Owner confirms the handoff of a giveaway is complete."""
    item = db.get_or_404(Item, item_id)
    
    # Validation: user must be owner
    if item.owner_id != current_user.id:
        flash('You do not have permission to manage this giveaway.', 'danger')
        return redirect(url_for('main.item_detail', item_id=item.id))
    
    # Validation: item must be a giveaway
    if not item.is_giveaway:
        flash('This item is not a giveaway.', 'danger')
        return redirect(url_for('main.item_detail', item_id=item.id))
    
    # Validation: item must be pending_pickup
    if item.claim_status != 'pending_pickup':
        flash('This giveaway is not pending pickup.', 'warning')
        return redirect(url_for('main.item_detail', item_id=item.id))
    
    form = ConfirmHandoffForm()
    
    if not form.validate_on_submit():
        flash('Invalid request.', 'danger')
        return redirect(url_for('main.item_detail', item_id=item.id))
    
    try:
        # Update item to claimed status
        item.claim_status = 'claimed'
        item.claimed_at = datetime.now(UTC)
        # claimed_by_id remains unchanged
        item.available = False  # Should already be False, but enforce
        
        db.session.commit()
        
        recipient_name = item.claimed_by.full_name if item.claimed_by else 'the recipient'
        flash(f'Handoff complete! The giveaway has been successfully given to {recipient_name}.', 'success')
        return redirect(url_for('main.item_detail', item_id=item.id))
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error confirming handoff for giveaway {item_id}: {str(e)}")
        flash('An error occurred. Please try again.', 'danger')
        return redirect(url_for('main.item_detail', item_id=item.id))


@main_bp.route('/items/<uuid:item_id>/request', methods=['GET', 'POST'])
@login_required
def request_item(item_id):
    item = db.get_or_404(Item, item_id)
    
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
    item = db.get_or_404(Item, item_id)
    if item.owner != current_user:
        flash('You do not have permission to edit this item.', 'danger')
        return redirect(url_for('main.profile'))
    
    form = ListItemForm(obj=item)

    if request.method == 'GET':
        # Prepopulate giveaway fields
        form.is_giveaway.data = item.is_giveaway
        form.giveaway_visibility.data = item.giveaway_visibility

    if form.validate_on_submit():
        item.name = form.name.data
        item.description = form.description.data
        item.category_id = form.category.data
        
        # Update giveaway fields
        item.is_giveaway = form.is_giveaway.data
        item.giveaway_visibility = form.giveaway_visibility.data if form.is_giveaway.data else None
        # Set claim_status if switching to giveaway
        if form.is_giveaway.data and not item.claim_status:
            item.claim_status = 'unclaimed'
        # Clear claim_status if switching from giveaway to loan
        elif not form.is_giveaway.data:
            item.claim_status = None
        
        # Update tags
        tag_input = form.tags.data.strip() if form.tags.data else ''
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
        # After editing an item, redirect the user back to the item's detail page
        return redirect(url_for('main.item_detail', item_id=item.id))
    
    # Prepopulate category and tags fields
    form.category.data = str(item.category_id)
    form.tags.data = ', '.join([tag.name for tag in item.tags])
    
    return render_template('main/edit_item.html', form=form, item=item)


@main_bp.route('/item/<uuid:item_id>/delete', methods=['POST'])
@login_required
def delete_item(item_id):
    item = db.get_or_404(Item, item_id)
    
    # Check if user owns the item
    if item.owner != current_user:
        flash('You can only delete your own items.', 'danger')
        return redirect(url_for('main.profile'))
    
    # Prevent deletion of claimed giveaways (completed transactions)
    if item.is_giveaway and item.claim_status == 'claimed':
        flash('You cannot delete a giveaway that has been claimed and handed off. This is a completed transaction.', 'danger')
        return redirect(url_for('main.profile'))
    
    try:
        # Start by deleting messages associated with loan requests
        Message.query.filter(
            Message.item_id == item_id
        ).delete()

        # Delete all loan requests for this item
        LoanRequest.query.filter_by(item_id=item_id).delete()
        
        # Delete all giveaway interest records for this item
        GiveawayInterest.query.filter_by(item_id=item_id).delete()
        
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
    form = EmptyForm()
    if not form.validate_on_submit():
        flash("Invalid request.", "danger")
        return redirect(url_for('main.messages'))
    
    loan = db.get_or_404(LoanRequest, loan_id)
    
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
    form = EmptyForm()
    if not form.validate_on_submit():
        flash("Invalid request.", "danger")
        return redirect(url_for('main.messages'))
    
    loan = db.get_or_404(LoanRequest, loan_id)
    
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
    form = EmptyForm()
    if not form.validate_on_submit():
        flash("Invalid request.", "danger")
        return redirect(url_for('main.messages'))
    
    loan = db.get_or_404(LoanRequest, loan_id)
    
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
    form = EmptyForm()
    if not form.validate_on_submit():
        flash("Invalid request.", "danger")
        return redirect(url_for('main.messages'))
    
    loan = db.get_or_404(LoanRequest, loan_id)
    
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

@main_bp.route('/loan/<uuid:loan_id>/extend', methods=['GET', 'POST'])
@login_required
def extend_loan(loan_id):
    """Allow item owner to extend the loan due date"""
    loan = db.get_or_404(LoanRequest, loan_id)
    
    # Check if the current user is the owner of the item
    if loan.item.owner_id != current_user.id:
        flash("You are not authorized to extend this loan.", "danger")
        return redirect(url_for('main.messages'))
    
    # Can extend pending or approved loans only
    if loan.status not in ['pending', 'approved']:
        flash("Only pending or approved loans can be extended.", "warning")
        return redirect(url_for('main.messages'))
    
    form = ExtendLoanForm(current_end_date=loan.end_date)
    
    if form.validate_on_submit():
        old_end_date = loan.end_date
        loan.end_date = form.new_end_date.data
        
        # Reset reminder flags since the due date has changed
        loan.due_soon_reminder_sent = None
        loan.due_date_reminder_sent = None
        loan.last_overdue_reminder_sent = None
        loan.overdue_reminder_count = 0
        
        # Create notification message to borrower
        if form.message.data and form.message.data.strip():
            message_body = f"The loan of '{loan.item.name}' has been extended until {form.new_end_date.data.strftime('%B %d, %Y')}.\n\nMessage from owner: {form.message.data}"
        else:
            message_body = f"Good news! The loan of '{loan.item.name}' has been extended. The new due date is {form.new_end_date.data.strftime('%B %d, %Y')} (previously {old_end_date.strftime('%B %d, %Y')})."
        
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
            
            # Send email notification to borrower
            try:
                send_message_notification_email(message)
            except Exception as e:
                current_app.logger.error(f"Failed to send email notification for loan extension message {message.id}: {str(e)}")
            
            flash(f"Loan has been extended until {form.new_end_date.data.strftime('%B %d, %Y')}.", "success")
        except Exception as e:
            db.session.rollback()
            flash("An error occurred while extending the loan.", "danger")
            current_app.logger.error(f"Error extending loan {loan_id}: {e}")
        
        # Redirect back to the original conversation
        original_message = Message.query.filter_by(loan_request_id=loan.id).order_by(Message.timestamp.asc()).first()
        return redirect(url_for('main.view_conversation', message_id=original_message.id))
    
    return render_template('main/extend_loan.html', form=form, loan=loan)

@main_bp.route('/tag/<uuid:tag_id>')
@login_required
def tag_items(tag_id):
    # Retrieve the tag or return 404 if not found
    tag = db.get_or_404(Tag, tag_id)

    # Get pagination parameters from the request
    page = request.args.get('page', 1, type=int)
    item_type = request.args.get('item_type', 'both')  # 'loans', 'giveaways', or 'both'
    per_page = 12  # Number of items per page (consistent with other pages)
    
    # Get circle member IDs for filtering
    has_circles = len(current_user.circles) > 0
    
    if not has_circles:
        # User has no circles - show prompt to join
        return render_template(
            'main/tag_items.html',
            tag=tag,
            items=[],
            pagination=None,
            no_circles=True,
            item_type=item_type
        )
    
    shared_circle_user_ids = current_user.get_shared_circle_user_ids_query()
    
    # Build base query for items with this tag from shared circle users
    items_query = Item.query.join(Item.tags).filter(
        Tag.id == tag_id,  # Filter by the specific tag
        Item.owner_id.in_(shared_circle_user_ids)  # Filter by circle membership
    )
    
    # Apply item_type filter
    if item_type == 'loans':
        items_query = items_query.filter(Item.is_giveaway == False)
    elif item_type == 'giveaways':
        items_query = items_query.filter(
            Item.is_giveaway == True,
            or_(Item.claim_status == 'unclaimed', Item.claim_status.is_(None))
        )
    # 'both' - no additional filtering needed
    
    # Perform a paginated query to retrieve items
    items_pagination = (
        items_query
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
        pagination=items_pagination,
        no_circles=False,
        item_type=item_type
    )

@main_bp.route('/category/<uuid:category_id>')
@login_required
def category_items(category_id):
    # Retrieve the category or return 404 if not found
    category = db.get_or_404(Category, category_id)

    # Get pagination parameters from the request
    page = request.args.get('page', 1, type=int)
    item_type = request.args.get('item_type', 'both')  # 'loans', 'giveaways', or 'both'
    per_page = 12  # Number of items per page (consistent with other pages)

    # Get circle member IDs for filtering
    has_circles = len(current_user.circles) > 0
    
    if not has_circles:
        # User has no circles - show prompt to join
        return render_template(
            'main/category_items.html',
            category=category,
            items=[],
            pagination=None,
            no_circles=True,
            item_type=item_type
        )

    shared_circle_user_ids = current_user.get_shared_circle_user_ids_query()

    # Build base query for items in this category from shared circle users
    items_query = Item.query.filter(
        Item.category_id == category_id,  # Filter by the specific category
        Item.owner_id.in_(shared_circle_user_ids)  # Filter by circle membership
    )
    
    # Apply item_type filter
    if item_type == 'loans':
        items_query = items_query.filter(Item.is_giveaway == False)
    elif item_type == 'giveaways':
        items_query = items_query.filter(
            Item.is_giveaway == True,
            or_(Item.claim_status == 'unclaimed', Item.claim_status.is_(None))
        )
    # 'both' - no additional filtering needed
    
    # Perform a paginated query to retrieve items
    items_pagination = (
        items_query
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
        pagination=items_pagination,
        no_circles=False,
        item_type=item_type
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
        
        # Handle web links - delete all existing and recreate
        UserWebLink.query.filter_by(user_id=current_user.id).delete()
        
        # Process each link field
        for i in range(1, 6):
            platform = getattr(form, f'link_{i}_platform').data
            custom_name = getattr(form, f'link_{i}_custom_name').data
            url = getattr(form, f'link_{i}_url').data
            
            # Only create link if we have both platform and URL
            if platform and url and url.strip():
                web_link = UserWebLink(
                    user_id=current_user.id,
                    platform_type=platform,
                    platform_name=custom_name.strip() if custom_name else None,
                    url=url.strip(),
                    display_order=i
                )
                db.session.add(web_link)
        
        db.session.commit()
        flash('Your profile has been updated.', 'success')
        return redirect(url_for('main.profile'))
    elif request.method == 'GET':
        form.about_me.data = current_user.about_me
        
        # Populate web links in form
        existing_links = UserWebLink.query.filter_by(user_id=current_user.id).order_by(UserWebLink.display_order).all()
        for link in existing_links:
            if 1 <= link.display_order <= 5:
                platform_field = getattr(form, f'link_{link.display_order}_platform')
                custom_name_field = getattr(form, f'link_{link.display_order}_custom_name')
                url_field = getattr(form, f'link_{link.display_order}_url')
                
                platform_field.data = link.platform_type
                custom_name_field.data = link.platform_name or ''
                url_field.data = link.url
 
    # Pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = 12  # Items per page for logged-in users (same as index page)
    
    # Fetch user's active giveaways (unclaimed or pending_pickup)
    active_giveaways = Item.query.filter_by(owner_id=current_user.id, is_giveaway=True).filter(
        or_(Item.claim_status == 'unclaimed', Item.claim_status == 'pending_pickup', Item.claim_status.is_(None))
    ).order_by(Item.created_at.desc()).all()
    
    # Fetch user's past giveaways (claimed within last 90 days)
    ninety_days_ago = datetime.now(UTC) - timedelta(days=90)
    past_giveaways = Item.query.filter_by(owner_id=current_user.id, is_giveaway=True).filter(
        Item.claim_status == 'claimed',
        Item.claimed_at >= ninety_days_ago
    ).order_by(Item.claimed_at.desc()).all()
    
    # Fetch user's regular items with pagination (newest first)
    items_pagination = Item.query.filter_by(owner_id=current_user.id, is_giveaway=False).order_by(Item.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    user_items = items_pagination.items
    
    # Create a DeleteItemForm for each item (exclude claimed giveaways since they can't be deleted)
    delete_forms = {item.id: DeleteItemForm() for item in active_giveaways + user_items}
    
    borrowing = current_user.get_active_loans_as_borrower()
    lending = current_user.get_active_loans_as_owner()
    
    return render_template('main/profile.html', 
                         form=form, 
                         user=current_user, 
                         items=user_items,
                         active_giveaways=active_giveaways,
                         past_giveaways=past_giveaways,
                         delete_forms=delete_forms,
                         borrowing=borrowing,
                         lending=lending,
                         pagination=items_pagination)

@main_bp.route('/update-location', methods=['GET', 'POST'])
@login_required
def update_location():
    """Allow users to update their location coordinates"""
    from app.utils.geocoding import geocode_address, build_address_string, GeocodingError
    
    # Check if user can update location (daily limit)
    if not current_user.can_update_location():
        flash('You can only update your location once per day. Please try again tomorrow.', 'warning')
        return redirect(url_for('main.profile'))
    
    form = UpdateLocationForm()
    
    if form.validate_on_submit():
        # Handle location based on input method
        if form.location_method.data == 'remove':
            # Remove location (don't update geocoded_at so user can re-add location immediately)
            current_user.latitude = None
            current_user.longitude = None
            db.session.commit()
            flash('Your location has been removed successfully.', 'success')
            return redirect(url_for('main.profile'))
        elif form.location_method.data == 'coordinates':
            # Direct coordinate input
            current_user.latitude = form.latitude.data
            current_user.longitude = form.longitude.data
            current_user.geocoded_at = datetime.now(UTC)
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
                    current_user.geocoded_at = datetime.now(UTC)
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
@login_required
def user_profile(user_id):
    # Privacy: avoid leaking whether a user exists to people who can't view them.
    # We only return a 404 after confirming the viewer is allowed (admin/self/shared-circle).
    if current_user.is_admin:
        user = db.get_or_404(User, user_id)
    elif current_user.id == user_id:
        user = db.get_or_404(User, user_id)
    else:
        # Viewer is neither admin nor viewing self.
        # If viewer shares a circle with the target user, allow; otherwise, act as if not found.
        target_user = db.session.get(User, user_id)
        if not target_user or not current_user.shares_circle_with(target_user):
            flash('You can only view profiles of users in your circles.', 'warning')
            return redirect(url_for('main.index'))
        user = target_user
    
    # Privacy: Only show items to the profile owner or admins
    # Circle members can view profiles but not browse items
    can_view_items = current_user.is_admin or current_user.id == user.id
    
    items = []
    items_pagination = None
    delete_forms = {}
    
    if can_view_items:
        # Pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = 12  # Items per page (consistent with profile and index pages)
        
        # Fetch user's items with pagination (newest first)
        items_pagination = Item.query.filter_by(owner_id=user.id).order_by(Item.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
        items = items_pagination.items
        
        # Create DeleteItemForm for each item if the current user is the owner
        if current_user.id == user.id:
            delete_forms = {item.id: DeleteItemForm() for item in items}
    
    return render_template(
        'main/user_profile.html',
        user=user,
        items=items,
        pagination=items_pagination,
        delete_forms=delete_forms,
        can_view_items=can_view_items
    )

@main_bp.route('/about')
def about():
    return render_template('main/about.html')


@main_bp.route('/how-it-works')
def how_it_works():
    """Public page that explains how Meutch works for new users."""
    return render_template('main/how_it_works.html')

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
            other_user = db.session.get(User, convo.recipient_id)
        else:
            other_user = db.session.get(User, convo.sender_id)
        
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
            'item': db.session.get(Item, convo.item_id),
            'latest_message': convo,
            'unread_count': unread_count
        })

    return render_template('messaging/messages.html', conversations=conversation_summaries)

@main_bp.route('/message/<uuid:message_id>', methods=['GET', 'POST'])
@login_required
def view_conversation(message_id):
    message = db.get_or_404(Message, message_id)

    if message.sender_id == current_user.id:
        other_user = db.session.get(User, message.recipient_id)
    else:
        other_user = db.session.get(User, message.sender_id)

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

    # Find active loan request for this conversation (pending or approved)
    active_loan = None
    for msg in thread_messages:
        if msg.loan_request and msg.loan_request.status in ['pending', 'approved']:
            active_loan = msg.loan_request
            break

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
            send_message_notification_email(reply)
        except Exception as e:
            current_app.logger.error(f"Failed to send email notification for reply message {reply.id}: {str(e)}")
        
        flash("Your reply has been sent.", "success")
        return redirect(url_for('main.view_conversation', message_id=message_id))

    # Create EmptyForms for loan actions
    loan_action_form = EmptyForm()

    return render_template('messaging/view_conversation.html', 
                         message=message, 
                         thread_messages=thread_messages, 
                         form=form, 
                         active_loan=active_loan,
                         loan_action_form=loan_action_form)


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