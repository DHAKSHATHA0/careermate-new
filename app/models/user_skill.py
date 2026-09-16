from app.extensions import db

class UserSkill(db.Model):
    __tablename__ = 'user_skills'
    
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True, index=True)
    skill_id = db.Column(db.Integer, db.ForeignKey('skills.skill_id'), primary_key=True, index=True)
    
    def __repr__(self):
        return f'<UserSkill user_id={self.user_id} skill_id={self.skill_id}>'
