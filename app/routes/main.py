from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.extensions import db
from app.models.user import User
from app.models.skill import Skill
from app.models.company import Company
from app.models.resume import Resume
from app.models.question import Question
from app.models.enrollment import CourseEnrollment
from app.models.job_feedback import JobFeedback
from app.models.job_analysis import JobAnalysis
from app.utils.profile import calculate_profile_completeness
from app.utils.resume_parser import ResumeParser
from app.utils.nlp_analyzer import NLPAnalyzer
from app.utils.similarity import SimilarityScorer
from app.utils.recommendations import JobRecommendationEngine, DOMAIN_ROLE_SKILLS, DOMAIN_MAPPING
import os
from datetime import datetime

main_bp = Blueprint('main', __name__)

nlp_analyzer = NLPAnalyzer()
similarity_scorer = SimilarityScorer()

# Verified official learning resources mapped directly to skills
SKILL_LEARNING_RESOURCES = {
    'Python': {'type': 'Official Docs & Course', 'provider': 'Python Software Foundation', 'url': 'https://docs.python.org/3/tutorial/', 'difficulty': 'Beginner - Intermediate', 'time': '3-4 weeks', 'impact': 'Core Programming'},
    'JavaScript': {'type': 'Documentation & Tutorials', 'provider': 'MDN Web Docs', 'url': 'https://developer.mozilla.org/en-US/docs/Web/JavaScript', 'difficulty': 'Beginner - Intermediate', 'time': '3-4 weeks', 'impact': 'Frontend & Full Stack'},
    'React': {'type': 'Official Interactive Docs', 'provider': 'React.dev', 'url': 'https://react.dev/learn', 'difficulty': 'Intermediate', 'time': '2-3 weeks', 'impact': 'Modern UI Development'},
    'Node.js': {'type': 'Official Guides', 'provider': 'Node.js Foundation', 'url': 'https://nodejs.org/en/learn', 'difficulty': 'Intermediate', 'time': '2-3 weeks', 'impact': 'Backend Runtime'},
    'SQL': {'type': 'Interactive Database Tutorial', 'provider': 'PostgreSQL / W3Schools', 'url': 'https://www.postgresql.org/docs/current/tutorial.html', 'difficulty': 'Beginner - Intermediate', 'time': '2 weeks', 'impact': 'Data Persistence'},
    'Docker': {'type': 'Hands-on Labs', 'provider': 'Docker Official Docs', 'url': 'https://docs.docker.com/get-started/', 'difficulty': 'Intermediate', 'time': '1-2 weeks', 'impact': 'Containerization & DevOps'},
    'Kubernetes': {'type': 'Interactive Basics', 'provider': 'Kubernetes.io', 'url': 'https://kubernetes.io/docs/tutorials/kubernetes-basics/', 'difficulty': 'Advanced', 'time': '3-4 weeks', 'impact': 'Cloud Orchestration'},
    'AWS': {'type': 'Skill Builder Cloud Essentials', 'provider': 'AWS Training', 'url': 'https://aws.amazon.com/training/digital/', 'difficulty': 'Intermediate', 'time': '3-4 weeks', 'impact': 'Cloud Infrastructure'},
    'Machine Learning': {'type': 'Comprehensive Guide', 'provider': 'Scikit-Learn Documentation', 'url': 'https://scikit-learn.org/stable/tutorial/index.html', 'difficulty': 'Intermediate - Advanced', 'time': '4-6 weeks', 'impact': 'AI Modeling'},
    'Deep Learning': {'type': 'Foundations Course', 'provider': 'PyTorch Tutorials', 'url': 'https://pytorch.org/tutorials/', 'difficulty': 'Advanced', 'time': '4-6 weeks', 'impact': 'Neural Networks'},
    'System Design': {'type': 'System Architecture Guide', 'provider': 'System Design Primer', 'url': 'https://github.com/donnemartin/system-design-primer', 'difficulty': 'Advanced', 'time': '4 weeks', 'impact': 'High-Scale Engineering'},
    'Git': {'type': 'Version Control Book', 'provider': 'Pro Git Book', 'url': 'https://git-scm.com/book/en/v2', 'difficulty': 'Beginner', 'time': '1 week', 'impact': 'Collaboration'},
    'REST APIs': {'type': 'API Design Guide', 'provider': 'RESTful API Tutorial', 'url': 'https://restfulapi.net/', 'difficulty': 'Intermediate', 'time': '1 week', 'impact': 'Service Architecture'}
}


@main_bp.route('/')
def index():
    """1. Landing Page - Locked Editorial Storytelling & Feature Showcase"""
    companies = Company.query.all()
    skills = Skill.query.limit(24).all()
    question_count = Question.query.count()
    return render_template(
        'index.html',
        companies=companies,
        skills=skills,
        question_count=question_count
    )


@main_bp.route('/signup')
def signup_shortcut():
    """Sign up shortcut route"""
    return redirect(url_for('auth.register'))


@main_bp.route('/login')
def login_shortcut():
    """Login shortcut route"""
    return redirect(url_for('auth.login'))


