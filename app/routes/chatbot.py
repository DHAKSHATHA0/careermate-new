import os
import time
import json
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, jsonify, Response, stream_with_context, current_app, send_from_directory
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.extensions import db
from app.models.chat_history import ChatHistory
from app.models.conversation import Conversation, ConversationMessage
from app.services.career_agent import CareerMateAgent
from app.services.image_intelligence import ImageIntelligence

chatbot_bp = Blueprint('chatbot', __name__)
agent = CareerMateAgent()

ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}

def allowed_image_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


@chatbot_bp.route('/assistant')
@chatbot_bp.route('/chatbot/chat')
@chatbot_bp.route('/chatbot')
@login_required
def chat():
    """Full-page CareerMate AI Workspace"""
    return render_template('chatbot.html', user=current_user)


# ==========================================
# CONVERSATIONS MANAGEMENT REST API
# ==========================================

@chatbot_bp.route('/api/assistant/conversations', methods=['GET'])
@login_required
def list_conversations():
    """List categorized conversations for current user with optional search."""
    search_q = request.args.get('q', '').strip().lower()
    
    query = Conversation.query.filter_by(user_id=current_user.id, archived=False)
    
    if search_q:
        # Search by title or message content
        query = query.filter(
            (Conversation.title.ilike(f"%{search_q}%")) |
            (Conversation.messages.any(ConversationMessage.content.ilike(f"%{search_q}%")))
        )
        
    conversations = query.order_by(Conversation.last_message_at.desc()).all()
    
    # Categorize into Today, Yesterday, Previous 7 days, Older
    now = datetime.utcnow()
    today_start = datetime(now.year, now.month, now.day)
    yesterday_start = today_start - timedelta(days=1)
    week_start = today_start - timedelta(days=7)
    
    categorized = {
        'today': [],
        'yesterday': [],
        'previous_7_days': [],
        'older': []
    }
    
    for c in conversations:
        c_dict = c.to_dict()
        msg_time = c.last_message_at or c.created_at
        if msg_time >= today_start:
            categorized['today'].append(c_dict)
        elif msg_time >= yesterday_start:
            categorized['yesterday'].append(c_dict)
        elif msg_time >= week_start:
            categorized['previous_7_days'].append(c_dict)
        else:
            categorized['older'].append(c_dict)
            
    return jsonify({
        'success': True,
        'total': len(conversations),
        'categorized': categorized,
        'conversations': [c.to_dict() for c in conversations]
    })


@chatbot_bp.route('/api/assistant/conversations', methods=['POST'])
@login_required
def create_conversation():
    """Create a new conversation workspace."""
    data = request.get_json() or {}
    title = data.get('title', '').strip() or 'New Conversation'
    
    conv = Conversation(
        user_id=current_user.id,
        title=title,
        last_message_at=datetime.utcnow()
    )
    db.session.add(conv)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'conversation': conv.to_dict()
    }), 201


@chatbot_bp.route('/api/assistant/conversations/<int:conv_id>', methods=['GET'])
@login_required
def get_conversation(conv_id):
    """Retrieve full conversation thread and messages for authenticated user."""
    conv = Conversation.query.filter_by(id=conv_id, user_id=current_user.id).first()
    if not conv:
        return jsonify({'error': 'Conversation not found or unauthorized'}), 404
        
    messages = [m.to_dict() for m in conv.messages]
    
    return jsonify({
        'success': True,
        'conversation': conv.to_dict(),
        'messages': messages
    })


@chatbot_bp.route('/api/assistant/conversations/<int:conv_id>', methods=['PATCH'])
@login_required
def update_conversation(conv_id):
    """Rename or archive conversation."""
    conv = Conversation.query.filter_by(id=conv_id, user_id=current_user.id).first()
    if not conv:
        return jsonify({'error': 'Conversation not found or unauthorized'}), 404
        
    data = request.get_json() or {}
    if 'title' in data and data['title'].strip():
        conv.title = data['title'].strip()
    if 'archived' in data:
        conv.archived = bool(data['archived'])
        
    conv.updated_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify({
        'success': True,
        'conversation': conv.to_dict()
    })


@chatbot_bp.route('/api/assistant/conversations/<int:conv_id>', methods=['DELETE'])
@login_required
def delete_conversation(conv_id):
    """Delete conversation and its message history (strict ownership verified)."""
    conv = Conversation.query.filter_by(id=conv_id, user_id=current_user.id).first()
    if not conv:
        return jsonify({'error': 'Conversation not found or unauthorized'}), 404
        
    db.session.delete(conv)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Conversation deleted successfully.'
    })


# ==========================================
# MESSAGING & MULTIMODAL ENDPOINTS
# ==========================================

