import pytest
import os
from app import create_app
from app.extensions import db
from app.models.user import User
from app.models.company import Company
from app.models.question import Question

@pytest.fixture
def app():
    """Create and configure a test app instance"""
    app = create_app('testing')
    
    with app.app_context():
        db.session.expire_on_commit = False
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    """Test client for making requests"""
    return app.test_client()

@pytest.fixture
def runner(app):
    """CLI runner for testing CLI commands"""
    return app.test_cli_runner()

@pytest.fixture
def auth_user(app):
    """Create a test user for authentication tests"""
    with app.app_context():
        user = User(
            name='Test User',
            email='test@example.com',
            user_type='student'
        )
        user.set_password('testpassword123')
        db.session.add(user)
        db.session.commit()
        # Ensure fields are cached in object dict
        _ = (user.id, user.email, user.name, user.password_hash, user.user_type)
        db.session.expunge(user)
        return user

@pytest.fixture
def seeded_companies(app):
    """Seed test database with sample companies"""
    with app.app_context():
        companies_data = [
            {
                'name': 'Google',
                'description': 'Google is a multinational technology company.',
                'eligibility': 'B.Tech/B.E in CS. CGPA >= 7.0',
                'salary': '₹60-80 LPA',
                'selection_process': 'Online Assessment → Technical Interview → HR Interview'
            },
            {
                'name': 'TCS',
                'description': 'Tata Consultancy Services is an IT services company.',
                'eligibility': 'Any graduate with 60% aggregate.',
                'salary': '₹3.6-4.5 LPA',
                'selection_process': 'Online Assessment → Technical Interview → HR Interview'
            }
        ]
        
        companies = []
        for comp_data in companies_data:
            company = Company(
                company_name=comp_data['name'],
                description=comp_data['description'],
                eligibility=comp_data['eligibility'],
                salary=comp_data['salary'],
                selection_process=comp_data['selection_process']
            )
            db.session.add(company)
            db.session.flush()
            companies.append(company)
        
        db.session.commit()
        for c in companies:
            _ = (c.company_id, c.company_name, c.description, c.eligibility, c.salary, c.selection_process)
            db.session.expunge(c)
        return companies
