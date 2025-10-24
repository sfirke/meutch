from flask import render_template, redirect, request, url_for, flash
from flask_login import login_user, logout_user, current_user, login_required
from app.auth import bp as auth_bp
from app.auth import bp as auth
from app.models import User
from app import db
from app.forms import RegistrationForm, LoginForm, ForgotPasswordForm, ResetPasswordForm
from app.utils.email import send_confirmation_email, send_password_reset_email
from app.utils.geocoding import geocode_address, build_address_string, GeocodingError
from datetime import datetime, timedelta, UTC
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
            email=form.email.data.lower(),
            first_name=form.first_name.data,
            last_name=form.last_name.data
        )
        user.set_password(form.password.data)
        
        # Handle location based on input method
        if form.location_method.data == 'coordinates':
            # Direct coordinate input
            user.latitude = form.latitude.data
            user.longitude = form.longitude.data
            user.geocoded_at = datetime.now(UTC)
            user.geocoding_failed = False
            logger.info(f"User {user.email} provided coordinates directly: ({user.latitude}, {user.longitude})")
        elif form.location_method.data == 'address':
            # Address geocoding
            address = build_address_string(
                form.street.data, form.city.data, form.state.data, 
                form.zip_code.data, form.country.data
            )
            
            try:
                coordinates = geocode_address(address)
                if coordinates:
                    user.latitude, user.longitude = coordinates
                    user.geocoded_at = datetime.now(UTC)
                    user.geocoding_failed = False
                    logger.info(f"Successfully geocoded address for user {user.email}")
                else:
                    user.geocoding_failed = True
                    logger.warning(f"Failed to geocode address for user {user.email}: {address}")
            except GeocodingError as e:
                user.geocoding_failed = True
                logger.error(f"Geocoding error for user {user.email}: {e}")
            except Exception as e:
                user.geocoding_failed = True
                logger.error(f"Unexpected error during geocoding for user {user.email}: {e}")
        # If location_method is 'skip', don't set any location data
        
        db.session.add(user)
        db.session.commit()
        
        # Provide appropriate feedback based on location choice
        if form.location_method.data == 'skip':
            flash('Your account has been created! You can add your location later on your profile page '
                  'to see distances to items and help others find items near you.', 'info')
        elif user.geocoding_failed:
            flash('Your account has been created, but we couldn\'t determine your location from the address provided. '
                  'You can try the option to enter coordinates directly, or update your location later on your profile page to see distances to items.', 'warning')
        
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
        # Use case-insensitive email lookup
        user = User.query.filter(db.func.lower(User.email) == db.func.lower(form.email.data)).first()
        if user and user.check_password(form.password.data):  # Use the model method
            if user.is_confirmed():
                login_user(user)
                return redirect(url_for('main.index'))
            else:
                flash('Please confirm your email address before logging in. Check your email for the confirmation link.', 'warning')
                return render_template('auth/login.html', form=form)
        flash('Invalid email or password', 'danger')
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
        token_age = datetime.now(UTC) - user.email_confirmation_sent_at
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
        user = User.query.filter(db.func.lower(User.email) == db.func.lower(email)).first()
        
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

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Request password reset"""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        user = User.query.filter(db.func.lower(User.email) == db.func.lower(form.email.data)).first()
        
        if user:
            if send_password_reset_email(user):
                flash('Password reset instructions have been sent to your email.', 'info')
            else:
                flash('Error sending password reset email. Please try again later.', 'error')
        else:
            flash('If an account with that email exists, password reset instructions have been sent.', 'info')
        
        return redirect(url_for('auth.login'))
    
    return render_template('auth/forgot_password.html', form=form)

@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Reset password with token"""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    user = User.query.filter_by(password_reset_token=token).first()
    
    if not user:
        flash('Invalid or expired reset link.', 'danger')
        return redirect(url_for('auth.forgot_password'))
    
    # Check if token is not too old (1 hour)
    if user.password_reset_sent_at:
        token_age = datetime.now(UTC) - user.password_reset_sent_at
        if token_age > timedelta(hours=1):
            flash('Reset link has expired. Please request a new one.', 'danger')
            return redirect(url_for('auth.forgot_password'))
    
    form = ResetPasswordForm()
    if form.validate_on_submit():
        if user.reset_password(token, form.password.data):
            db.session.commit()
            flash('Your password has been reset successfully. You can now log in.', 'success')
            return redirect(url_for('auth.login'))
        else:
            flash('Invalid reset token. Please request a new password reset.', 'danger')
            return redirect(url_for('auth.forgot_password'))
    
    return render_template('auth/reset_password.html', form=form)