@chatbot_bp.route('/api/assistant/conversations/<int:conv_id>/messages', methods=['POST'])
@login_required
def send_conversation_message(conv_id):
    """Send a user message (text, image, or multimodal) and receive grounded intelligence response."""
    conv = Conversation.query.filter_by(id=conv_id, user_id=current_user.id).first()
    if not conv:
        return jsonify({'error': 'Conversation not found or unauthorized'}), 404
        
    data = request.get_json() or {}
    message_text = data.get('content', '').strip()
    image_url = data.get('image_url')
    msg_type = 'mixed' if (message_text and image_url) else ('image' if image_url else 'text')
    
    if not message_text and not image_url:
        return jsonify({'error': 'Message content or image required'}), 400
        
    # Persist User Message
    user_msg = ConversationMessage(
        conversation_id=conv.id,
        role='user',
        content=message_text or 'Uploaded an image',
        message_type=msg_type,
        image_url=image_url
    )
    db.session.add(user_msg)
    
    # Resolve image local path if image_url provided
    local_image_path = None
    if image_url:
        filename = os.path.basename(image_url)
        upload_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'chat_images')
        potential_path = os.path.join(upload_folder, filename)
        if os.path.exists(potential_path):
            local_image_path = potential_path
            
    # Prepare chat history for conversational context
    history = [{'message': m.content, 'response': ''} for m in conv.messages if m.role == 'user']
    
    # Process through Career Intelligence Agent
    result = agent.process_message(
        user=current_user,
        message=message_text,
        image_path=local_image_path,
        history=history
    )
    
    # Persist Assistant Response
    assistant_msg = ConversationMessage(
        conversation_id=conv.id,
        role='assistant',
        content=result.get('response', ''),
        message_type='text',
        metadata_json=json.dumps({
            'sources': result.get('sources', []),
            'intent': result.get('intent', '')
        })
    )
    db.session.add(assistant_msg)
    
    # Auto-generate meaningful title if this is the first interaction
    if len(conv.messages) <= 2 and (conv.title == 'New Conversation' or not conv.title):
        first_q = message_text.lower()
        if 'roadmap' in first_q or 'become' in first_q:
            conv.title = 'Career Roadmap Plan'
        elif 'interview' in first_q:
            conv.title = 'Interview Preparation & Feedback'
        elif 'resume' in first_q or 'ats' in first_q:
            conv.title = 'Resume & ATS Optimization'
        elif 'job' in first_q:
            conv.title = 'Job Fit & Matching Search'
        elif 'course' in first_q or 'learn' in first_q:
            conv.title = 'Course Learning Track'
        else:
            conv.title = (message_text[:35] + '...') if len(message_text) > 35 else message_text
            
    conv.last_message_at = datetime.utcnow()
    conv.updated_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify({
        'success': True,
        'user_message': user_msg.to_dict(),
        'assistant_message': assistant_msg.to_dict(),
        'sources': result.get('sources', []),
        'intent': result.get('intent', '')
    })


@chatbot_bp.route('/api/assistant/conversations/<int:conv_id>/stream', methods=['POST'])
@login_required
def stream_conversation_message(conv_id):
    """Server-Sent Events endpoint for streaming LLM response."""
    conv = Conversation.query.filter_by(id=conv_id, user_id=current_user.id).first()
    if not conv:
        return jsonify({'error': 'Conversation not found or unauthorized'}), 404
        
    data = request.get_json() or {}
    message_text = data.get('content', '').strip()
    image_url = data.get('image_url')
    
    if not message_text and not image_url:
        return jsonify({'error': 'Message content or image required'}), 400
        
    # Save user message
    user_msg = ConversationMessage(
        conversation_id=conv.id,
        role='user',
        content=message_text or 'Uploaded image',
        message_type='image' if image_url and not message_text else ('mixed' if image_url else 'text'),
        image_url=image_url
    )
    db.session.add(user_msg)
    db.session.commit()
    
    local_image_path = None
    if image_url:
        filename = os.path.basename(image_url)
        upload_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'chat_images')
        potential_path = os.path.join(upload_folder, filename)
        if os.path.exists(potential_path):
            local_image_path = potential_path
            
    history = [{'message': m.content, 'response': ''} for m in conv.messages if m.role == 'user']
    
    def generate():
        full_response_text = ""
        sources = []
        for line in agent.stream_message(current_user, message_text, local_image_path, history):
            chunk_data = json.loads(line)
            if chunk_data.get('type') == 'chunk':
                full_response_text += chunk_data.get('content', '')
                yield f"data: {line}\n\n"
            elif chunk_data.get('type') == 'done':
                full_response_text = chunk_data.get('full_response', full_response_text)
                sources = chunk_data.get('sources', [])
                yield f"data: {line}\n\n"
                
        # Save assistant message on stream completion
        with current_app.app_context():
            asst_msg = ConversationMessage(
                conversation_id=conv_id,
                role='assistant',
                content=full_response_text,
                message_type='text',
                metadata_json=json.dumps({'sources': sources})
            )
            db.session.add(asst_msg)
            c_rec = db.session.get(Conversation, conv_id)
            if c_rec:
                c_rec.last_message_at = datetime.utcnow()
            db.session.commit()

    return Response(stream_with_context(generate()), mimetype='text/event-stream')