@main_bp.route('/dashboard')
@login_required
def dashboard():
    """Career Dashboard - State-aware career command center with genuine intelligence."""
    user = current_user
    
    # 1. Real Resumes & ATS evaluation
    resumes = Resume.query.filter_by(user_id=user.id).order_by(Resume.uploaded_at.desc()).all()
    latest_resume = resumes[0] if resumes else None
    has_resume = bool(latest_resume)
    
    # 2. Profile completeness evaluation (based on user fields)
    profile_pct = calculate_profile_completeness(user)
    is_profile_complete = bool(user.domain and ((user.college_name and user.degree) or user.current_company))
    
    # 3. Dynamic Career Hero State Calculation
    # State 1: Incomplete profile + No resume
    # State 2: Complete profile + No resume
    # State 3: Incomplete profile + Resume exists
    # State 4: Complete profile + Resume exists
    if not is_profile_complete and not has_resume:
        hero_state = 1
        hero_title = "Complete Your Career Profile"
        hero_desc = "Help CareerMate understand your background to calculate accurate job fit and skill gap recommendations."
    elif is_profile_complete and not has_resume:
        hero_state = 2
        hero_title = "Upload Your Resume to Get Closer to Your Dream Job"
        hero_desc = "Upload your PDF or DOCX resume to calculate your genuine ATS compatibility score and extract keyword insights."
    elif not is_profile_complete and has_resume:
        hero_state = 3
        hero_title = "Complete Your Career Profile"
        hero_desc = "Your resume is active. Complete your education and domain preferences to fine-tune your job match ranking."
    else:
        hero_state = 4
        hero_title = "Your Career Profile Is Ready"
        hero_desc = "Your profile and resume intelligence are active. Review your real-time matches and learning steps below."
        
    target_role = DOMAIN_MAPPING.get(user.domain, 'Full Stack Engineer')
    
    # 4. Locked "Your Next Best Move"
    if not has_resume:
        next_action = {
            'title': 'Upload Your Resume for Intelligence Analysis',
            'desc': 'Upload your PDF or DOCX resume to calculate your genuine ATS compatibility score and extract keyword insights.',
            'url': url_for('resume.analyzer'),
            'cta': 'Analyze Resume'
        }
    else:
        next_action = {
            'title': 'Upload Your Resume for Intelligence Analysis',
            'desc': 'Upload your PDF or DOCX resume to calculate your genuine ATS compatibility score and extract keyword insights.',
            'url': url_for('resume.analyzer'),
            'cta': 'Analyze Resume'
        }
        
    # 5. Box A: Real ATS Resume Score data & freshness
    ats_data = {
        'has_resume': has_resume,
        'ats_score': latest_resume.ats_score if (latest_resume and latest_resume.ats_score is not None) else None,
        'uploaded_at': latest_resume.uploaded_at if latest_resume else None,
        'target_role': target_role,
        'freshness': latest_resume.uploaded_at.strftime('%b %d, %Y') if latest_resume else None
    }
    
    # 6. Box B: Real Enrolled Courses data
    enrolled_courses = CourseEnrollment.query.filter_by(user_id=user.id).order_by(CourseEnrollment.updated_at.desc()).all()
    
    # 7. Recommended Jobs from Real Recommendation Engine
    recommendations_result = JobRecommendationEngine.get_recommendations(user, latest_resume, limit=4)
    
    # 8. Build Your Missing Skills from Real Resume-to-Job Analysis
    latest_analysis = JobAnalysis.query.filter_by(user_id=user.id).order_by(JobAnalysis.created_at.desc()).first()
    
    missing_skills_data = {
        'has_analysis': False,
        'source_label': None,
        'target_job': None,
        'missing_skills': [],
        'analysis_date': None
    }
    
    if latest_analysis:
        missing_skills_data = {
            'has_analysis': True,
            'source_label': f"Based on your latest job analysis",
            'target_job': f"{latest_analysis.company_name} — {latest_analysis.target_role}",
            'missing_skills': latest_analysis.missing_skills[:8],
            'analysis_date': latest_analysis.created_at.strftime('%b %d, %Y')
        }
    elif has_resume and latest_resume.file_path and os.path.exists(latest_resume.file_path):
        try:
            r_text = ResumeParser.extract_text(latest_resume.file_path)
            if r_text:
                top_comp = Company.query.first()
                comp_name = top_comp.company_name if top_comp else "Industry Benchmark"
                comp_desc = f"{comp_name} {top_comp.description or ''} {top_comp.eligibility or ''}" if top_comp else target_role
                gaps = similarity_scorer.extract_missing_keywords(r_text, comp_desc)
                
                all_valid_skills = set([s.skill_name.lower() for s in Skill.query.all()] + [k.lower() for k in DOMAIN_ROLE_SKILLS.get(target_role, [])])
                filtered_gaps = [w.title() for w in gaps if w.lower() in all_valid_skills]
                if not filtered_gaps:
                    user_keywords = [k.lower() for k in nlp_analyzer.extract_keywords(r_text)]
                    filtered_gaps = [s for s in DOMAIN_ROLE_SKILLS.get(target_role, []) if s.lower() not in user_keywords]
                    
                missing_skills_data = {
                    'has_analysis': True,
                    'source_label': f"Based on your latest job analysis",
                    'target_job': f"{comp_name} — {target_role}",
                    'missing_skills': filtered_gaps[:8],
                    'analysis_date': latest_resume.uploaded_at.strftime('%b %d, %Y')
                }
        except Exception:
            pass
            
    return render_template(
        'dashboard.html',
        user=user,
        hero_state=hero_state,
        hero_title=hero_title,
        hero_desc=hero_desc,
        is_profile_complete=is_profile_complete,
        has_resume=has_resume,
        target_role=target_role,
        next_action=next_action,
        ats_data=ats_data,
        latest_resume=latest_resume,
        enrolled_courses=enrolled_courses,
        recommendations=recommendations_result,
        missing_skills_data=missing_skills_data
    )


