from app.extensions import db
from datetime import datetime
import json

class JobAnalysis(db.Model):
    __tablename__ = 'job_analyses'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    job_id = db.Column(db.Integer, db.ForeignKey('jobs.id'), nullable=True, index=True)
    resume_id = db.Column(db.Integer, db.ForeignKey('resumes.resume_id'), nullable=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.company_id'), nullable=True)
    company_name = db.Column(db.String(150), nullable=False)
    target_role = db.Column(db.String(150), nullable=False)
    score = db.Column(db.Integer, default=0)
    matching_skills_json = db.Column(db.Text, default='[]')
    missing_skills_json = db.Column(db.Text, default='[]')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    company = db.relationship('Company', backref='analyses')
    resume = db.relationship('Resume', backref='job_analyses')
    
    @property
    def matching_skills(self):
        try:
            return json.loads(self.matching_skills_json or '[]')
        except Exception:
            return []
            
    @matching_skills.setter
    def matching_skills(self, skills_list):
        self.matching_skills_json = json.dumps(skills_list or [])

    @property
    def missing_skills(self):
        try:
            return json.loads(self.missing_skills_json or '[]')
        except Exception:
            return []
            
    @missing_skills.setter
    def missing_skills(self, skills_list):
        self.missing_skills_json = json.dumps(skills_list or [])

    def __repr__(self):
        return f'<JobAnalysis id={self.id} user={self.user_id} target="{self.company_name} - {self.target_role}">'
