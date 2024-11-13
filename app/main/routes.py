from uuid import UUID
from flask import render_template, current_app, request, flash, redirect, url_for
from flask_login import login_required, current_user
from sqlalchemy import or_, and_, func
from sqlalchemy.orm import joinedload
from app import db
from app.models import Item, Category, LoanRequest, Tag, User, Message
from app.forms import ListItemForm, EditProfileForm, DeleteItemForm, MessageForm
from app.main import bp as main_bp
from app.utils.storage import upload_file, delete_file
from datetime import datetime


@main_bp.route('/')
def index():
    # Fetch all items (you can modify the query as needed)
    items = Item.query.all()
    
    circles = []
    if current_user.is_authenticated:
        # Fetch the circles the current user is a member of
        circles = current_user.circles
        
    return render_template('main/index.html', items=items, circles=circles)

@main_bp.route('/list-item', methods=['GET', 'POST'])
@login_required
def list_item():
    form = ListItemForm()
    if form.validate_on_submit():
        new_item = Item(
            name=form.name.data.strip(),
            description=form.description.data.strip(),
            owner=current_user,
            category_id=form.category.data
        )
        
        if form.image.data:
            image_url = upload_file(form.image.data)
            if image_url:
                new_item.image_url = image_url

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
        
        flash(f'Item "{new_item.name}" has been listed successfully!', 'success')
        return redirect(url_for('main.index'))
    
    return render_template('main/list_item.html', form=form)

@main_bp.route('/search', methods=['GET', 'POST'])
def search():
    query = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = 10  # Number of items per page

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
    ).distinct().paginate(page=page, per_page=per_page, error_out=False)

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
        
        flash("Your message has been sent.", "success")
        return redirect(url_for('main.item_detail', item_id=item.id))
    
    # Retrieve messages related to this item (optional)
    messages = Message.query.filter_by(item_id=item.id, recipient_id=current_user.id).order_by(Message.timestamp.desc()).all()
    
    return render_template('main/item_detail.html', item=item, form=form, messages=messages)

@main_bp.route('/item/<uuid:item_id>/request', methods=['GET', 'POST'])
@login_required
def request_loan(item_id):
    item = Item.query.get_or_404(item_id)
    if request.method == 'POST':
        loan_request = LoanRequest(
            item=item,
            borrower_id=current_user.id,
            start_date=datetime.strptime(request.form['start_date'], '%Y-%m-%d'),
            end_date=datetime.strptime(request.form['end_date'], '%Y-%m-%d')
        )
        db.session.add(loan_request)
        db.session.commit()
        flash('Loan request submitted')
        return redirect(url_for('main.item_detail', item_id=item_id))
    return render_template('main/request_loan.html', item=item)


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

        if form.delete_image.data:
            if item.image_url:
                current_app.logger.debug("Deleting existing image")
                delete_file(item.image_url)
                item.image_url = None
                current_app.logger.debug("Set item.image_url to None")
                flash('Image has been removed.', 'success')
 
        if form.image.data:
            if item.image_url:
                delete_file(item.image_url)
            image_url = upload_file(form.image.data)
            if image_url:
                item.image_url = image_url

        db.session.commit()
        flash('Item has been updated.', 'success')
        return redirect(url_for('main.profile'))
    
    # Prepopulate tags field
    form.tags.data = ', '.join([tag.name for tag in item.tags])
    
    return render_template('main/edit_item.html', form=form, item=item)


@main_bp.route('/item/<uuid:item_id>/delete', methods=['POST'])
@login_required
def delete_item(item_id):
    form = DeleteItemForm()
    if form.validate_on_submit():
        item = Item.query.get_or_404(item_id)
        if item.owner != current_user:
            flash('You do not have permission to delete this item.', 'danger')
            return redirect(url_for('main.profile'))
        if item.image_url:
            delete_file(item.image_url)
        
        db.session.delete(item)
        db.session.commit()
        flash('Item has been deleted.', 'success')
    else:
        flash('Invalid request.', 'danger')
    return redirect(url_for('main.profile'))

@main_bp.route('/loans/manage')
@login_required
def manage_loans():
    pending_requests = LoanRequest.query.join(Item).filter(
        Item.owner_id == current_user.id,
        LoanRequest.status == 'pending'
    ).all()
    return render_template('main/manage_loans.html', requests=pending_requests)

@main_bp.route('/loan/<uuid:loan_id>/<string:action>')
@login_required
def process_loan(loan_id, action):
    loan = LoanRequest.query.get_or_404(loan_id)
    if loan.item.owner_id != current_user.id:
        flash('Unauthorized')
        return redirect(url_for('main.index'))
    
    if action == 'approve':
        loan.status = 'approved'
        loan.item.available = False
    elif action == 'deny':
        loan.status = 'denied'
    
    db.session.commit()
    flash(f'Loan request {action}d')
    return redirect(url_for('main.manage_loans'))
    
@main_bp.route('/tag/<uuid:tag_id>')
def tag_items(tag_id):
    # Retrieve the tag or return 404 if not found
    tag = Tag.query.get_or_404(tag_id)

    # Get pagination parameters from the request
    page = request.args.get('page', 1, type=int)
    per_page = 10  # Number of items per page

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
            image_url = upload_file(form.profile_image.data)
            if image_url:
                current_user.profile_image_url = image_url
        
        current_user.about_me = form.about_me.data
        db.session.commit()
        flash('Your profile has been updated.', 'success')
        return redirect(url_for('main.profile'))
    elif request.method == 'GET':
        form.about_me.data = current_user.about_me
 
    # Fetch user's items
    user_items = Item.query.filter_by(owner_id=current_user.id).all()
    
    # Create a DeleteItemForm for each item
    delete_forms = {item.id: DeleteItemForm() for item in user_items}
    
    return render_template('main/profile.html', form=form, user=current_user, items=user_items, delete_forms=delete_forms)


@main_bp.route('/user/<uuid:user_id>')
def user_profile(user_id):
    user = User.query.get_or_404(user_id)
    
    # Pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    # Fetch user's items with pagination
    items_pagination = Item.query.filter_by(owner_id=user.id).paginate(page=page, per_page=per_page, error_out=False)
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
    
    # Fetch the entire thread (all messages related to the item between the two users)
    thread_messages = Message.query.filter(
        Message.item_id == message.item_id,
        db.or_(
            db.and_(Message.sender_id == message.sender_id, Message.recipient_id == message.recipient_id),
            db.and_(Message.sender_id == message.recipient_id, Message.recipient_id == message.sender_id)
        )
    ).order_by(Message.timestamp.asc()).all()

    if not message.is_read:
        message.is_read = True
        db.session.commit()

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
        flash("Your reply has been sent.", "success")
        return redirect(url_for('main.view_conversation', message_id=message_id))

    return render_template('messaging/view_conversation.html', message=message, thread_messages=thread_messages, form=form)

@main_bp.context_processor
def inject_unread_messages():
    if current_user.is_authenticated:
        unread_count = Message.query.filter_by(recipient_id=current_user.id, is_read=False).count()
        return dict(unread_messages_count=unread_count)
    return dict(unread_messages_count=0)