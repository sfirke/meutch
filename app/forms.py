from flask_wtf import FlaskForm
from wtforms import BooleanField, StringField, PasswordField, SelectField, SubmitField, TextAreaField, DateField
from flask_wtf.file import FileField, FileAllowed
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional, ValidationError
from app.models import Category, User
from datetime import datetime

def OptionalFileAllowed(upload_set, message=None):
    """
    Custom validator that allows empty files and validates non-empty files with FileAllowed
    """
    def _validate(form, field):
        if not field.data:
            return
        
        # Check if file has a filename and content
        if hasattr(field.data, 'filename') and field.data.filename and field.data.filename.strip():
            # Only apply FileAllowed validation if there's actually a file
            file_allowed = FileAllowed(upload_set, message)
            file_allowed(form, field)
    
    return _validate

class EmptyForm(FlaskForm):
    pass

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[
        DataRequired(message="Email is required."),
        Email(message="Invalid email format."),
        Length(max=120, message="Email must be under 120 characters.")
    ])
    password = PasswordField('Password', validators=[
        DataRequired(message="Password is required."),
        Length(min=6, message="Password must be at least 6 characters long.")
    ])
    submit = SubmitField('Log In')

class RegistrationForm(FlaskForm):
    email = StringField('Email', validators=[
        DataRequired(message="Email is required."),
        Email(message="Invalid email format."),
        Length(max=120, message="Email must be under 120 characters.")
    ])
    first_name = StringField('First Name', validators=[
        DataRequired(message="First name is required."),
        Length(max=50, message="First name must be under 50 characters.")
    ])
    last_name = StringField('Last Name', validators=[
        DataRequired(message="Last name is required."),
        Length(max=50, message="Last name must be under 50 characters.")
    ])
    street = StringField('Street Address', validators=[
        DataRequired(message="Street address is required."),
        Length(max=200, message="Street address must be under 200 characters.")
    ])
    city = StringField('City', validators=[
        DataRequired(message="City is required."),
        Length(max=100, message="City must be under 100 characters.")
    ])
    state = StringField('State', validators=[
        DataRequired(message="State is required."),
        Length(max=100, message="State must be under 100 characters.")
    ])
    zip_code = StringField('ZIP Code', validators=[
        DataRequired(message="ZIP Code is required."),
        Length(max=20, message="ZIP Code must be under 20 characters.")
    ])
    country = StringField('Country', validators=[
        DataRequired(message="Country is required."),
        Length(max=100, message="Country must be under 100 characters.")
    ], default='USA')
    password = PasswordField('Password', validators=[
        DataRequired(message="Password is required."),
        Length(min=6, message="Password must be at least 6 characters long.")
    ])
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(message="Please confirm your password."),
        EqualTo('password', message="Passwords must match.")
    ])
    submit = SubmitField('Register')

    def validate_email(self, email):
        """Check if email is already registered"""
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('This email is already registered. Please choose a different one.')

class UpdateAddressForm(FlaskForm):
    street = StringField('Street Address', validators=[
        DataRequired(message="Street address is required."),
        Length(max=200, message="Street address must be under 200 characters.")
    ])
    city = StringField('City', validators=[
        DataRequired(message="City is required."),
        Length(max=100, message="City must be under 100 characters.")
    ])
    state = StringField('State', validators=[
        DataRequired(message="State is required."),
        Length(max=100, message="State must be under 100 characters.")
    ])
    zip_code = StringField('ZIP Code', validators=[
        DataRequired(message="ZIP Code is required."),
        Length(max=20, message="ZIP Code must be under 20 characters.")
    ])
    country = StringField('Country', validators=[
        DataRequired(message="Country is required."),
        Length(max=100, message="Country must be under 100 characters.")
    ], default='USA')
    submit = SubmitField('Update Address')

class CircleCreateForm(FlaskForm):
        name = StringField('Circle Name', validators=[
            DataRequired(message="Circle name is required."),
            Length(max=100, message="Circle name must be under 100 characters.")
        ])
        description = TextAreaField('Description', validators=[
            Length(max=500, message="Description must be under 500 characters.")
        ])
        requires_approval = BooleanField('Require Approval to Join')
        image = FileField('Circle Image', validators=[
            OptionalFileAllowed(['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp'], 'Images only! Allowed formats: JPG, PNG, GIF, BMP, WebP')
        ])
        delete_image = BooleanField('Delete current image')
        submit = SubmitField('Create Circle')

