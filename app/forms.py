from flask_wtf import FlaskForm
from wtforms import BooleanField, StringField, PasswordField, SelectField, SubmitField, TextAreaField, DateField
from flask_wtf.file import FileField, FileAllowed
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional
from app.models import Category
from datetime import datetime

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

class CircleCreateForm(FlaskForm):
        name = StringField('Circle Name', validators=[
            DataRequired(message="Circle name is required."),
            Length(max=100, message="Circle name must be under 100 characters.")
        ])
        description = TextAreaField('Description', validators=[
            Length(max=500, message="Description must be under 500 characters.")
        ])
        requires_approval = BooleanField('Require Approval to Join')
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
        Optional(),
        FileAllowed(['jpg', 'jpeg', 'png'], 'Images only!')
    ])
    delete_image = BooleanField('Delete current image')
    submit = SubmitField('List Item')
    
    def __init__(self, *args, **kwargs):
        super(ListItemForm, self).__init__(*args, **kwargs)
        self.category.choices = [('', 'Select a category...')] + [(str(c.id), c.name) for c in Category.query.order_by('name')]
    
class EditProfileForm(FlaskForm):
    about_me = TextAreaField('About Me', validators=[Length(max=500)])
    profile_image = FileField('Profile Picture', validators=[
        Optional(),
        FileAllowed(['jpg', 'jpeg', 'png'], 'Images only!')
    ])
    delete_image = BooleanField('Delete current profile picture')
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