from app.extensions import db
from datetime import datetime
import json

class Conversation(db.Model):
    __tablename__ = 'conversations'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False, default='New Conversation')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_message_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    archived = db.Column(db.Boolean, default=False, index=True)
    metadata_json = db.Column(db.Text, default='{}')
    
    # Relationships
    messages = db.relationship(
        'ConversationMessage',
        backref='conversation',
        lazy=True,
        cascade='all, delete-orphan',
        order_by='ConversationMessage.created_at.asc()'
    )
    
    @property
    def meta(self):
        try:
            return json.loads(self.metadata_json or '{}')
        except Exception:
            return {}
            
    @meta.setter
    def meta(self, val):
        self.metadata_json = json.dumps(val or {})
        
    @property
    def last_message_preview(self):
        if self.messages:
            last = self.messages[-1]
            return (last.content[:60] + '...') if len(last.content) > 60 else last.content
        return 'No messages yet'
        
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'last_message_at': self.last_message_at.isoformat() if self.last_message_at else None,
            'last_preview': self.last_message_preview,
            'message_count': len(self.messages),
            'archived': self.archived
        }
        
    def __repr__(self):
        return f'<Conversation id={self.id} user={self.user_id} title="{self.title}">'


class ConversationMessage(db.Model):
    __tablename__ = 'conversation_messages'
    
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversations.id'), nullable=False, index=True)
    role = db.Column(db.String(20), nullable=False)  # 'user', 'assistant', 'system'
    content = db.Column(db.Text, nullable=False)
    message_type = db.Column(db.String(20), default='text')  # 'text', 'image', 'voice', 'mixed'
    image_url = db.Column(db.String(500), nullable=True)
    audio_url = db.Column(db.String(500), nullable=True)
    metadata_json = db.Column(db.Text, default='{}')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    @property
    def meta(self):
        try:
            return json.loads(self.metadata_json or '{}')
        except Exception:
            return {}
            
    @meta.setter
    def meta(self, val):
        self.metadata_json = json.dumps(val or {})
        
    def to_dict(self):
        return {
            'id': self.id,
            'conversation_id': self.conversation_id,
            'role': self.role,
            'content': self.content,
            'message_type': self.message_type,
            'image_url': self.image_url,
            'audio_url': self.audio_url,
            'metadata': self.meta,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
        
    def __repr__(self):
        return f'<ConversationMessage id={self.id} conv={self.conversation_id} role={self.role}>'
