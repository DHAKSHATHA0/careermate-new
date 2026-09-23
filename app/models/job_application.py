from app.extensions import db
from datetime import datetime

APPLICATION_STATUSES = [
    'Saved',
    'Applied',
    'Assessment',
    'Shortlisted',
    'Interview',
    'Selected',
    'Rejected',
    'Withdrawn'
]

class JobApplication(db.Model):
    __tablename__ = 'job_applications'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    job_id = db.Column(db.Integer, db.ForeignKey('jobs.id'), nullable=True, index=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.company_id'), nullable=True)
    
    company_name = db.Column(db.String(150), nullable=False)
    job_title = db.Column(db.String(255), nullable=False)
    application_url = db.Column(db.String(1000), nullable=True)
    
    status = db.Column(db.String(30), default='Applied', nullable=False, index=True)
    applied_at = db.Column(db.DateTime, default=datetime.utcnow)
    interview_date = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<JobApplication id={self.id} user={self.user_id} company={self.company_name} status={self.status}>'