class CircleSearchForm(FlaskForm):
    search_query = StringField('Search Circles', validators=[
        DataRequired(message="Please enter a search term."),
        Length(max=100, message="Search term must be under 100 characters.")
    ])
    submit = SubmitField('Search')

class ListItemForm(FlaskForm):
    name = StringField('Item Name', validators=[DataRequired(), Length(max=100)])
    description = TextAreaField('Description', validators=[Length(max=500)])
    category = SelectField('Category', coerce=str, validators=[DataRequired()])
    tags = StringField('Tags (comma-separated)', validators=[Length(max=200)])
    image = FileField('Image', validators=[
        OptionalFileAllowed(['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp'], 'Images only! Allowed formats: JPG, PNG, GIF, BMP, WebP')
    ])
    delete_image = BooleanField('Delete current image')
    submit = SubmitField('List Item')
    submit_and_create_another = SubmitField('List Item & Create Another')
    
    def __init__(self, *args, **kwargs):
        super(ListItemForm, self).__init__(*args, **kwargs)
        self.category.choices = [('', 'Select a category...')] + [(str(c.id), c.name) for c in Category.query.order_by('name')]
    
class EditProfileForm(FlaskForm):
    about_me = TextAreaField('About Me', validators=[Length(max=500)])
    profile_image = FileField('Profile Picture', validators=[
        OptionalFileAllowed(['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp'], 'Images only! Allowed formats: JPG, PNG, GIF, BMP, WebP')
    ])
    delete_image = BooleanField('Delete current profile picture')
    email_notifications_enabled = BooleanField('Receive email notifications for new messages')
    submit = SubmitField('Update Profile')

class DeleteItemForm(FlaskForm):
    submit = SubmitField('Delete')

class MessageForm(FlaskForm):
    body = TextAreaField('Message', validators=[DataRequired(), Length(min=1, max=1000)])
    submit = SubmitField('Send')

class CircleJoinRequestForm(FlaskForm):
    message = TextAreaField(
        'Message to Circle Admins',
        validators=[Optional(), Length(max=500)]
    )
    submit = SubmitField('Request to Join')

class LoanRequestForm(FlaskForm):
    start_date = DateField('Start Date', 
        validators=[DataRequired(message="Please select a start date.")])
    end_date = DateField('End Date', 
        validators=[DataRequired(message="Please select an end date.")])
    message = TextAreaField('Message to Owner', 
        validators=[
            DataRequired(message="Please include a message with your request."),
            Length(min=10, max=1000, 
                message="Message must be between 10 and 1000 characters.")
        ])
    submit = SubmitField('Submit Request')

    def validate_end_date(self, field):
        if field.data < self.start_date.data:
            raise ValidationError('End date must be after start date.')
        if field.data < datetime.now().date():
            raise ValidationError('End date cannot be in the past.')

    def validate_start_date(self, field):
        if field.data < datetime.now().date():
            raise ValidationError('Start date cannot be in the past.')

class ForgotPasswordForm(FlaskForm):
    email = StringField('Email', validators=[
        DataRequired(message="Email is required."),
        Email(message="Invalid email format."),
        Length(max=120, message="Email must be under 120 characters.")
    ])
    submit = SubmitField('Send Reset Link')

class ResetPasswordForm(FlaskForm):
    password = PasswordField('New Password', validators=[
        DataRequired(message="Password is required."),
        Length(min=6, message="Password must be at least 6 characters long.")
    ])
    confirm_password = PasswordField('Confirm New Password', validators=[
        DataRequired(message="Please confirm your password."),
        EqualTo('password', message="Passwords must match.")
    ])
    submit = SubmitField('Reset Password')

class DeleteAccountForm(FlaskForm):
    confirmation = StringField('Type "DELETE MY ACCOUNT" to confirm', validators=[
        DataRequired(message="Please type the confirmation phrase."),
        Length(max=50, message="Confirmation phrase is too long.")
    ])
    submit = SubmitField('Delete My Account')

    def validate_confirmation(self, field):
        if field.data != "DELETE MY ACCOUNT":
            raise ValidationError('You must type "DELETE MY ACCOUNT" exactly to confirm deletion.')