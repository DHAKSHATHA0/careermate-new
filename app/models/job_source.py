from app.extensions import db
from datetime import datetime

class JobSource(db.Model):
    __tablename__ = 'job_sources'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    source_type = db.Column(db.String(50), nullable=False)  # official_api, ats_api, public_job_board
    base_url = db.Column(db.String(500))
    api_endpoint = db.Column(db.String(500))
    last_synced_at = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), default='active')  # active, paused, degraded
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<JobSource {self.name} ({self.source_type})>'
