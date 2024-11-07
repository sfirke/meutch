from flask import render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, current_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from app.auth import bp as auth_bp
from app.models import User, Item, LoanRequest, Circle
from app import db
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
logger.debug("Loading app.auth.routes")
logger.debug("Loading app.main.routes")

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Capture form data
        email = request.form['email']
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        street = request.form['street']
        city = request.form['city']
        state = request.form['state']
        zip_code = request.form['zip_code']
        country = request.form.get('country', 'USA')  # Default to 'USA'
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        # Validate password confirmation
        if password != confirm_password:
            flash("Passwords do not match.")
            return render_template('auth/register.html')

        # Check if the email already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash("Email already registered.")
            return render_template('auth/register.html')

        # Create new user
        user = User(
            email=email,
            first_name=first_name,
            last_name=last_name,
            street=street,
            city=city,
            state=state,
            zip_code=zip_code,
            country=country
        )
        user.password_hash = generate_password_hash(password)
        db.session.add(user)
        db.session.commit()
        logger.debug(f'User registered: {user.email}')
        flash("Registration successful. Please log in.")
        return redirect(url_for('auth.login'))
    return render_template('auth/register.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form['email']).first()
        if user and check_password_hash(user.password_hash, request.form['password']):
            login_user(user)
            logger.debug(f'User logged in: {user.email}')
            return redirect(url_for('main.index'))
        flash('Invalid email or password')
    return render_template('auth/login.html')

@auth_bp.route('/logout')
def logout():
    logout_user()
    logger.debug('User logged out')
    return redirect(url_for('main.index'))
