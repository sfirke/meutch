from flask_wtf import FlaskForm
from wtforms import BooleanField, StringField, PasswordField, SelectField, SubmitField, TextAreaField, DateField, FloatField, RadioField, FieldList, FormField
from flask_wtf.file import FileField, FileAllowed
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional, ValidationError, NumberRange, URL
from app.models import Category, User, ItemRequest
from datetime import datetime

def OptionalURL(message=None):
    """
    Custom validator for optional URLs - only validates if field has data
    """
    def _validate(form, field):
        if field.data and field.data.strip():
            # Only validate if there's actual data
            url_validator = URL(message=message or 'Please enter a valid URL (starting with http:// or https://)')
            url_validator(form, field)
    return _validate

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
    remember_device = BooleanField('Remember this device for 30 days')
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
            ('coordinates', 'Enter latitude and longitude directly'),
            ('remove', 'Remove my location')
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
        # Visibility replaces older requires_approval boolean to allow three states
        visibility = SelectField('Circle Visibility',
            choices=[
                ('public', 'Public - Anyone can find and join'),
                ('private', 'Private - Anyone can find it, but requires approval to join.'),
                ('unlisted', 'Unlisted - Cannot be found by search, requires UUID and approval to join.')
            ],
            default='public',
            validators=[DataRequired()]
        )
        image = FileField('Circle Image', validators=[
            OptionalFileAllowed(['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp'], 'Images only! Allowed formats: JPG, PNG, GIF, BMP, WebP')
        ])
        delete_image = BooleanField('Delete current image')
        
        # Location input method choice
        location_method = RadioField('How would you like to set the circle location?', 
            choices=[
                ('address', 'Enter an address (we\'ll look up coordinates)'),
                ('coordinates', 'Enter latitude and longitude directly'),
                ('skip', 'Skip for now (admins can add this later)')
            ], 
            default='skip',
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
        
        submit = SubmitField('Create Circle')
        
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


class CircleSearchForm(FlaskForm):
    search_query = StringField('Search Circles', validators=[
        Optional(),
        Length(max=100, message="Search term must be under 100 characters.")
    ])
    radius = SelectField('Within',
        choices=[
            ('', 'Any distance'),
            ('5', 'Within 5 miles'),
            ('10', 'Within 10 miles'),
            ('25', 'Within 25 miles'),
            ('50', 'Within 50 miles'),
            ('100', 'Within 100 miles')
        ],
        default='',
        validators=[Optional()]
    )
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
    is_giveaway = BooleanField('This is a giveaway (free item)')
    giveaway_visibility = RadioField('Giveaway Visibility',
        choices=[
            ('default', 'Circles only - Only visible to users in my circles'),
            ('public', 'Public - Visible to all users on the platform')
        ],
        default='default',
        validators=[Optional()]
    )
    submit = SubmitField('List Item')
    submit_and_create_another = SubmitField('List Item & Create Another')
    
    def __init__(self, *args, **kwargs):
        super(ListItemForm, self).__init__(*args, **kwargs)
        self.category.choices = [('', 'Select a category...')] + [(str(c.id), c.name) for c in Category.query.order_by('name')]
    
    def validate(self, extra_validators=None):
        """Custom validation to ensure giveaway_visibility is set when is_giveaway is checked"""
        rv = FlaskForm.validate(self, extra_validators)
        if not rv:
            return False
        
        if self.is_giveaway.data and not self.giveaway_visibility.data:
            self.giveaway_visibility.errors.append('Please select a visibility option for this giveaway.')
            rv = False
        
        return rv
    
class EditProfileForm(FlaskForm):
    about_me = TextAreaField('About Me', validators=[Length(max=500)])
    profile_image = FileField('Profile Picture', validators=[
        OptionalFileAllowed(['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp'], 'Images only! Allowed formats: JPG, PNG, GIF, BMP, WebP')
    ])
    delete_image = BooleanField('Delete current profile picture')
    
    # Web Links - 5 sets of fields for dynamic web link management
    link_1_platform = SelectField('Platform 1', choices=[], validators=[Optional()])
    link_1_custom_name = StringField('Custom Name 1', validators=[Optional(), Length(max=50)])
    link_1_url = StringField('URL 1', validators=[OptionalURL()])
    
    link_2_platform = SelectField('Platform 2', choices=[], validators=[Optional()])
    link_2_custom_name = StringField('Custom Name 2', validators=[Optional(), Length(max=50)])
    link_2_url = StringField('URL 2', validators=[OptionalURL()])
    
    link_3_platform = SelectField('Platform 3', choices=[], validators=[Optional()])
    link_3_custom_name = StringField('Custom Name 3', validators=[Optional(), Length(max=50)])
    link_3_url = StringField('URL 3', validators=[OptionalURL()])
    
    link_4_platform = SelectField('Platform 4', choices=[], validators=[Optional()])
    link_4_custom_name = StringField('Custom Name 4', validators=[Optional(), Length(max=50)])
    link_4_url = StringField('URL 4', validators=[OptionalURL()])
    
    link_5_platform = SelectField('Platform 5', choices=[], validators=[Optional()])
    link_5_custom_name = StringField('Custom Name 5', validators=[Optional(), Length(max=50)])
    link_5_url = StringField('URL 5', validators=[OptionalURL()])
    
    submit = SubmitField('Update Profile')
    
    def __init__(self, *args, **kwargs):
        super(EditProfileForm, self).__init__(*args, **kwargs)
        # Import here to avoid circular imports
        from app.models import UserWebLink
        
        # Set platform choices for all link fields
        platform_choices = [('', 'Select a platform...')] + UserWebLink.PLATFORM_CHOICES
        self.link_1_platform.choices = platform_choices
        self.link_2_platform.choices = platform_choices
        self.link_3_platform.choices = platform_choices
        self.link_4_platform.choices = platform_choices
        self.link_5_platform.choices = platform_choices
    
    def validate(self, **kwargs):
        rv = FlaskForm.validate(self, **kwargs)
        if not rv:
            return False
        
        # Custom validation for web links
        for i in range(1, 6):
            platform_field = getattr(self, f'link_{i}_platform')
            custom_name_field = getattr(self, f'link_{i}_custom_name')
            url_field = getattr(self, f'link_{i}_url')
            
            # If URL is provided, platform must be selected
            if url_field.data and url_field.data.strip() and not platform_field.data:
                platform_field.errors.append('Please select a platform when providing a URL.')
                rv = False
            
            # If platform is "other", both custom name and URL are required
            if platform_field.data == 'other':
                if not custom_name_field.data or not custom_name_field.data.strip():
                    custom_name_field.errors.append('Please provide a custom name when selecting "Other".')
                    rv = False
                if not url_field.data or not url_field.data.strip():
                    url_field.errors.append('Please provide a URL when selecting "Other".')
                    rv = False
        
        return rv

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

class ExtendLoanForm(FlaskForm):
    new_end_date = DateField('New End Date', 
        validators=[DataRequired(message="Please select a new end date.")])
    message = TextAreaField('Include a message to borrower (optional)', 
        validators=[
            Optional(),
            Length(max=1000, message="Message must be under 1000 characters.")
        ])
    submit = SubmitField('Extend Loan')

    def __init__(self, current_end_date=None, *args, **kwargs):
        super(ExtendLoanForm, self).__init__(*args, **kwargs)
        self.current_end_date = current_end_date

    def validate_new_end_date(self, field):
        if field.data < datetime.now().date():
            raise ValidationError('New end date cannot be in the past.')

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

class VacationModeForm(FlaskForm):
    vacation_mode = BooleanField('Vacation Mode')
    submit = SubmitField('Update')

class ExpressInterestForm(FlaskForm):
    message = TextAreaField(
        'Optional message to the owner',
        validators=[Optional(), Length(max=500, message="Message must be under 500 characters.")]
    )
    submit = SubmitField('Submit Interest')

class WithdrawInterestForm(FlaskForm):
    submit = SubmitField('Withdraw Interest')

class SelectRecipientForm(FlaskForm):
    selection_method = RadioField(
        'Selection Method',
        choices=[
            ('first', 'First Requester'),
            ('random', 'Random Selection'),
            ('manual', 'Manual Selection')
        ],
        validators=[DataRequired(message="Please select a method.")]
    )
    user_id = StringField('Selected User ID')  # Hidden field for manual selection
    submit = SubmitField('Select Recipient')


class ChangeRecipientForm(FlaskForm):
    """Form for changing the recipient of a giveaway that's pending pickup."""
    selection_method = RadioField(
        'Selection Method',
        choices=[
            ('next', 'Next in Line'),
            ('random', 'Random from Remaining'),
            ('manual', 'Manual Selection')
        ],
        validators=[DataRequired(message="Please select a method.")]
    )
    user_id = StringField('Selected User ID')  # Hidden field for manual selection
    submit = SubmitField('Change Recipient')


class ReleaseToAllForm(FlaskForm):
    """Form for releasing a giveaway back to unclaimed status."""
    submit = SubmitField('Release to Everyone')


class ConfirmHandoffForm(FlaskForm):
    """Form for confirming the handoff of a giveaway."""
    submit = SubmitField('Confirm Handoff Complete')


class ResendConfirmationForm(FlaskForm):
    email = StringField('Email Address', validators=[
        DataRequired(message="Email is required."),
        Email(message="Invalid email format."),
        Length(max=120, message="Email must be under 120 characters.")
    ])
    submit = SubmitField('Send Confirmation Email')


class ItemRequestForm(FlaskForm):
    """Form for creating or editing a community item request."""
    title = StringField('What are you looking for?', validators=[
        DataRequired(message="A short title is required."),
        Length(max=100, message="Title must be under 100 characters.")
    ])
    description = TextAreaField('More details (optional)', validators=[
        Optional(),
        Length(max=1000, message="Description must be under 1000 characters.")
    ])
    expires_at = DateField('Request expires on', validators=[
        DataRequired(message="Please select an expiration date.")
    ])
    seeking = SelectField('What are you looking for?',
        choices=ItemRequest.SEEKING_CHOICES,
        default='either',
        validators=[DataRequired()]
    )
    visibility = SelectField('Who can see this?',
        choices=ItemRequest.VISIBILITY_CHOICES,
        default='circles',
        validators=[DataRequired()]
    )
    submit = SubmitField('Post Request')

    def validate_expires_at(self, field):
        """Expiration must be between today and 6 months from today."""
        from dateutil.relativedelta import relativedelta
        today = datetime.now().date()
        max_date = today + relativedelta(months=6)
        if field.data < today:
            raise ValidationError('Expiration date cannot be in the past.')
        if field.data > max_date:
            raise ValidationError('Expiration date cannot be more than 6 months from today.')