@main_bp.route('/job-fit')
@login_required
def job_fit():
    """6. Job Fit Analysis - How well do I fit this job?"""
    user = current_user
    companies = Company.query.all()
    selected_company_id = request.args.get('company_id', type=int)
    custom_jd = request.args.get('jd', '').strip()
    
    # Get user's latest resume text
    resumes = Resume.query.filter_by(user_id=user.id).order_by(Resume.uploaded_at.desc()).all()
    latest_resume = resumes[0] if resumes else None
    
    resume_text = ""
    if latest_resume and os.path.exists(latest_resume.file_path):
        try:
            resume_text = ResumeParser.extract_text(latest_resume.file_path) or ""
        except Exception:
            resume_text = ""
            
    # Build fallback resume profile from user database skills & education if no file uploaded
    if not resume_text:
        user_skills_str = ", ".join([s.skill_name for s in user.skills])
        resume_text = f"Candidate: {user.name}\nEducation: {user.degree or ''} {user.college_name or ''}\nSkills: {user_skills_str}\nDomain: {user.domain or ''}"
    
    selected_company = None
    target_job_text = custom_jd
    
    if selected_company_id:
        selected_company = Company.query.get(selected_company_id)
        if selected_company:
            target_job_text = f"{selected_company.company_name}\nDescription: {selected_company.description or ''}\nEligibility: {selected_company.eligibility or ''}\nSelection Process: {selected_company.selection_process or ''}"
    elif not custom_jd and companies:
        selected_company = companies[0]
        target_job_text = f"{selected_company.company_name}\nDescription: {selected_company.description or ''}\nEligibility: {selected_company.eligibility or ''}\nSelection Process: {selected_company.selection_process or ''}"
    
    analysis_result = None
    if target_job_text:
        overall_score = similarity_scorer.calculate_similarity(resume_text, target_job_text)
        matching_keywords = similarity_scorer.get_matching_keywords(resume_text, target_job_text)
        missing_keywords = similarity_scorer.extract_missing_keywords(resume_text, target_job_text)
        
        # Breakdown calculations
        skill_score = min(int(len(matching_keywords) * 12), 100) if matching_keywords else 10
        exp_score = 75 if user.user_type == 'professional' else 55 if user.user_type == 'fresher' else 40
        edu_score = 90 if (user.degree and user.college_name) else 50
        
        if overall_score >= 70:
            rec = "Strong Fit — Your profile and technical background strongly align with this position. Recommended to apply."
            status_badge = "Strong Fit"
        elif overall_score >= 40:
            rec = "Moderate Fit — You possess essential foundational qualifications, but closing specific keyword and tool gaps will significantly boost interview probability."
            status_badge = "Moderate Fit"
        else:
            rec = "Skill Gap Present — We recommend strengthening missing required competencies through dedicated coursework and projects prior to applying."
            status_badge = "Skill Gap"
            
        analysis_result = {
            'overall_score': overall_score,
            'skill_score': skill_score,
            'exp_score': exp_score,
            'edu_score': edu_score,
            'matching_keywords': matching_keywords,
            'missing_keywords': missing_keywords,
            'recommendation': rec,
            'status_badge': status_badge,
            'has_resume_file': bool(latest_resume)
        }
        
        # Persist JobAnalysis record for multi-job analysis history and traceability
        try:
            comp_name = selected_company.company_name if selected_company else ("Custom Job" if custom_jd else "Target Role")
            role_name = user.domain or 'Full Stack Engineer'
            job_analysis_record = JobAnalysis(
                user_id=user.id,
                resume_id=latest_resume.resume_id if latest_resume else None,
                company_id=selected_company.company_id if selected_company else None,
                company_name=comp_name,
                target_role=role_name,
                score=overall_score
            )
            job_analysis_record.matching_skills = matching_keywords
            job_analysis_record.missing_skills = missing_keywords
            db.session.add(job_analysis_record)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"Error persisting job analysis: {e}")
            
    return render_template(
        'job_fit.html',
        companies=companies,
        selected_company=selected_company,
        custom_jd=custom_jd,
        analysis=analysis_result,
        latest_resume=latest_resume
    )


