from app.extensions import db
from datetime import datetime

class Resume(db.Model):
    __tablename__ = 'resumes'
    
    resume_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    file_path = db.Column(db.String(255), nullable=False)
    ats_score = db.Column(db.Integer)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Resume {self.resume_id} - User {self.user_id}>'
