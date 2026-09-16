from app.extensions import db
from datetime import datetime

class CourseEnrollment(db.Model):
    __tablename__ = 'course_enrollments'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    skill_name = db.Column(db.String(100), nullable=False)
    course_title = db.Column(db.String(255), nullable=False)
    provider = db.Column(db.String(150))
    url = db.Column(db.String(500))
    status = db.Column(db.String(50), default='enrolled')  # 'enrolled', 'in_progress', 'completed'
    progress = db.Column(db.Integer, default=0)  # 0 to 100
    enrolled_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<CourseEnrollment user_id={self.user_id} course={self.course_title} status={self.status}>'
