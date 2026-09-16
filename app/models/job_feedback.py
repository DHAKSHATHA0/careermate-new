from app.extensions import db
from datetime import datetime

class JobFeedback(db.Model):
    __tablename__ = 'job_feedback'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.company_id'), nullable=False, index=True)
    reason = db.Column(db.String(100), default='Not interested')  # 'Wrong role', 'Wrong location', 'Skills don\'t match', 'Not interested', 'Other'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    company = db.relationship('Company', backref='user_feedback')
    
    def __repr__(self):
        return f'<JobFeedback user={self.user_id} company={self.company_id} reason={self.reason}>'
