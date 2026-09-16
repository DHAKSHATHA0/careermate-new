from app.extensions import db

class Question(db.Model):
    __tablename__ = 'questions'
    
    question_id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.company_id'), nullable=False, index=True)
    question_type = db.Column(db.Enum('aptitude', 'technical', 'logical', 'verbal'), nullable=False)
    difficulty_level = db.Column(db.Enum('easy', 'medium', 'hard'), nullable=False)
    question = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text)
    
    def __repr__(self):
        return f'<Question {self.question_id} - {self.question_type}>'
