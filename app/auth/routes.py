from flask import render_template, redirect, request, url_for, flash
from flask_login import login_user, logout_user, current_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from app.auth import bp as auth_bp
from app.models import User, LoanRequest, Item
from app import db
from app.forms import RegistrationForm
import logging

logger = logging.getLogger(__name__)
logger.debug("Loading app.auth.routes")

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        email = form.email.data
        first_name = form.first_name.data
        last_name = form.last_name.data
        street = form.street.data
        city = form.city.data
        state = form.state.data
        zip_code = form.zip_code.data
        country = form.country.data or 'USA'
        password = form.password.data

        # Check if the email already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash("Email already registered.")
            return render_template('auth/register.html', form=form)

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
    return render_template('auth/register.html', form=form)

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
