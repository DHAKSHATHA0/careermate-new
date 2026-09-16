from app.extensions import db

class Company(db.Model):
    __tablename__ = 'companies'
    
    company_id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(150), nullable=False, unique=True, index=True)
    description = db.Column(db.Text)
    eligibility = db.Column(db.Text)
    salary = db.Column(db.String(100))
    selection_process = db.Column(db.Text)
    
    # Relationships
    questions = db.relationship('Question', backref='company', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Company {self.company_name}>'
