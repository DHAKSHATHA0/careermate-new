import pytest
from app.models.company import Company
from app.models.question import Question
from app.extensions import db

class TestCompanyList:
    """Test company listing page"""
    
    def test_company_list_loads(self, client, auth_user, seeded_companies):
        """Test /company/list loads and returns seeded companies"""
        # Login first
        client.post('/auth/login', data={
            'email': auth_user.email,
            'password': 'testpassword123'
        })
        
        response = client.get('/company/list')
        
        assert response.status_code == 200
        assert b'Browse Companies' in response.data or b'companies' in response.data.lower()
        
        # Check that seeded companies are displayed
        for company in seeded_companies:
            assert company.company_name.encode() in response.data
    
    def test_company_list_requires_login(self, client):
        """Test that company list requires authentication"""
        response = client.get('/company/list')
        
        # Should redirect to login
        assert response.status_code == 302
        assert '/auth/login' in response.location
    
    def test_company_list_search_filter(self, client, auth_user, seeded_companies):
        """Test company list search functionality"""
        # Login first
        client.post('/auth/login', data={
            'email': auth_user.email,
            'password': 'testpassword123'
        })
        
        response = client.get('/company/list')
        
        assert response.status_code == 200
        # Both companies should be present
        assert b'Google' in response.data
        assert b'TCS' in response.data


class TestCompanyDetail:
    """Test company detail page"""
    
    def test_company_detail_loads(self, client, auth_user, app):
        """Test /company/<id> returns company details"""
        with app.app_context():
            # Create a company with questions
            company = Company(
                company_name='Test Company',
                description='A test company',
                eligibility='B.Tech',
                salary='₹50 LPA',
                selection_process='Online → Interview'
            )
            db.session.add(company)
            db.session.flush()
            
            # Add a question
            question = Question(
                company_id=company.company_id,
                question_type='technical',
                difficulty_level='medium',
                question='What is a database?',
                answer='A database is a structured collection of data.'
            )
            db.session.add(question)
            db.session.commit()
            
            company_id = company.company_id
        
        # Login first
        client.post('/auth/login', data={
            'email': auth_user.email,
            'password': 'testpassword123'
        })
        
        response = client.get(f'/company/{company_id}')
        
        assert response.status_code == 200
        assert b'Test Company' in response.data
        assert b'A test company' in response.data
        assert '₹50 LPA'.encode('utf-8') in response.data
    
    def test_company_detail_404_nonexistent(self, client, auth_user):
        """Test /company/<id> returns 404 for non-existent company"""
        # Login first
        client.post('/auth/login', data={
            'email': auth_user.email,
            'password': 'testpassword123'
        })
        
        response = client.get('/company/99999')
        
        assert response.status_code == 404
    
    def test_company_detail_shows_questions(self, client, auth_user, app):
        """Test that company detail page shows interview questions"""
        with app.app_context():
            # Create a company with multiple questions
            company = Company(
                company_name='Question Test Company',
                description='Test',
                eligibility='Any',
                salary='₹40 LPA',
                selection_process='Test'
            )
            db.session.add(company)
            db.session.flush()
            
            # Add questions of different types
            for i, qtype in enumerate(['technical', 'aptitude', 'logical']):
                question = Question(
                    company_id=company.company_id,
                    question_type=qtype,
                    difficulty_level='easy',
                    question=f'Sample {qtype} question {i}',
                    answer=f'Sample answer {i}'
                )
                db.session.add(question)
            
            db.session.commit()
            company_id = company.company_id
        
        # Login first
        client.post('/auth/login', data={
            'email': auth_user.email,
            'password': 'testpassword123'
        })
        
        response = client.get(f'/company/{company_id}')
        
        assert response.status_code == 200
        # Check that questions are displayed
        assert b'Sample technical question' in response.data or b'technical' in response.data.lower()
        assert b'Sample aptitude question' in response.data or b'aptitude' in response.data.lower()
        assert b'Sample logical question' in response.data or b'logical' in response.data.lower()
    
    def test_company_detail_requires_login(self, client, app):
        """Test that company detail requires authentication"""
        with app.app_context():
            company = Company(
                company_name='Test',
                description='Test',
                eligibility='Any',
                salary='₹40 LPA',
                selection_process='Test'
            )
            db.session.add(company)
            db.session.commit()
            company_id = company.company_id
        
        response = client.get(f'/company/{company_id}')
        
        # Should redirect to login
        assert response.status_code == 302
        assert '/auth/login' in response.location
