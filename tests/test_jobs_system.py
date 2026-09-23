import pytest
from app.extensions import db
from app.models.user import User
from app.models.company import Company
from app.models.job import Job
from app.models.saved_job import SavedJob
from app.models.job_application import JobApplication
from app.models.skill import Skill
from app.services.ingestion.base_adapter import BaseJobAdapter
from app.services.ingestion.arbeitnow_adapter import ArbeitnowAdapter
from app.services.ingestion.remotive_adapter import RemotiveAdapter
from app.services.ingestion.greenhouse_adapter import GreenhouseAdapter
from app.services.ingestion.service import IngestionService
from app.utils.recommendations import JobRecommendationEngine

def login_user(client, email='test@example.com', password='testpassword123'):
    return client.post('/auth/login', data={'email': email, 'password': password}, follow_redirects=True)

class TestJobModelsAndCareerAreas:
    """Test Job, Company, and dynamic Career Area derivation."""
    
    def test_company_slug_and_dynamic_career_areas(self, app):
        with app.app_context():
            comp = Company(company_name='Stripe Inc', industry='Fintech & Payments')
            db.session.add(comp)
            db.session.flush()
            
            assert comp.slug == 'stripe-inc'
            assert comp.career_areas == []
            
            # Add jobs in multiple career areas
            j1 = Job(
                company_id=comp.company_id,
                title='Senior Backend Engineer',
                career_area='Software Engineering',
                application_url='https://stripe.com/jobs/1'
            )
            j2 = Job(
                company_id=comp.company_id,
                title='Data Scientist - Risk',
                career_area='Data Analytics',
                application_url='https://stripe.com/jobs/2'
            )
            db.session.add_all([j1, j2])
            db.session.commit()
            
            assert 'Software Engineering' in comp.career_areas
            assert 'Data Analytics' in comp.career_areas
            assert comp.active_jobs_count == 2

    def test_job_skills_and_salary_properties(self, app):
        with app.app_context():
            comp = Company(company_name='Figma Inc')
            db.session.add(comp)
            db.session.flush()
            
            job = Job(
                company_id=comp.company_id,
                title='Frontend Systems Engineer',
                salary_min=140000,
                salary_max=180000,
                currency='USD',
                experience_min=3,
                experience_max=5,
                application_url='https://figma.com/jobs/1'
            )
            job.skills = ['React', 'TypeScript', 'WebAssembly']
            db.session.add(job)
            db.session.commit()
            
            assert 'React' in job.skills
            assert job.salary_display == 'USD 140,000 - 180,000'
            assert job.experience_display == '3-5 yrs'
            assert 'Verified' in job.freshness_label


class TestIngestionAdapters:
    """Test modular ingestion adapters and skill normalization."""
    
    def test_base_adapter_skill_normalization_and_inference(self):
        adapter = ArbeitnowAdapter()
        text = "We are seeking a Python and ReactJS developer with experience in PostgreSQL, Docker, and ML algorithms."
        skills = adapter.extract_and_normalize_skills(text, tags=['js', 'k8s'])
        
        assert 'Python' in skills
        assert 'React' in skills
        assert 'PostgreSQL' in skills
        assert 'Docker' in skills
        assert 'Machine Learning' in skills
        assert 'JavaScript' in skills
        assert 'Kubernetes' in skills
        
        area = adapter.infer_career_area('Senior Machine Learning Engineer', 'Deep learning and NLP')
        assert area == 'AI / Machine Learning'
        
        data_area = adapter.infer_career_area('Business Intelligence Data Analyst', 'SQL and Tableau')
        assert data_area == 'Data Analytics'

    def test_adapter_normalization_schemas(self):
        arb = ArbeitnowAdapter()
        norm_arb = arb.normalize_job({
            'slug': 'test-dev-123',
            'title': 'Senior Python Backend Developer',
            'company_name': 'Test Tech Corp',
            'description': '<p>We need Python and Docker expertise.</p>',
            'location': 'Berlin, Germany',
            'remote': True,
            'url': 'https://example.com/apply'
        })
        assert norm_arb['company']['name'] == 'Test Tech Corp'
        assert norm_arb['job']['career_area'] == 'Software Engineering'
        assert 'Python' in norm_arb['job']['skills']
        assert norm_arb['job']['work_mode'] == 'Remote'