@main_bp.route('/skill-gap')
@login_required
def skill_gap():
    """7. Skill Gap Analysis - What am I missing for my target career?"""
    user = current_user
    selected_role = request.args.get('role', 'Full Stack Engineer')
    if selected_role not in DOMAIN_ROLE_SKILLS:
        selected_role = 'Full Stack Engineer'
        
    required_skills = DOMAIN_ROLE_SKILLS[selected_role]
    
    # User's known skills (from profile + parsed resume)
    user_skills = [s.skill_name.lower() for s in user.skills]
    resumes = Resume.query.filter_by(user_id=user.id).order_by(Resume.uploaded_at.desc()).all()
    latest_resume = resumes[0] if resumes else None
    
    if latest_resume and os.path.exists(latest_resume.file_path):
        try:
            r_text = ResumeParser.extract_text(latest_resume.file_path)
            if r_text:
                r_keywords = nlp_analyzer.extract_keywords(r_text)
                user_skills.extend([k.lower() for k in r_keywords])
        except Exception:
            pass
            
    user_skills = set(user_skills)
    
    strong_skills = []
    moderate_skills = []
    missing_skills = []
    
    for idx, skill in enumerate(required_skills):
        is_possessed = skill.lower() in user_skills
        if is_possessed:
            if idx < 3:
                strong_skills.append(skill)
            else:
                moderate_skills.append(skill)
        else:
            priority = 'High' if idx < 3 else 'Medium' if idx < 6 else 'Low'
            missing_skills.append({
                'skill': skill,
                'priority': priority,
                'relevance': f"Essential for {selected_role} architecture and core responsibilities.",
                'learning': SKILL_LEARNING_RESOURCES.get(skill, None)
            })
            
    match_percentage = int((len(strong_skills) + len(moderate_skills)) / max(len(required_skills), 1) * 100)
    
    return render_template(
        'skill_gap.html',
        roles=list(DOMAIN_ROLE_SKILLS.keys()),
        selected_role=selected_role,
        required_skills=required_skills,
        strong_skills=strong_skills,
        moderate_skills=moderate_skills,
        missing_skills=missing_skills,
        match_percentage=match_percentage,
        user=user
    )


@main_bp.route('/jobs')
@login_required
def jobs():
    """8. Job Recommendations - Which jobs are suitable for me?"""
    user = current_user
    search_query = request.args.get('q', '').strip().lower()
    
    # Real companies from DB
    companies = Company.query.all()
    
    # Gather user skills for genuine match calculation
    user_skills = [s.skill_name.lower() for s in user.skills]
    resumes = Resume.query.filter_by(user_id=user.id).order_by(Resume.uploaded_at.desc()).all()
    latest_resume = resumes[0] if resumes else None
    
    resume_text = ""
    if latest_resume and os.path.exists(latest_resume.file_path):
        try:
            resume_text = ResumeParser.extract_text(latest_resume.file_path) or ""
        except Exception:
            pass
            
    job_cards = []
    for comp in companies:
        # Search filter
        if search_query:
            if search_query not in comp.company_name.lower() and search_query not in (comp.description or '').lower():
                continue
                
        comp_text = f"{comp.company_name} {comp.description or ''} {comp.eligibility or ''}"
        
        # Calculate real similarity or skill matching
        if resume_text:
            match_score = similarity_scorer.calculate_similarity(resume_text, comp_text)
            matching_skills = similarity_scorer.get_matching_keywords(resume_text, comp_text)[:4]
            missing_skills = similarity_scorer.extract_missing_keywords(resume_text, comp_text)[:4]
        else:
            comp_words = set(comp_text.lower().split())
            matching_skills = [s for s in user_skills if s in comp_words][:4]
            missing_skills = [w.capitalize() for w in ['System Design', 'Docker', 'SQL', 'APIs'] if w.lower() not in user_skills][:3]
            match_score = int(min((len(matching_skills) / max(len(user_skills), 1)) * 80 + 20, 95)) if user_skills else 25
            
        job_cards.append({
            'company': comp,
            'match_score': match_score,
            'matching_skills': matching_skills,
            'missing_skills': missing_skills,
            'question_count': len(comp.questions)
        })
        
    job_cards.sort(key=lambda x: x['match_score'], reverse=True)
    
    return render_template(
        'jobs.html',
        jobs=job_cards,
        search_query=search_query,
        user=user
    )


@main_bp.route('/learning')
@login_required
def learning():
    """9. Learning Recommendations - What should I learn next?"""
    user = current_user
    
    # Determine user's domain role
    role_mapping = {
        'web_dev': 'Full Stack Engineer',
        'ml': 'AI/ML Engineer',
        'data_science': 'Data Scientist',
        'cloud': 'Cloud & DevOps Engineer',
        'core': 'Core Software Engineer'
    }
    target_role = role_mapping.get(user.domain, 'Full Stack Engineer')
    required_skills = DOMAIN_ROLE_SKILLS.get(target_role, DOMAIN_ROLE_SKILLS['Full Stack Engineer'])
    
    # User skills
    user_skills = [s.skill_name.lower() for s in user.skills]
    resumes = Resume.query.filter_by(user_id=user.id).order_by(Resume.uploaded_at.desc()).all()
    latest_resume = resumes[0] if resumes else None
    
    if latest_resume and os.path.exists(latest_resume.file_path):
        try:
            r_text = ResumeParser.extract_text(latest_resume.file_path)
            if r_text:
                r_keywords = nlp_analyzer.extract_keywords(r_text)
                user_skills.extend([k.lower() for k in r_keywords])
        except Exception:
            pass
            
    # Real identified skill gaps
    gap_skills = [s for s in required_skills if s.lower() not in user_skills]
    
    learning_paths = []
    for skill in gap_skills:
        res = SKILL_LEARNING_RESOURCES.get(skill)
        if res:
            learning_paths.append({
                'skill': skill,
                'resource': res,
                'target_role': target_role
            })
            
    return render_template(
        'learning.html',
        target_role=target_role,
        gap_skills=gap_skills,
        learning_paths=learning_paths,
        all_resources=SKILL_LEARNING_RESOURCES,
        user=user
    )


