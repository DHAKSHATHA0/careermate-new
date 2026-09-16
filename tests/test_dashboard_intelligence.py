import pytest
from app.extensions import db
from app.models.user import User
from app.models.skill import Skill
from app.models.company import Company
from app.models.enrollment import CourseEnrollment
from app.models.job_feedback import JobFeedback
from app.models.job_analysis import JobAnalysis
from app.utils.recommendations import JobRecommendationEngine

def login_user(client, email='test@example.com', password='testpassword123'):
    return client.post('/auth/login', data={'email': email, 'password': password}, follow_redirects=True)

def test_recommendation_engine_no_inputs(app):
    """Test recommendation engine with empty profile and no resume"""
    with app.app_context():
        user = User(name='Test User', email='empty@example.com', user_type='student')
        recs = JobRecommendationEngine.get_recommendations(user, None)
        assert recs['source'] == 'insufficient_data'
        assert recs['has_matches'] is False
        assert recs['recommendations'] == []

def test_recommendation_engine_profile_matching(app, auth_user):
    """Test recommendation engine with profile skills and company database"""
    with app.app_context():
        u = db.session.get(User, auth_user.id)
        u.domain = 'web_dev'
        s1 = Skill(skill_name='Python')
        s2 = Skill(skill_name='React')
        db.session.add_all([s1, s2])
        u.skills.extend([s1, s2])
        
        comp = Company(
            company_name='Acme Web Tech',
            description='Building full stack React and Python applications',
            eligibility='B.Tech CS'
        )
        db.session.add(comp)
        db.session.commit()
        
        recs = JobRecommendationEngine.get_recommendations(u, None)
        assert recs['has_matches'] is True
        assert len(recs['recommendations']) > 0
        top = recs['recommendations'][0]
        assert top['company_name'] == 'Acme Web Tech'
        assert 'Python' in top['matching_skills'] or 'React' in top['matching_skills']
        assert top['recommendation_source'] == 'Based on your profile'

def test_job_feedback_filtering(app, auth_user):
    """Test that jobs marked 'Not relevant' are filtered out for that user"""
    with app.app_context():
        u = db.session.get(User, auth_user.id)
        comp = Company(
            company_name='Hidden Tech',
            description='Test description'
        )
        db.session.add(comp)
        db.session.commit()
        
        feedback = JobFeedback(user_id=u.id, company_id=comp.company_id, reason='Wrong role')
        db.session.add(feedback)
        db.session.commit()
        
        recs = JobRecommendationEngine.get_recommendations(u, None)
        comp_ids = [r['company_id'] for r in recs['recommendations']]
        assert comp.company_id not in comp_ids

def test_course_enrollment_workflow(client, auth_user):
    """Test course enrollment API and status updating"""
    login_user(client)
    res = client.post('/api/courses/enroll', json={
        'skill': 'Python',
        'title': 'Mastering Python',
        'provider': 'PSF',
        'url': 'https://docs.python.org/3/'
    })
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    enrollment_id = data['enrollment_id']
    
    # Update progress
    prog_res = client.post('/api/courses/update-progress', json={
        'enrollment_id': enrollment_id,
        'status': 'in_progress',
        'progress': 50
    })
    assert prog_res.status_code == 200
    assert prog_res.get_json()['status'] == 'in_progress'

def test_dashboard_renders_for_logged_in_user(client, auth_user):
    """Test that dashboard renders successfully with HTTP 200 and required intelligence blocks"""
    login_user(client)
    res = client.get('/dashboard')
    assert res.status_code == 200
    assert b"RECOMMENDED JOBS" in res.data
    assert b"BUILD YOUR MISSING SKILLS" in res.data
    assert b"Latest ATS Resume Score" in res.data
    assert b"Your Learning" in res.data
    assert b"Your Next Best Move" in res.data
    assert b"Ask CareerMate AI" in res.data
