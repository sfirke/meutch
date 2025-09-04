from flask_wtf import FlaskForm
from wtforms import BooleanField, StringField, PasswordField, SelectField, SubmitField, TextAreaField, DateField, FloatField, RadioField
from flask_wtf.file import FileField, FileAllowed
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional, ValidationError, NumberRange
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
    
    # Location input method choice
    location_method = RadioField('How would you like to set your location?', 
        choices=[
            ('address', 'Enter an address (we\'ll look up coordinates)'),
            ('coordinates', 'Enter latitude and longitude directly'),
            ('skip', 'Skip for now (you can add this later on your profile)')
        ], 
        default='address',
        validators=[DataRequired()]
    )
    
    # Address fields (used when location_method is 'address')
    street = StringField('Street Address', validators=[
        Optional(),
        Length(max=200, message="Street address must be under 200 characters.")
    ])
    city = StringField('City', validators=[
        Optional(),
        Length(max=100, message="City must be under 100 characters.")
    ])
    state = StringField('State', validators=[
        Optional(),
        Length(max=100, message="State must be under 100 characters.")
    ])
    zip_code = StringField('ZIP Code', validators=[
        Optional(),
        Length(max=20, message="ZIP Code must be under 20 characters.")
    ])
    country = StringField('Country', validators=[
        Optional(),
        Length(max=100, message="Country must be under 100 characters.")
    ], default='USA')
    
    # Coordinate fields (used when location_method is 'coordinates')
    latitude = FloatField('Latitude', validators=[
        Optional(),
        NumberRange(min=-90, max=90, message="Latitude must be between -90 and 90 degrees.")
    ])
    longitude = FloatField('Longitude', validators=[
        Optional(),
        NumberRange(min=-180, max=180, message="Longitude must be between -180 and 180 degrees.")
    ])
    
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
        from app import db  # Import here to avoid circular imports
        user = User.query.filter(db.func.lower(User.email) == db.func.lower(email.data)).first()
        if user:
            raise ValidationError('This email is already registered. Please choose a different one.')
    
    def validate(self, extra_validators=None):
        """Custom validation to ensure required fields are filled based on location method"""
        rv = FlaskForm.validate(self, extra_validators)
        if not rv:
            return False

        if self.location_method.data == 'address':
            # All address fields are required when using address method
            required_fields = [self.street, self.city, self.state, self.zip_code, self.country]
            for field in required_fields:
                if not field.data or not field.data.strip():
                    field.errors.append(f'{field.label.text} is required when entering an address.')
                    rv = False
        elif self.location_method.data == 'coordinates':
            # Both coordinates are required when using coordinate method
            if self.latitude.data is None:
                self.latitude.errors.append('Latitude is required when entering coordinates directly.')
                rv = False
            if self.longitude.data is None:
                self.longitude.errors.append('Longitude is required when entering coordinates directly.')
                rv = False
        # If location_method is 'skip', no validation is needed for location fields

        return rv

class UpdateLocationForm(FlaskForm):
    # Location input method choice
    location_method = RadioField('How would you like to set your location?', 
        choices=[
            ('address', 'Enter an address (we\'ll look up coordinates)'),
            ('coordinates', 'Enter latitude and longitude directly')
        ], 
        default='address',
        validators=[DataRequired()]
    )
    
    # Address fields (used when location_method is 'address')
    street = StringField('Street Address', validators=[
        Optional(),
        Length(max=200, message="Street address must be under 200 characters.")
    ])
    city = StringField('City', validators=[
        Optional(),
        Length(max=100, message="City must be under 100 characters.")
    ])
    state = StringField('State', validators=[
        Optional(),
        Length(max=100, message="State must be under 100 characters.")
    ])
    zip_code = StringField('ZIP Code', validators=[
        Optional(),
        Length(max=20, message="ZIP Code must be under 20 characters.")
    ])
    country = StringField('Country', validators=[
        Optional(),
        Length(max=100, message="Country must be under 100 characters.")
    ], default='USA')
    
    # Coordinate fields (used when location_method is 'coordinates')
    latitude = FloatField('Latitude', validators=[
        Optional(),
        NumberRange(min=-90, max=90, message="Latitude must be between -90 and 90 degrees.")
    ])
    longitude = FloatField('Longitude', validators=[
        Optional(),
        NumberRange(min=-180, max=180, message="Longitude must be between -180 and 180 degrees.")
    ])
    
    submit = SubmitField('Update Location')
    
    def validate(self, extra_validators=None):
        """Custom validation to ensure required fields are filled based on location method"""
        rv = FlaskForm.validate(self, extra_validators)
        if not rv:
            return False

        if self.location_method.data == 'address':
            # All address fields are required when using address method
            required_fields = [self.street, self.city, self.state, self.zip_code, self.country]
            for field in required_fields:
                if not field.data or not field.data.strip():
                    field.errors.append(f'{field.label.text} is required when entering an address.')
                    rv = False
        elif self.location_method.data == 'coordinates':
            # Both coordinates are required when using coordinate method
            if self.latitude.data is None:
                self.latitude.errors.append('Latitude is required when entering coordinates directly.')
                rv = False
            if self.longitude.data is None:
                self.longitude.errors.append('Longitude is required when entering coordinates directly.')
                rv = False

        return rv

class CircleCreateForm(FlaskForm):
        name = StringField('Circle Name', validators=[
            DataRequired(message="Circle name is required."),
            Length(max=100, message="Circle name must be under 100 characters.")
        ])
        description = TextAreaField('Description', validators=[
            Length(max=500, message="Description must be under 500 characters.")
        ])
        visibility = SelectField('Circle Visibility', 
            choices=[
                ('public', 'Public - Anyone can find and join'),
                ('private', 'Private - Anyone can find, requires approval to join'),
                ('unlisted', 'Unlisted - Can only be found by UUID, requires approval to join')
            ],
            default='public',
            validators=[DataRequired()]
        )
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

class CircleUuidSearchForm(FlaskForm):
    circle_uuid = StringField('Circle UUID', validators=[
        DataRequired(message="Please enter a circle UUID."),
        Length(min=36, max=36, message="UUID must be exactly 36 characters.")
    ])
    submit = SubmitField('Find Circle')

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