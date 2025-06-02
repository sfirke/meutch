from flask import render_template, redirect, request, url_for, flash
from flask_login import login_user, logout_user, current_user, login_required
from app.auth import bp as auth_bp
from app.auth import bp as auth
from app.models import User
from app import db
from app.forms import RegistrationForm, LoginForm
from app.utils.email import send_confirmation_email
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)
logger.debug("Loading app.auth.routes")

@auth.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(
            email=form.email.data,
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            street=form.street.data,
            city=form.city.data,
            state=form.state.data,
            zip_code=form.zip_code.data,
            country=form.country.data
        )
        user.set_password(form.password.data)
        
        db.session.add(user)
        db.session.commit()
        
        if send_confirmation_email(user):
            flash('A confirmation email has been sent to you by email.', 'info')
        else:
            flash('Error sending confirmation email. Please try again.', 'error')
        
        return redirect(url_for('auth.login'))
    
    return render_template('auth/register.html', title='Register', form=form)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):  # Use the model method
            if user.is_confirmed():
                login_user(user)
                return redirect(url_for('main.index'))
            else:
                flash('Please confirm your email address before logging in. Check your email for the confirmation link.', 'warning')
                return render_template('auth/login.html', form=form)
        flash('Invalid email or password')
    return render_template('auth/login.html', form=form)

@auth_bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('main.index'))


@auth_bp.route('/confirm/<token>')
def confirm_email(token):
    """Confirm user email with token"""
    
    user = User.query.filter_by(email_confirmation_token=token).first()
    
    if not user:
        flash('Invalid or expired confirmation link.', 'danger')
        return redirect(url_for('auth.login'))
    
    # Check if token is not too old (24 hours)
    if user.email_confirmation_sent_at:
        token_age = datetime.utcnow() - user.email_confirmation_sent_at
        if token_age > timedelta(hours=24):
            flash('Confirmation link has expired. Please request a new one.', 'danger')
            return redirect(url_for('auth.resend_confirmation'))
    
    if user.confirm_email(token):
        db.session.commit()
        flash('Your email has been confirmed! You can now log in.', 'success')
        return redirect(url_for('auth.login'))
    else:
        flash('Invalid confirmation link.', 'danger')
        return redirect(url_for('auth.login'))

@auth_bp.route('/resend-confirmation', methods=['GET', 'POST'])
def resend_confirmation():
    """Resend confirmation email"""
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        
        if not user:
            flash('No account found with that email address.', 'danger')
            return render_template('auth/resend_confirmation.html')
        
        if user.is_confirmed():
            flash('Your email is already confirmed. You can log in.', 'info')
            return redirect(url_for('auth.login'))
        
        if send_confirmation_email(user):
            db.session.commit()
            flash('A new confirmation email has been sent. Please check your email.', 'success')
        else:
            flash('Error sending confirmation email. Please try again later.', 'danger')
        
        return render_template('auth/resend_confirmation.html')
    
    return render_template('auth/resend_confirmation.html')