from app.extensions import db
from datetime import datetime

class ChatHistory(db.Model):
    __tablename__ = 'chat_history'
    
    chat_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    message = db.Column(db.Text, nullable=False)
    response = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<ChatHistory {self.chat_id} - User {self.user_id}>'