@main_bp.route('/roadmap')
@login_required
def roadmap():
    """10. Career Roadmap - Where should I go from here?"""
    user = current_user
    profile_pct = calculate_profile_completeness(user)
    
    # Real milestones based on user state
    has_skills = len(user.skills) > 0
    resumes = Resume.query.filter_by(user_id=user.id).all()
    has_resume = len(resumes) > 0
    
    role_mapping = {
        'web_dev': 'Full Stack Engineer',
        'ml': 'AI/ML Engineer',
        'data_science': 'Data Scientist',
        'cloud': 'Cloud & DevOps Engineer',
        'core': 'Core Software Engineer'
    }
    target_role = role_mapping.get(user.domain, 'Full Stack Engineer')
    
    stages = [
        {
            'step': 1,
            'title': 'Current Profile',
            'desc': 'Establish baseline career profile, educational foundation, and preferred domain target.',
            'status': 'completed' if profile_pct >= 60 else 'active',
            'milestones': [f"Account registered as {user.user_type.title()}", f"Domain: {user.domain or 'Not set'}", f"Profile Completeness: {profile_pct}%"]
        },
        {
            'step': 2,
            'title': 'Core Skills',
            'desc': 'Master foundational programming languages, data structures, and algorithms required for your target role.',
            'status': 'completed' if len(user.skills) >= 3 else ('active' if has_skills else 'pending'),
            'milestones': ['Programming Fundamentals', 'Object-Oriented Design', 'Data Structures & Algorithms']
        },
        {
            'step': 3,
            'title': 'Advanced Skills',
            'desc': 'Develop deep expertise in framework ecosystems, modern database systems, and REST API development.',
            'status': 'completed' if len(user.skills) >= 6 else 'pending',
            'milestones': ['Frameworks & Tooling', 'Database Modeling & Indexing', 'API Architecture']
        },
        {
            'step': 4,
            'title': 'Projects',
            'desc': 'Build end-to-end production-grade applications that demonstrate practical domain competence.',
            'status': 'active' if has_resume else 'pending',
            'milestones': ['Portfolio Web Application', 'Integrated Database & Authentication', 'Clean Code & Documentation']
        },
        {
            'step': 5,
            'title': 'Deployment & System Design',
            'desc': 'Deploy applications with Docker, configure CI/CD automation, and understand cloud architecture.',
            'status': 'pending',
            'milestones': ['Containerization with Docker', 'Cloud Deployment (AWS/GCP)', 'Basic System Architecture']
        },
        {
            'step': 6,
            'title': 'Interview Preparation',
            'desc': 'Practice company-specific technical assessments, aptitude problems, and system design questions.',
            'status': 'pending',
            'milestones': ['Company Practice Question Sets', 'Mock Technical Interviews', 'Behavioral & HR Prep']
        },
        {
            'step': 7,
            'title': 'Job Ready',
            'desc': 'Target compatible openings with an ATS-optimized resume and tailored portfolio.',
            'status': 'pending',
            'milestones': ['Resume ATS Score >= 80%', 'Verified Project Portfolio', 'Targeted Applications']
        },
        {
            'step': 8,
            'title': f"Target Career: {target_role}",
            'desc': f"Successfully transition into your goal position as a {target_role}.",
            'status': 'pending',
            'milestones': [f"Offer acceptance in {target_role}", 'Onboarding & Continuous Growth']
        }
    ]
    
    completed_count = sum(1 for s in stages if s['status'] == 'completed')
    overall_progress = int((completed_count / len(stages)) * 100)
    
    return render_template(
        'roadmap.html',
        stages=stages,
        target_role=target_role,
        overall_progress=overall_progress,
        user=user
    )


@main_bp.route('/assistant')
@login_required
def assistant():
    """11. CareerMate AI - Your personal career intelligence assistant"""
    return render_template('chatbot.html', user=current_user)


