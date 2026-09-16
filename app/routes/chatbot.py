from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from app.extensions import db
from app.models.chat_history import ChatHistory
from app.utils.chatbot import ChatbotRAG

chatbot_bp = Blueprint('chatbot', __name__, url_prefix='/chatbot')
rag = ChatbotRAG()

@chatbot_bp.route('/chat')
@login_required
def chat():
    """Chatbot page"""
    return render_template('chatbot.html')

@chatbot_bp.route('/api/message', methods=['POST'])
@login_required
def send_message():
    """API endpoint to send message and get response"""
    data = request.get_json()
    user_message = data.get('message', '').strip()
    
    if not user_message:
        return jsonify({'error': 'Message cannot be empty'}), 400
    
    # Get knowledge base context
    knowledge_base = rag.get_knowledge_base()
    kb_context = rag.format_knowledge_base(knowledge_base)
    
    # Generate response
    response_data = rag.generate_response(user_message, kb_context)
    
    # Save to chat history
    chat_entry = ChatHistory(
        user_id=current_user.id,
        message=user_message,
        response=response_data['response']
    )
    db.session.add(chat_entry)
    db.session.commit()
    
    return jsonify({
        'message': user_message,
        'response': response_data['response'],
        'sources': response_data['sources']
    })

@chatbot_bp.route('/api/history')
@login_required
def get_history():
    """Get chat history for current user"""
    history = ChatHistory.query.filter_by(user_id=current_user.id).order_by(ChatHistory.timestamp).all()
    
    return jsonify([{
        'message': h.message,
        'response': h.response,
        'timestamp': h.timestamp.isoformat()
    } for h in history])