class TestJobsRoutesAndWorkflow:
    """Test Jobs page, search, filtering, detail, save, and application tracking."""
    
    def test_jobs_page_renders_with_real_jobs(self, client, auth_user, app):
        with app.app_context():
            comp = Company(company_name='Linear Orbit', industry='Software')
            db.session.add(comp)
            db.session.flush()
            
            job = Job(
                company_id=comp.company_id,
                title='Systems Infrastructure Engineer',
                career_area='Cloud & DevOps',
                location='Remote',
                work_mode='Remote',
                employment_type='Full-time',
                application_url='https://linear.app/careers'
            )
            job.skills = ['Kubernetes', 'Go', 'AWS']
            db.session.add(job)
            db.session.commit()
            
        login_user(client)
        res = client.get('/jobs')
        assert res.status_code == 200
        assert b"Find where your skills can take you." in res.data
        assert b"Linear Orbit" in res.data
        assert b"Systems Infrastructure Engineer" in res.data

    def test_jobs_search_and_career_area_filter(self, client, auth_user, app):
        with app.app_context():
            comp = Company(company_name='Vercel Inc')
            db.session.add(comp)
            db.session.flush()
            
            j1 = Job(
                company_id=comp.company_id,
                title='Frontend Next.js Architect',
                career_area='Software Engineering',
                application_url='https://vercel.com/1'
            )
            j2 = Job(
                company_id=comp.company_id,
                title='Security Operations Analyst',
                career_area='Cybersecurity',
                application_url='https://vercel.com/2'
            )
            db.session.add_all([j1, j2])
            db.session.commit()
            
        login_user(client)
        
        # Search query filter
        res_search = client.get('/jobs?q=Next.js')
        assert res_search.status_code == 200
        assert b"Frontend Next.js Architect" in res_search.data
        assert b"Security Operations Analyst" not in res_search.data
        
        # Category filter
        res_cat = client.get('/jobs?role=Cybersecurity')
        assert res_cat.status_code == 200
        assert b"Security Operations Analyst" in res_cat.data

    def test_job_detail_and_save_workflow(self, client, auth_user, app):
        with app.app_context():
            comp = Company(company_name='OpenAI', industry='Artificial Intelligence')
            db.session.add(comp)
            db.session.flush()
            
            job = Job(
                company_id=comp.company_id,
                title='Research Engineer - Alignment',
                career_area='AI / Machine Learning',
                description='Researching foundation models and scalable oversight.',
                application_url='https://openai.com/careers/research-eng'
            )
            job.skills = ['PyTorch', 'Python', 'Machine Learning']
            db.session.add(job)
            db.session.commit()
            job_id = job.id
            
        login_user(client)
        
        # 1. View Job Detail
        res = client.get(f'/jobs/{job_id}')
        assert res.status_code == 200
        assert b"Research Engineer - Alignment" in res.data
        assert b"OpenAI" in res.data
        assert b"Verified Source" in res.data
        
        # 2. Toggle Save Job
        save_res = client.post(f'/api/jobs/{job_id}/save')
        assert save_res.status_code == 200
        assert save_res.get_json()['saved'] is True
        
        # Toggle Unsave
        unsave_res = client.post(f'/api/jobs/{job_id}/save')
        assert unsave_res.status_code == 200
        assert unsave_res.get_json()['saved'] is False

    def test_application_tracker_lifecycle(self, client, auth_user, app):
        with app.app_context():
            comp = Company(company_name='Datadog')
            db.session.add(comp)
            db.session.flush()
            
            job = Job(
                company_id=comp.company_id,
                title='Site Reliability Engineer',
                application_url='https://datadoghq.com/careers'
            )
            db.session.add(job)
            db.session.commit()
            job_id = job.id
            
        login_user(client)
        
        # 1. "I Applied" action
        apply_res = client.post(f'/api/jobs/{job_id}/apply', json={'notes': 'Applied via official career link'})
        assert apply_res.status_code == 200
        assert apply_res.get_json()['status'] == 'Applied'
        
        # 2. Fetch applications
        list_res = client.get('/api/applications')
        assert list_res.status_code == 200
        data = list_res.get_json()
        assert data['count'] >= 1
        app_item = data['applications'][0]
        assert app_item['company_name'] == 'Datadog'
        
        # 3. Update status to Interview
        update_res = client.post('/api/applications/update', json={
            'id': app_item['id'],
            'status': 'Interview',
            'notes': 'Technical screening scheduled'
        })
        assert update_res.status_code == 200
        assert update_res.get_json()['status'] == 'Interview'

    def test_job_fit_integration_and_missing_skills(self, client, auth_user, app):
        with app.app_context():
            u = db.session.get(User, auth_user.id)
            s_python = Skill(skill_name='Python')
            s_sql = Skill(skill_name='SQL')
            db.session.add_all([s_python, s_sql])
            u.skills.extend([s_python, s_sql])
            
            comp = Company(company_name='Snowflake')
            db.session.add(comp)
            db.session.flush()
            
            job = Job(
                company_id=comp.company_id,
                title='Data Platform Engineer',
                career_area='Data Analytics',
                description='Required skills: Python, SQL, Docker, Kubernetes.',
                application_url='https://snowflake.com/careers'
            )
            job.skills = ['Python', 'SQL', 'Docker', 'Kubernetes']
            db.session.add(job)
            db.session.commit()
            job_id = job.id
            
        login_user(client)
        res = client.get(f'/job-fit?job_id={job_id}')
        assert res.status_code == 200
        assert b"Data Platform Engineer" in res.data
        assert b"Python" in res.data
        # Missing skills should be displayed with links to courses
        assert b"courses?q=" in res.data
