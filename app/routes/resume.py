from flask import Blueprint, render_template, request, jsonify, send_from_directory, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.extensions import db
from app.models.resume import Resume
from app.utils.resume_parser import ResumeParser
from app.utils.nlp_analyzer import NLPAnalyzer
from app.utils.similarity import SimilarityScorer
import os
from datetime import datetime

resume_bp = Blueprint('resume', __name__, url_prefix='/resume')

# Initialize analyzers
nlp_analyzer = NLPAnalyzer()
similarity_scorer = SimilarityScorer()

@resume_bp.route('/')
@resume_bp.route('/analyzer')
@login_required
def analyzer():
    """5. Resume Analyzer Page"""
    user_resumes = Resume.query.filter_by(user_id=current_user.id).order_by(Resume.uploaded_at.desc()).all()
    latest_resume = user_resumes[0] if user_resumes else None
    
    initial_analysis = None
    if latest_resume and os.path.exists(latest_resume.file_path):
        try:
            resume_text = ResumeParser.extract_text(latest_resume.file_path)
            if resume_text:
                initial_analysis = {
                    'resume_id': latest_resume.resume_id,
                    'filename': os.path.basename(latest_resume.file_path),
                    'uploaded_at': latest_resume.uploaded_at.strftime('%b %d, %Y'),
                    'ats_score': latest_resume.ats_score or similarity_scorer.calculate_ats_score(resume_text),
                    'keywords': nlp_analyzer.extract_keywords(resume_text),
                    'entities': nlp_analyzer.extract_entities(resume_text),
                    'grammar_issues': nlp_analyzer.check_grammar_issues(resume_text),
                    'formatting_issues': nlp_analyzer.analyze_formatting(resume_text),
                    'word_count': len(resume_text.split()),
                    'preview_text': resume_text[:1200]
                }
        except Exception as e:
            print(f"Error pre-analyzing resume: {e}")
            
    return render_template('resume_analyzer.html', resumes=user_resumes, latest_resume=latest_resume, initial_analysis=initial_analysis)

@resume_bp.route('/api/upload', methods=['POST'])
@login_required
def upload_resume():
    """Upload and analyze resume"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    is_valid, errors = ResumeParser.validate_file(file)
    if not is_valid:
        return jsonify({'error': ', '.join(errors)}), 400
    
    file_path = ""
    try:
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
        filename = timestamp + filename
        
        upload_folder = current_app.config['UPLOAD_FOLDER']
        os.makedirs(upload_folder, exist_ok=True)
        
        file_path = os.path.join(upload_folder, filename)
        file.save(file_path)
        
        # Parse resume text
        resume_text = ResumeParser.extract_text(file_path)
        
        if not resume_text or len(resume_text.strip()) < 50:
            if os.path.exists(file_path):
                os.remove(file_path)
            return jsonify({'error': 'Resume appears to be empty or unreadable'}), 400
        
        # Real NLP & ATS calculations
        ats_score = similarity_scorer.calculate_ats_score(resume_text)
        keywords = nlp_analyzer.extract_keywords(resume_text)
        entities = nlp_analyzer.extract_entities(resume_text)
        grammar_issues = nlp_analyzer.check_grammar_issues(resume_text)
        formatting_issues = nlp_analyzer.analyze_formatting(resume_text)
        job_fit = similarity_scorer.calculate_similarity(
            resume_text,
            current_app.config.get('SAMPLE_JOB_DESCRIPTION', 'Software engineering role with Python, JavaScript, SQL, Git')
        )
        
        # Save to database
        resume_record = Resume(
            user_id=current_user.id,
            file_path=file_path,
            ats_score=ats_score
        )
        db.session.add(resume_record)
        db.session.commit()
        
        analysis = {
            'resume_id': resume_record.resume_id,
            'ats_score': ats_score,
            'keywords': keywords,
            'entities': entities,
            'grammar_issues': grammar_issues,
            'formatting_issues': formatting_issues,
            'job_fit': job_fit,
            'word_count': len(resume_text.split()),
            'preview_text': resume_text[:1200]
        }
        
        return jsonify({
            'success': True,
            'resume_id': resume_record.resume_id,
            'analysis': analysis
        })
    
    except Exception as e:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
        return jsonify({'error': f'Analysis failed: {str(e)}'}), 500

@resume_bp.route('/api/resume/<int:resume_id>')
@login_required
def get_resume_analysis(resume_id):
    """Get stored resume analysis"""
    resume = Resume.query.get(resume_id)
    if not resume or resume.user_id != current_user.id:
        return jsonify({'error': 'Resume not found'}), 404
    
    if not os.path.exists(resume.file_path):
        return jsonify({'error': 'Resume file not found on disk'}), 404
    
    try:
        resume_text = ResumeParser.extract_text(resume.file_path)
        analysis = {
            'resume_id': resume_id,
            'filename': os.path.basename(resume.file_path),
            'uploaded_at': resume.uploaded_at.isoformat(),
            'ats_score': resume.ats_score or similarity_scorer.calculate_ats_score(resume_text),
            'keywords': nlp_analyzer.extract_keywords(resume_text),
            'entities': nlp_analyzer.extract_entities(resume_text),
            'grammar_issues': nlp_analyzer.check_grammar_issues(resume_text),
            'formatting_issues': nlp_analyzer.analyze_formatting(resume_text),
            'word_count': len(resume_text.split()),
            'preview_text': resume_text[:1200]
        }
        return jsonify({'analysis': analysis})
    except Exception as e:
        return jsonify({'error': f'Analysis failed: {str(e)}'}), 500

@resume_bp.route('/download/<int:resume_id>')
@login_required
def download_resume(resume_id):
    """Download resume file securely"""
    resume = Resume.query.get(resume_id)
    if not resume or resume.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    if not os.path.exists(resume.file_path):
        return jsonify({'error': 'File not found'}), 404
    
    directory = os.path.dirname(resume.file_path)
    filename = os.path.basename(resume.file_path)
    return send_from_directory(directory, filename, as_attachment=True)

@resume_bp.route('/api/delete/<int:resume_id>', methods=['POST', 'DELETE'])
@login_required
def delete_resume(resume_id):
    """Delete resume"""
    resume = Resume.query.get(resume_id)
    if not resume or resume.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        if os.path.exists(resume.file_path):
            os.remove(resume.file_path)
        db.session.delete(resume)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
