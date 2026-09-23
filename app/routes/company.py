from flask import Blueprint, render_template, request, abort, redirect, url_for
from flask_login import login_required, current_user
from app.extensions import db
from app.models.company import Company
from app.models.job import Job
from app.models.question import Question
from app.models.resume import Resume
from app.utils.recommendations import JobRecommendationEngine

company_bp = Blueprint('company', __name__, url_prefix='/company')

@company_bp.route('', endpoint='list')
@company_bp.route('/list', endpoint='list')
@login_required
def company_list():
    """Verified Company Directory"""
    search_q = request.args.get('q', '').strip()
    industry_filter = request.args.get('industry', '').strip()
    
    query = Company.query
    if search_q:
        search_term = f"%{search_q}%"
        query = query.filter(
            (Company.company_name.ilike(search_term)) |
            (Company.description.ilike(search_term))
        )
    if industry_filter:
        query = query.filter(Company.industry.ilike(f"%{industry_filter}%"))
        
    companies = query.order_by(Company.company_name.asc()).all()
    
    all_comps = Company.query.all()
    industries = sorted(list(set(c.industry for c in all_comps if getattr(c, 'industry', None))))
    
    return render_template(
        'company/list.html',
        companies=companies,
        search_q=search_q,
        industry_filter=industry_filter,
        industries=industries
    )

@company_bp.route('/<company_id>', endpoint='detail')
@login_required
def detail(company_id):
    """
    Dedicated Company Page.
    Supports either integer company_id or company slug.
    """
    company = None
    identifier_str = str(company_id)
    if identifier_str.isdigit():
        company = db.session.get(Company, int(identifier_str))
    if not company:
        company = Company.query.filter_by(slug=identifier_str).first()
    if not company:
        company = Company.query.filter(Company.company_name.ilike(identifier_str.replace('-', ' '))).first()
    if not company:
        abort(404)
        
    selected_category = request.args.get('category', '').strip()
    
    # Real active jobs for this company
    jobs_query = Job.query.filter_by(company_id=company.company_id, status='active')
    if selected_category:
        jobs_query = jobs_query.filter_by(career_area=selected_category)
    openings = jobs_query.order_by(Job.posted_at.desc()).all()
    
    # Dynamically derived career areas from actual jobs
    all_company_jobs = Job.query.filter_by(company_id=company.company_id, status='active').all()
    career_areas_map = {}
    for j in all_company_jobs:
        area = j.career_area or 'Software Engineering'
        career_areas_map[area] = career_areas_map.get(area, 0) + 1
        
    # Personalized role recommendations within this company
    resumes = Resume.query.filter_by(user_id=current_user.id).order_by(Resume.uploaded_at.desc()).all()
    latest_resume = resumes[0] if resumes else None
    
    candidate_rep = JobRecommendationEngine.get_candidate_representation(current_user, latest_resume)
    has_profile_or_resume = candidate_rep['has_profile'] or candidate_rep['has_resume']
    
    personalized_matches = []
    if has_profile_or_resume:
        personalized_matches = JobRecommendationEngine.get_company_role_matches(
            current_user, company.company_id, latest_resume
        )[:3]
        
    # Practice questions for backward compatibility and interview prep
    questions = Question.query.filter_by(company_id=company.company_id).all()
    questions_by_type = {}
    for question in questions:
        if question.question_type not in questions_by_type:
            questions_by_type[question.question_type] = []
        questions_by_type[question.question_type].append(question)
        
    return render_template(
        'company/detail.html',
        company=company,
        openings=openings,
        career_areas=career_areas_map,
        selected_category=selected_category,
        personalized_matches=personalized_matches,
        has_profile_or_resume=has_profile_or_resume,
        questions_by_type=questions_by_type
    )
