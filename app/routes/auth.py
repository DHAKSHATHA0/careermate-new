from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.extensions import db
from app.models.user import User
from app.models.skill import Skill
from app.forms.auth import RegisterForm, ProfileCompletionForm, LoginForm

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Step 1: Account Creation"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    form = RegisterForm()
    if form.validate_on_submit():
        normalized_email = (form.email.data or '').strip().lower()
        user = User(
            name=form.name.data.strip() if form.name.data else '',
            email=normalized_email,
            phone=form.phone.data.strip() if form.phone.data else None,
            user_type=form.user_type.data
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        
        login_user(user)
        flash('Account created! Complete your profile to get started.', 'success')
        return redirect(url_for('auth.complete_profile'))
    
    return render_template('auth/register.html', form=form)

@auth_bp.route('/complete-profile', methods=['GET', 'POST'])
@login_required
def complete_profile():
    """Step 2: Profile Completion (optional, can skip)"""
    form = ProfileCompletionForm()
    if form.validate_on_submit():
        current_user.college_name = form.college_name.data.strip() if form.college_name.data else None
        current_user.degree = form.degree.data.strip() if form.degree.data else None
        current_user.graduation_start_year = form.graduation_start_year.data if form.graduation_start_year.data else None
        current_user.graduation_year = form.graduation_year.data if form.graduation_year.data else None
        current_user.domain = form.domain.data or None
        current_user.career_goal = form.career_goal.data or None
        
        # Handle skills multi-select
        if form.skills.data:
            # Clear existing skills
            current_user.skills.clear()
            # Add selected skills
            for skill_id in form.skills.data:
                skill = Skill.query.get(skill_id)
                if skill:
                    current_user.skills.append(skill)
        
        db.session.commit()
        
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('main.dashboard'))
    
    return render_template('auth/complete_profile.html', form=form)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Login"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        normalized_email = (form.email.data or '').strip().lower()
        user = User.query.filter_by(email=normalized_email).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('main.dashboard'))
        else:
            flash('Invalid email or password.', 'danger')
    
    return render_template('auth/login.html', form=form)

@auth_bp.route('/logout')
@login_required
def logout():
    """Logout"""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('main.index'))
