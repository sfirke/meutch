from flask import render_template, current_app as app, request, flash, redirect, url_for
from flask_login import login_required, current_user
from sqlalchemy import or_
from sqlalchemy.orm import joinedload
from app import db
from app.models import Item, Category, Tag, LoanRequest
from app.forms import ListItemForm  
from app.main import bp as main_bp


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
        item_name = form.name.data.strip()
        item_description = form.description.data.strip()
        category_id = form.category.data
        tag_input = form.tags.data.strip()
        
        # Retrieve the selected category
        category = Category.query.get_or_404(category_id)
        
        # Create new item
        new_item = Item(
            name=item_name,
            description=item_description,
            owner=current_user,
            category=category
        )
        
        # Process tags
        if tag_input:
            tag_names = [tag.strip().lower() for tag in tag_input.split(',') if tag.strip()]
            for tag_name in tag_names:
                tag = Tag.query.filter_by(name=tag_name).first()
                if not tag:
                    tag = Tag(name=tag_name)
                    db.session.add(tag)
                new_item.tags.append(tag)
        
        db.session.add(new_item)
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

@main_bp.route('/item/<int:item_id>')
def item_detail(item_id):
    item = Item.query.options(
        joinedload(Item.owner),
        joinedload(Item.category),
        joinedload(Item.tags)
    ).filter_by(id=item_id).first_or_404()
    return render_template('item_detail.html', item=item)

@main_bp.route('/item/<int:item_id>/request', methods=['GET', 'POST'])
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

@main_bp.route('/loans/manage')
@login_required
def manage_loans():
    pending_requests = LoanRequest.query.join(Item).filter(
        Item.owner_id == current_user.id,
        LoanRequest.status == 'pending'
    ).all()
    return render_template('main/manage_loans.html', requests=pending_requests)

@main_bp.route('/loan/<int:loan_id>/<string:action>')
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
    
@main_bp.route('/debug')
def debug():
    logger = logging.getLogger(__name__)
    logger.debug('Debug route accessed')
    return 'App is running, blueprints: ' + str(app.blueprints.keys())