@main_bp.route('/preparation')
@login_required
def preparation():
    """Preparation Hub: Aptitude, DSA, Technical, Domain, Company Prep, HR/Behavioral"""
    user = current_user
    category = request.args.get('category', 'all').lower()
    difficulty = request.args.get('difficulty', 'all').lower()
    company_id = request.args.get('company_id', type=int)
    search_q = request.args.get('q', '').strip().lower()
    
    companies = Company.query.all()
    selected_company = Company.query.get(company_id) if company_id else None
    
    # Query real questions from DB
    q_query = Question.query
    if company_id:
        q_query = q_query.filter_by(company_id=company_id)
    if difficulty != 'all' and difficulty in ['easy', 'medium', 'hard']:
        q_query = q_query.filter_by(difficulty_level=difficulty)
    if category != 'all' and category in ['aptitude', 'technical', 'logical', 'verbal']:
        q_query = q_query.filter_by(question_type=category)
        
    all_db_questions = q_query.all()
    if search_q:
        all_db_questions = [q for q in all_db_questions if search_q in q.question.lower() or (q.answer and search_q in q.answer.lower())]
        
    # Preparation curriculum structures
    aptitude_topics = [
        {'name': 'Number System', 'category': 'Quantitative', 'questions_count': '15+ problems', 'difficulty': 'Easy - Medium', 'ref_url': 'https://www.geeksforgeeks.org/number-system-in-maths/'},
        {'name': 'Percentages & Profit/Loss', 'category': 'Quantitative', 'questions_count': '20+ problems', 'difficulty': 'Medium', 'ref_url': 'https://www.geeksforgeeks.org/profit-and-loss/'},
        {'name': 'Ratio & Proportion', 'category': 'Quantitative', 'questions_count': '15+ problems', 'difficulty': 'Easy - Medium', 'ref_url': 'https://www.geeksforgeeks.org/ratios-and-proportions/'},
        {'name': 'Time & Work', 'category': 'Quantitative', 'questions_count': '18+ problems', 'difficulty': 'Medium', 'ref_url': 'https://www.geeksforgeeks.org/time-and-work/'},
        {'name': 'Time, Speed & Distance', 'category': 'Quantitative', 'questions_count': '18+ problems', 'difficulty': 'Medium - Hard', 'ref_url': 'https://www.geeksforgeeks.org/time-speed-and-distance/'},
        {'name': 'Probability & Permutation', 'category': 'Quantitative', 'questions_count': '15+ problems', 'difficulty': 'Hard', 'ref_url': 'https://www.geeksforgeeks.org/permutations-and-combinations/'},
        {'name': 'Logical Reasoning & Series', 'category': 'Logical', 'questions_count': '25+ problems', 'difficulty': 'Medium', 'ref_url': 'https://www.geeksforgeeks.org/logical-reasoning/'},
        {'name': 'Data Interpretation', 'category': 'Logical', 'questions_count': '12+ sets', 'difficulty': 'Hard', 'ref_url': 'https://www.geeksforgeeks.org/data-interpretation-concepts/'},
        {'name': 'Verbal Ability & Grammar', 'category': 'Verbal', 'questions_count': '30+ questions', 'difficulty': 'Easy - Medium', 'ref_url': 'https://www.geeksforgeeks.org/verbal-ability/'}
    ]
    
    dsa_topics = [
        {'name': 'Arrays & Two Pointers', 'platform': 'LeetCode / GFG', 'problems': 'Two Sum, 3Sum, Container With Most Water, Trapping Rain Water', 'difficulty': 'Medium', 'ref_url': 'https://leetcode.com/tag/array/'},
        {'name': 'Strings & Sliding Window', 'platform': 'LeetCode', 'problems': 'Longest Substring Without Repeating Characters, Valid Anagram, Group Anagrams', 'difficulty': 'Medium', 'ref_url': 'https://leetcode.com/tag/sliding-window/'},
        {'name': 'Hashing & Frequency Maps', 'platform': 'LeetCode', 'problems': 'Subarray Sum Equals K, Top K Frequent Elements, LRU Cache', 'difficulty': 'Medium', 'ref_url': 'https://leetcode.com/tag/hash-table/'},
        {'name': 'Linked Lists', 'platform': 'LeetCode', 'problems': 'Reverse Linked List, Merge Two Sorted Lists, Detect Cycle, Copy List with Random Pointer', 'difficulty': 'Easy - Medium', 'ref_url': 'https://leetcode.com/tag/linked-list/'},
        {'name': 'Stacks & Queues', 'platform': 'LeetCode', 'problems': 'Valid Parentheses, Min Stack, Daily Temperatures, Implement Queue using Stacks', 'difficulty': 'Medium', 'ref_url': 'https://leetcode.com/tag/stack/'},
        {'name': 'Trees & BST', 'platform': 'LeetCode', 'problems': 'Maximum Depth of Binary Tree, Invert Binary Tree, Lowest Common Ancestor, Level Order Traversal', 'difficulty': 'Medium', 'ref_url': 'https://leetcode.com/tag/tree/'},
        {'name': 'Graphs & BFS/DFS', 'platform': 'LeetCode', 'problems': 'Number of Islands, Clone Graph, Course Schedule, Word Ladder', 'difficulty': 'Medium - Hard', 'ref_url': 'https://leetcode.com/tag/graph/'},
        {'name': 'Dynamic Programming', 'platform': 'LeetCode', 'problems': 'Climbing Stairs, Coin Change, Longest Increasing Subsequence, 0/1 Knapsack', 'difficulty': 'Hard', 'ref_url': 'https://leetcode.com/tag/dynamic-programming/'}
    ]
    
    technical_topics = [
        {'name': 'Object-Oriented Programming (OOP)', 'concepts': ['Encapsulation, Inheritance, Polymorphism, Abstraction', 'Design Patterns (Factory, Singleton, Observer)', 'SOLID Principles'], 'ref_url': 'https://www.geeksforgeeks.org/object-oriented-programming-oops-concept-in-java/'},
        {'name': 'Database Management Systems (DBMS)', 'concepts': ['ACID Properties & Transactions', 'Indexing (B-Trees, Hash Indexing)', 'Normalization (1NF, 2NF, 3NF, BCNF)', 'SQL Query Optimization'], 'ref_url': 'https://www.postgresql.org/docs/current/tutorial.html'},
        {'name': 'Operating Systems', 'concepts': ['Process vs Thread & Context Switching', 'CPU Scheduling Algorithms', 'Memory Management & Virtual Memory / Paging', 'Deadlocks & Concurrency Locks'], 'ref_url': 'https://www.geeksforgeeks.org/operating-systems/'},
        {'name': 'Computer Networks', 'concepts': ['OSI 7-Layer vs TCP/IP Model', 'TCP vs UDP Protocols & Three-Way Handshake', 'HTTP / HTTPS, SSL/TLS, DNS & Web Sockets'], 'ref_url': 'https://developer.mozilla.org/en-US/docs/Web/HTTP/Overview'},
        {'name': 'System Design Fundamentals', 'concepts': ['Load Balancers & Horizontal Scaling', 'Caching Strategies (Redis/Memcached)', 'Database Sharding & Replication', 'Microservices vs Monoliths'], 'ref_url': 'https://github.com/donnemartin/system-design-primer'}
    ]

    return render_template(
        'preparation.html',
        user=user,
        companies=companies,
        selected_company=selected_company,
        questions=all_db_questions,
        aptitude_topics=aptitude_topics,
        dsa_topics=dsa_topics,
        technical_topics=technical_topics,
        active_category=category,
        active_difficulty=difficulty,
        search_q=search_q
    )


