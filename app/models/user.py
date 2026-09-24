from app.extensions import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from sqlalchemy.orm import validates

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(15))
    user_type = db.Column(db.Enum('student', 'fresher', 'professional'), nullable=False)
    domain = db.Column(db.String(100))
    college_name = db.Column(db.String(150))
    degree = db.Column(db.String(100))
    graduation_start_year = db.Column(db.Integer)
    graduation_year = db.Column(db.Integer)
    current_company = db.Column(db.String(150))
    career_goal = db.Column(db.Enum('placement_prep', 'job_switch', 'upskilling', ''), nullable=True)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    resumes = db.relationship('Resume', backref='user', lazy=True, cascade='all, delete-orphan')
    chat_history = db.relationship('ChatHistory', backref='user', lazy=True, cascade='all, delete-orphan')
    enrollments = db.relationship('CourseEnrollment', backref='user', lazy=True, cascade='all, delete-orphan')
    job_feedback = db.relationship('JobFeedback', backref='user', lazy=True, cascade='all, delete-orphan')
    job_analyses = db.relationship('JobAnalysis', backref='user', lazy=True, cascade='all, delete-orphan')
    saved_jobs = db.relationship('SavedJob', backref='user', lazy=True, cascade='all, delete-orphan')
    applications = db.relationship('JobApplication', backref='user', lazy=True, cascade='all, delete-orphan')
    conversations = db.relationship('Conversation', backref='user', lazy=True, cascade='all, delete-orphan', order_by='Conversation.last_message_at.desc()')
    
    @validates('email')
    def validate_email(self, key, address):
        """Ensure email is consistently trimmed and lowercased"""
        if address:
            return address.strip().lower()
        return address
    
    def set_password(self, password):
        """Hash and set password"""
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')
    
    def check_password(self, password):
        """Verify password against hash"""
        return check_password_hash(self.password_hash, password)
    
    @property
    def education_period(self):
        """Return formatted education duration string e.g. 2024 - 2028"""
        if self.graduation_start_year and self.graduation_year:
            return f"{self.graduation_start_year} - {self.graduation_year}"
        elif self.graduation_year:
            return f"Class of {self.graduation_year}"
        elif self.graduation_start_year:
            return f"Since {self.graduation_start_year}"
        return "Not specified"
    
    def __repr__(self):
        return f'<User {self.email}>'
