from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, TelField, SubmitField, SelectMultipleField
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional, ValidationError
from app.models.user import User
from app.models.skill import Skill

class RegisterForm(FlaskForm):
    """Step 1: Account Creation"""
    name = StringField('Full Name', validators=[DataRequired(), Length(min=2, max=100)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    phone = TelField('Phone Number', validators=[Optional(), Length(min=10, max=15)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField('Confirm Password',
        validators=[DataRequired(), EqualTo('password', message='Passwords must match')])
    user_type = SelectField('I am a', choices=[
        ('student', 'Student'),
        ('fresher', 'Fresher'),
        ('professional', 'Working Professional')
    ], validators=[DataRequired()])
    submit = SubmitField('Create Account')
    
    def validate_email(self, email):
        """Check if email already exists"""
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Email already registered. Please log in.')

class ProfileCompletionForm(FlaskForm):
    """Step 2: Profile Completion (optional at signup, can be skipped)"""
    college_name = StringField('College/University', validators=[Optional(), Length(max=150)])
    degree = StringField('Degree & Branch', validators=[Optional(), Length(max=100)])
    graduation_year = SelectField('Graduation Year', validators=[Optional()], coerce=int)
    domain = SelectField('Preferred Domain', choices=[
        ('', '-- Select Domain --'),
        ('web_dev', 'Web Development'),
        ('data_science', 'Data Science'),
        ('ml', 'Machine Learning'),
        ('cloud', 'Cloud Computing'),
        ('core', 'Core Engineering')
    ], validators=[Optional()])
    career_goal = SelectField('Career Goal', choices=[
        ('', '-- Select Goal --'),
        ('placement_prep', 'Placement Preparation'),
        ('job_switch', 'Job Switch'),
        ('upskilling', 'Upskilling')
    ], validators=[Optional()])
    skills = SelectMultipleField('Skills', validators=[Optional()], coerce=int)
    submit = SubmitField('Complete Profile')
    
    def __init__(self, *args, **kwargs):
        super(ProfileCompletionForm, self).__init__(*args, **kwargs)
        # Populate graduation year dropdown (current year to 10 years ago)
        from datetime import datetime
        current_year = datetime.now().year
        self.graduation_year.choices = [
            (year, str(year)) for year in range(current_year + 5, current_year - 10, -1)
        ]
        
        # Populate skills from database
        skills = Skill.query.all()
        self.skills.choices = [(skill.skill_id, skill.skill_name) for skill in skills]

class LoginForm(FlaskForm):
    """Login Form"""
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Log In')
