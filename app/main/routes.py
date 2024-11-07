from flask import render_template, current_app as app, request, flash, redirect, url_for
from flask_login import login_required, current_user
from app import db
from app.models import Item
import logging
from app.main import bp as main_bp

logger = logging.getLogger(__name__)
logger.debug("Loading app.main.routes")

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
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        item = Item(
            name=name,
            description=description,
            owner=current_user
        )
        db.session.add(item)
        db.session.commit()
        flash('Item listed successfully!')
        return redirect(url_for('main.index'))
    return render_template('main/list_item.html')


@main_bp.route('/search', methods=['GET', 'POST'])
@login_required
def search():
    if request.method == 'POST':
        query = request.form.get('query', '').strip()
        if not query:
            flash("Please enter a search term.")
            return render_template('main/search.html')
        
        # Perform the search (example: case-insensitive search on item names)
        results = Item.query.filter(Item.name.ilike(f'%{query}%')).all()
        logger.debug(f"Search query: {query}, Results found: {len(results)}")
        return render_template('main/search_results.html', query=query, results=results)
    
    # For GET request, just render the search form
    return render_template('main/search.html')

@main_bp.route('/item/<int:item_id>')
def item_detail(item_id):
    item = Item.query.get_or_404(item_id)
    return render_template('main/item_detail.html', item=item)

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


