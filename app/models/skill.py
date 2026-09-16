from app.extensions import db

class Skill(db.Model):
    __tablename__ = 'skills'
    
    skill_id = db.Column(db.Integer, primary_key=True)
    skill_name = db.Column(db.String(100), unique=True, nullable=False, index=True)
    
    # Relationships
    users = db.relationship('User', secondary='user_skills', backref='skills')
    
    def __repr__(self):
        return f'<Skill {self.skill_name}>'