@chatbot_bp.route('/api/assistant/upload-image', methods=['POST'])
@login_required
def upload_chat_image():
    """Upload career-related image, preprocess with OpenCV, and run OCR extraction."""
    if 'file' not in request.files:
        return jsonify({'error': 'No image file uploaded'}), 400
        
    file = request.files['file']
    if not file or file.filename == '':
        return jsonify({'error': 'Empty filename'}), 400
        
    if not allowed_image_file(file.filename):
        return jsonify({'error': 'Supported image formats: PNG, JPG, JPEG, WEBP'}), 400
        
    try:
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
        saved_filename = f"{timestamp}{filename}"
        
        upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'chat_images')
        os.makedirs(upload_dir, exist_ok=True)
        
        file_path = os.path.join(upload_dir, saved_filename)
        file.save(file_path)
        
        # Run computer vision preprocessing & OCR
        ocr_result = ImageIntelligence.extract_text(file_path)
        extracted_text = ocr_result.get('text', '')
        career_analysis = ImageIntelligence.classify_and_extract_career_data(extracted_text, current_user.id)
        
        image_url = f"/api/assistant/images/{saved_filename}"
        
        return jsonify({
            'success': True,
            'image_url': image_url,
            'filename': saved_filename,
            'ocr_text': extracted_text[:500],
            'doc_type': career_analysis.get('doc_type'),
            'extracted_skills': career_analysis.get('extracted_skills', []),
            'matching_skills': career_analysis.get('matching_skills', []),
            'missing_skills': career_analysis.get('missing_skills', [])
        })
    except Exception as e:
        logger.error(f"Image upload error: {e}")
        return jsonify({'error': f"Image processing failed: {str(e)}"}), 500


@chatbot_bp.route('/api/assistant/images/<path:filename>', methods=['GET'])
@login_required
def serve_chat_image(filename):
    """Securely serve uploaded conversation images for authenticated users."""
    upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'chat_images')
    return send_from_directory(upload_dir, secure_filename(filename))


@chatbot_bp.route('/api/assistant/transcribe', methods=['POST'])
@login_required
def transcribe_audio():
    """Speech-to-text endpoint for voice inputs."""
    data = request.get_json() or {}
    transcript = data.get('text', '').strip()
    
    if transcript:
        return jsonify({'success': True, 'transcript': transcript})
        
    return jsonify({
        'success': True,
        'transcript': transcript,
        'message': 'Speech recognition processed.'
    })


@chatbot_bp.route('/api/assistant/speak', methods=['POST'])
@login_required
def text_to_speech():
    """Text-to-speech configuration helper."""
    data = request.get_json() or {}
    text = data.get('text', '').strip()
    return jsonify({
        'success': True,
        'text': text[:500],
        'provider': 'web_speech_api'
    })


# ==========================================
# BACKWARD COMPATIBLE CHAT API
# ==========================================

@chatbot_bp.route('/api/message', methods=['POST'])
@chatbot_bp.route('/chatbot/api/message', methods=['POST'])
@login_required
def send_message():
    """Legacy backward-compatible message API."""
    data = request.get_json() or {}
    user_message = data.get('message', '').strip()
    
    if not user_message:
        return jsonify({'error': 'Message cannot be empty'}), 400
        
    past_records = ChatHistory.query.filter_by(user_id=current_user.id).order_by(ChatHistory.timestamp.asc()).all()
    history = [{'message': r.message, 'response': r.response} for r in past_records]
    
    response_data = agent.process_message(current_user, user_message, history=history)
    
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
        'sources': response_data['sources'],
        'intent': response_data.get('intent')
    })


@chatbot_bp.route('/api/history', methods=['GET'])
@chatbot_bp.route('/chatbot/api/history', methods=['GET'])
@login_required
def get_history():
    """Legacy chat history."""
    history = ChatHistory.query.filter_by(user_id=current_user.id).order_by(ChatHistory.timestamp.asc()).all()
    return jsonify([{
        'message': h.message,
        'response': h.response,
        'timestamp': h.timestamp.isoformat()
    } for h in history])


@chatbot_bp.route('/api/clear', methods=['POST'])
@chatbot_bp.route('/chatbot/api/clear', methods=['POST'])
@login_required
def clear_history():
    """Legacy clear history."""
    ChatHistory.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    return jsonify({'success': True, 'message': 'Chat history cleared.'})