@main_bp.route('/assessments', methods=['GET'])
@login_required
def assessments():
    """Assessments Hub: Configure customized aptitude, technical, and company tests"""
    user = current_user
    companies = Company.query.all()
    questions = Question.query.all()
    
    # Calculate stats
    total_available_questions = len(questions)
    
    return render_template(
        'assessments.html',
        user=user,
        companies=companies,
        total_questions=total_available_questions,
        questions=questions[:10]
    )


@main_bp.route('/api/assessments/start', methods=['POST'])
@login_required
def start_assessment_api():
    """API to generate a real question set for an assessment"""
    data = request.get_json() or {}
    company_id = data.get('company_id')
    question_type = data.get('question_type', 'all')
    difficulty = data.get('difficulty', 'all')
    count = int(data.get('count', 5))
    
    query = Question.query
    if company_id and str(company_id).isdigit():
        query = query.filter_by(company_id=int(company_id))
    if question_type and question_type != 'all':
        query = query.filter_by(question_type=question_type)
    if difficulty and difficulty != 'all':
        query = query.filter_by(difficulty_level=difficulty)
        
    questions = query.limit(min(count, 20)).all()
    
    if not questions:
        # Fallback to general questions if specific filter has no results
        questions = Question.query.limit(count).all()
        
    results = []
    for q in questions:
        results.append({
            'id': q.question_id,
            'type': q.question_type,
            'difficulty': q.difficulty_level,
            'question': q.question,
            'company': q.company.company_name if q.company else 'General',
            'has_answer': bool(q.answer)
        })
        
    return jsonify({
        'success': True,
        'count': len(results),
        'questions': results
    })


@main_bp.route('/courses')
@login_required
def courses():
    """Courses & Verified Learning Resources Hub"""
    user = current_user
    skill_filter = request.args.get('skill', '').strip()
    role_filter = request.args.get('role', '').strip()
    search_q = request.args.get('q', '').strip()
    
    # If skill_filter is provided and search_q is empty, populate search_q with skill_filter
    if not search_q and skill_filter:
        search_q = skill_filter
        
    search_lower = search_q.lower()
    
    # User's current enrollments
    enrollment_map = {e.skill_name.lower(): e for e in CourseEnrollment.query.filter_by(user_id=user.id).all()}
    
    # Build list of curated courses from SKILL_LEARNING_RESOURCES
    course_list = []
    for skill_name, res in SKILL_LEARNING_RESOURCES.items():
        if skill_filter and skill_filter.lower() != skill_name.lower():
            continue
        if search_lower and (search_lower not in skill_name.lower() and search_lower not in res['provider'].lower() and search_lower not in res['impact'].lower() and search_lower not in res['type'].lower()):
            continue
            
        enrollment = enrollment_map.get(skill_name.lower())
        
        course_list.append({
            'skill': skill_name,
            'title': f"Mastering {skill_name}: {res['type']}",
            'provider': res['provider'],
            'url': res['url'],
            'difficulty': res['difficulty'],
            'time': res['time'],
            'impact': res['impact'],
            'free': True,
            'enrollment': enrollment
        })
        
    all_skills = list(SKILL_LEARNING_RESOURCES.keys())
    
    return render_template(
        'courses.html',
        user=user,
        courses=course_list,
        all_skills=all_skills,
        skill_filter=skill_filter,
        search_q=search_q
    )


@main_bp.route('/api/courses/enroll', methods=['POST'])
@login_required
def enroll_course_api():
    """Enroll user in a learning resource"""
    data = request.get_json() or {}
    skill = data.get('skill', '').strip()
    title = data.get('title', '').strip()
    provider = data.get('provider', '').strip()
    url = data.get('url', '').strip()
    
    if not skill:
        return jsonify({'error': 'Skill name is required'}), 400
        
    # Check if already enrolled
    existing = CourseEnrollment.query.filter_by(user_id=current_user.id, skill_name=skill).first()
    if existing:
        return jsonify({
            'success': True,
            'message': 'Already enrolled',
            'enrollment_id': existing.id,
            'status': existing.status,
            'progress': existing.progress
        })
        
    new_enrollment = CourseEnrollment(
        user_id=current_user.id,
        skill_name=skill,
        course_title=title or f"Mastering {skill}",
        provider=provider or "Official Resource",
        url=url,
        status='enrolled',
        progress=0
    )
    db.session.add(new_enrollment)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'Successfully enrolled in {skill} track',
        'enrollment_id': new_enrollment.id,
        'status': new_enrollment.status,
        'progress': new_enrollment.progress
    })


