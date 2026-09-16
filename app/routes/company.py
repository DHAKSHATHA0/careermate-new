from flask import Blueprint, render_template, abort
from flask_login import login_required
from app.models.company import Company
from app.models.question import Question

company_bp = Blueprint('company', __name__, url_prefix='/company')

@company_bp.route('/list')
@login_required
def list():
    """Company list page"""
    companies = Company.query.all()
    return render_template('company/list.html', companies=companies)

@company_bp.route('/<int:company_id>')
@login_required
def detail(company_id):
    """Company detail page"""
    company = Company.query.get_or_404(company_id)
    questions = Question.query.filter_by(company_id=company_id).all()
    
    # Group questions by type
    questions_by_type = {}
    for question in questions:
        if question.question_type not in questions_by_type:
            questions_by_type[question.question_type] = []
        questions_by_type[question.question_type].append(question)
    
    return render_template('company/detail.html', company=company, questions_by_type=questions_by_type)
