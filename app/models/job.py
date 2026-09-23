from app.extensions import db
from datetime import datetime
import json
import re

class Job(db.Model):
    __tablename__ = 'jobs'
    
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.company_id'), nullable=False, index=True)
    external_job_id = db.Column(db.String(150), index=True)
    title = db.Column(db.String(255), nullable=False, index=True)
    slug = db.Column(db.String(255), index=True)
    career_area = db.Column(db.String(100), index=True)  # e.g., 'Software Engineering', 'Data Science', 'Cloud'
    
    description = db.Column(db.Text)
    responsibilities = db.Column(db.Text)
    required_qualifications = db.Column(db.Text)
    preferred_qualifications = db.Column(db.Text)
    skills_json = db.Column(db.Text, default='[]')
    
    location = db.Column(db.String(150), default='Remote')
    country = db.Column(db.String(100), default='Global')
    employment_type = db.Column(db.String(50), default='Full-time')  # Full-time, Part-time, Contract, Internship
    work_mode = db.Column(db.String(50), default='Remote')  # Remote, Hybrid, On-site
    
    experience_min = db.Column(db.Integer, nullable=True)
    experience_max = db.Column(db.Integer, nullable=True)
    
    salary_min = db.Column(db.Float, nullable=True)
    salary_max = db.Column(db.Float, nullable=True)
    currency = db.Column(db.String(10), default='USD')
    
    posted_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    application_deadline = db.Column(db.DateTime, nullable=True)
    application_url = db.Column(db.String(1000), nullable=False)
    source_url = db.Column(db.String(1000))
    source_platform = db.Column(db.String(100), default='Official Company Careers')
    
    status = db.Column(db.String(30), default='active', index=True)  # 'active', 'closed', 'expired'
    last_verified_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    saved_by = db.relationship('SavedJob', backref='job', lazy=True, cascade='all, delete-orphan')
    applications = db.relationship('JobApplication', backref='job', lazy=True, cascade='all, delete-orphan')
    analyses = db.relationship('JobAnalysis', backref='job_record', lazy=True)
    
    def __init__(self, **kwargs):
        super(Job, self).__init__(**kwargs)
        if not self.slug and self.title:
            self.slug = self.generate_slug(self.title)
            
    @staticmethod
    def generate_slug(title):
        slug = re.sub(r'[^a-zA-Z0-9\s-]', '', title or '').strip().lower()
        return re.sub(r'[\s_-]+', '-', slug)
        
    @property
    def skills(self):
        try:
            return json.loads(self.skills_json or '[]')
        except Exception:
            return []
            
    @skills.setter
    def skills(self, skills_list):
        self.skills_json = json.dumps(skills_list or [])
        
    @property
    def salary_display(self):
        if self.salary_min and self.salary_max:
            return f"{self.currency} {int(self.salary_min):,} - {int(self.salary_max):,}"
        elif self.salary_min:
            return f"From {self.currency} {int(self.salary_min):,}"
        elif self.salary_max:
            return f"Up to {self.currency} {int(self.salary_max):,}"
        return None
        
    @property
    def experience_display(self):
        if self.experience_min is not None and self.experience_max is not None:
            if self.experience_min == self.experience_max:
                return f"{self.experience_min} yrs"
            return f"{self.experience_min}-{self.experience_max} yrs"
        elif self.experience_min is not None:
            return f"{self.experience_min}+ yrs"
        elif self.experience_max is not None:
            return f"Up to {self.experience_max} yrs"
        return "Not specified"
        
    @property
    def freshness_label(self):
        if not self.last_verified_at:
            return "Recently verified"
        diff = datetime.utcnow() - self.last_verified_at
        if diff.days > 0:
            return f"Verified {diff.days}d ago"
        hours = int(diff.total_seconds() // 3600)
        if hours > 0:
            return f"Verified {hours}h ago"
        mins = int(diff.total_seconds() // 60)
        return f"Verified {max(mins, 1)}m ago"
        
    def __repr__(self):
        return f'<Job {self.title} @ {self.company.company_name if self.company else self.company_id}>'