@main_bp.route('/api/courses/update-progress', methods=['POST'])
@login_required
def update_course_progress_api():
    """Update progress / status for an enrolled course"""
    data = request.get_json() or {}
    enrollment_id = data.get('enrollment_id')
    status = data.get('status')
    progress = data.get('progress')
    
    if not enrollment_id:
        return jsonify({'error': 'Enrollment ID required'}), 400
        
    enrollment = CourseEnrollment.query.get(enrollment_id)
    if not enrollment or enrollment.user_id != current_user.id:
        return jsonify({'error': 'Enrollment not found'}), 404
        
    if status in ['enrolled', 'in_progress', 'completed']:
        enrollment.status = status
    if progress is not None and isinstance(progress, int) and 0 <= progress <= 100:
        enrollment.progress = progress
        if progress == 100:
            enrollment.status = 'completed'
        elif progress > 0 and enrollment.status == 'enrolled':
            enrollment.status = 'in_progress'
            
    db.session.commit()
    
    return jsonify({
        'success': True,
        'enrollment_id': enrollment.id,
        'status': enrollment.status,
        'progress': enrollment.progress
    })


@main_bp.route('/api/recommendations/feedback', methods=['POST'])
@login_required
def recommendation_feedback_api():
    """Record 'Not relevant' feedback for a job to filter it from future recommendations"""
    data = request.get_json() or {}
    company_id = data.get('company_id')
    reason = data.get('reason', 'Not interested')
    
    if not company_id:
        return jsonify({'error': 'Company ID required'}), 400
        
    # Check if feedback already exists
    existing = JobFeedback.query.filter_by(user_id=current_user.id, company_id=company_id).first()
    if existing:
        existing.reason = reason
        existing.created_at = datetime.utcnow()
    else:
        new_feedback = JobFeedback(
            user_id=current_user.id,
            company_id=company_id,
            reason=reason
        )
        db.session.add(new_feedback)
        
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Feedback received. Opportunity hidden from your recommendations.'
    })


@main_bp.route('/api/dashboard/data', methods=['GET'])
@login_required
def dashboard_data_api():
    """Async endpoint returning real dashboard intelligence data for instant refresh and retry"""
    user = current_user
    resumes = Resume.query.filter_by(user_id=user.id).order_by(Resume.uploaded_at.desc()).all()
    latest_resume = resumes[0] if resumes else None
    
    # 1. Recommendations
    rec_result = JobRecommendationEngine.get_recommendations(user, latest_resume, limit=4)
    serialized_recs = []
    for r in rec_result.get('recommendations', []):
        serialized_recs.append({
            'company_id': r['company_id'],
            'company_name': r['company_name'],
            'target_role': r['target_role'],
            'match_score': r['match_score'],
            'matching_skills': r['matching_skills'],
            'required_skills': r['required_skills'],
            'missing_skills': r['missing_skills'],
            'explanation': r['explanation'],
            'salary': r['salary'],
            'recommendation_source': r['recommendation_source']
        })
        
    # 2. Enrolled courses
    enrolled = CourseEnrollment.query.filter_by(user_id=user.id).order_by(CourseEnrollment.updated_at.desc()).all()
    serialized_courses = [{
        'id': c.id,
        'skill_name': c.skill_name,
        'course_title': c.course_title,
        'provider': c.provider,
        'url': c.url,
        'status': c.status,
        'progress': c.progress,
        'enrolled_at': c.enrolled_at.strftime('%b %d, %Y')
    } for c in enrolled]
    
    # 3. Latest ATS
    ats_info = {
        'has_resume': bool(latest_resume),
        'ats_score': latest_resume.ats_score if (latest_resume and latest_resume.ats_score is not None) else None,
        'uploaded_at': latest_resume.uploaded_at.strftime('%b %d, %Y') if latest_resume else None,
        'target_role': DOMAIN_MAPPING.get(user.domain, 'Full Stack Engineer')
    }
    
    return jsonify({
        'success': True,
        'recommendations': {
            'source': rec_result.get('source'),
            'source_label': rec_result.get('source_label'),
            'has_matches': rec_result.get('has_matches'),
            'has_inputs': rec_result.get('has_inputs'),
            'freshness': rec_result.get('freshness'),
            'items': serialized_recs
        },
        'learning': {
            'count': len(serialized_courses),
            'items': serialized_courses
        },
        'ats': ats_info
    })


@main_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """12. Profile - Personal Career Profile and Preferences"""
    user = current_user
    all_skills = Skill.query.order_by(Skill.skill_name).all()
    user_resumes = Resume.query.filter_by(user_id=user.id).order_by(Resume.uploaded_at.desc()).all()
    
    if request.method == 'POST':
        user.name = request.form.get('name', user.name).strip()
        user.phone = request.form.get('phone', user.phone).strip()
        user.user_type = request.form.get('user_type', user.user_type)
        user.college_name = request.form.get('college_name', user.college_name).strip()
        user.degree = request.form.get('degree', user.degree).strip()
        grad_year = request.form.get('graduation_year')
        user.graduation_year = int(grad_year) if grad_year and grad_year.isdigit() else user.graduation_year
        user.current_company = request.form.get('current_company', user.current_company).strip() or None
        user.domain = request.form.get('domain', user.domain)
        user.career_goal = request.form.get('career_goal', user.career_goal)
        
        # Update skills
        selected_skill_ids = request.form.getlist('skills')
        user.skills.clear()
        for sid in selected_skill_ids:
            if sid.isdigit():
                skill_obj = Skill.query.get(int(sid))
                if skill_obj:
                    user.skills.append(skill_obj)
                    
        db.session.commit()
        flash('Career profile updated successfully.', 'success')
        return redirect(url_for('main.profile'))
        
    profile_pct = calculate_profile_completeness(user)
    
    return render_template(
        'profile.html',
        user=user,
        all_skills=all_skills,
        resumes=user_resumes,
        profile_pct=profile_pct
    )
