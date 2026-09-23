from app.extensions import db
from datetime import datetime
import json
import re

class Company(db.Model):
    __tablename__ = 'companies'
    
    company_id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(150), nullable=False, unique=True, index=True)
    slug = db.Column(db.String(150), unique=True, index=True)
    logo_url = db.Column(db.String(500))
    official_website = db.Column(db.String(500))
    official_careers_url = db.Column(db.String(500))
    industry = db.Column(db.String(100), default='Technology')
    description = db.Column(db.Text)
    headquarters = db.Column(db.String(150))
    locations_json = db.Column(db.Text, default='[]')
    source = db.Column(db.String(100), default='Official Company Source')
    last_verified_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Backward compatible fields for interview preparation and recruitment
    eligibility = db.Column(db.Text)
    salary = db.Column(db.String(100))
    selection_process = db.Column(db.Text)
    
    # Relationships
    questions = db.relationship('Question', backref='company', lazy=True, cascade='all, delete-orphan')
    jobs = db.relationship('Job', backref='company', lazy=True, cascade='all, delete-orphan')
    
    def __init__(self, **kwargs):
        super(Company, self).__init__(**kwargs)
        if not self.slug and self.company_name:
            self.slug = self.generate_slug(self.company_name)
            
    @staticmethod
    def generate_slug(name):
        slug = re.sub(r'[^a-zA-Z0-9\s-]', '', name or '').strip().lower()
        return re.sub(r'[\s_-]+', '-', slug)
        
    @property
    def locations(self):
        try:
            return json.loads(self.locations_json or '[]')
        except Exception:
            return []
            
    @locations.setter
    def locations(self, loc_list):
        self.locations_json = json.dumps(loc_list or [])
        
    @property
    def active_jobs_count(self):
        return sum(1 for j in self.jobs if j.status == 'active')
        
    @property
    def career_areas(self):
        """Dynamically derived career areas strictly from actual active jobs."""
        areas = set()
        for j in self.jobs:
            if j.status == 'active' and j.career_area:
                areas.add(j.career_area.strip())
        return sorted(list(areas))
    
    def __repr__(self):
        return f'<Company {self.company_name}>'
