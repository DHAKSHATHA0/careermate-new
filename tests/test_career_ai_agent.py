import pytest
import json
import io
import os
from PIL import Image, ImageDraw
from app.extensions import db
from app.models.user import User
from app.models.resume import Resume
from app.models.job import Job
from app.models.company import Company
from app.models.job_application import JobApplication
from app.models.saved_job import SavedJob
from app.models.enrollment import CourseEnrollment
from app.models.skill import Skill
from app.models.question import Question
from app.models.conversation import Conversation, ConversationMessage
from app.services.career_tools import CareerTools
from app.services.career_agent import CareerMateAgent
from app.services.image_intelligence import ImageIntelligence


@pytest.fixture
def agent_test_data(app):
    """Seed comprehensive user data for User A and User B to test isolation and intelligence."""
    with app.app_context():
        # 1. User A (Rich profile)
        user_a = User(
            name='Alice Wonderland',
            email='alice@example.com',
            user_type='student',
            domain='web_dev',
            college_name='Tech Institute of California',
            degree='B.S. in Computer Science',
            graduation_start_year=2022,
            graduation_year=2026,
            career_goal='placement_prep'
        )
        user_a.set_password('alicepassword123')
        db.session.add(user_a)
        db.session.flush()

        # Skills for User A
        skill_python = Skill.query.filter_by(skill_name='Python').first() or Skill(skill_name='Python')
        skill_js = Skill.query.filter_by(skill_name='JavaScript').first() or Skill(skill_name='JavaScript')
        skill_react = Skill.query.filter_by(skill_name='React').first() or Skill(skill_name='React')
        db.session.add_all([skill_python, skill_js, skill_react])
        db.session.flush()
        user_a.skills.extend([skill_python, skill_js, skill_react])

        # Resume for User A
        resume_a = Resume(
            user_id=user_a.id,
            file_path='instance/uploads/sample_resume_alice.pdf',
            ats_score=82
        )
        db.session.add(resume_a)

        # Company & Jobs
        company_google = Company(
            company_name='Google',
            industry='Technology',
            description='Global internet and technology company.',
            salary='₹35-50 LPA',
            eligibility='CS / IT degree with 70% aggregate',
            selection_process='Online Assessment -> Technical Interview 1 -> Technical Interview 2 -> Googliness'
        )
        company_tcs = Company(
            company_name='TCS',
            industry='IT Services',
            description='Enterprise IT services leader.',
            salary='₹4.5-7 LPA',
            eligibility='Any graduate with 60%'
        )
        db.session.add_all([company_google, company_tcs])
        db.session.flush()

        job_da = Job(
            company_id=company_google.company_id,
            title='Data Analyst',
            career_area='Data Science',
            location='Mountain View, CA / Remote',
            status='active',
            application_url='https://careers.google.com/jobs/results/12345'
        )
        job_da.skills = ['Python', 'SQL', 'Pandas', 'Power BI']

        job_swe = Job(
            company_id=company_google.company_id,
            title='Full Stack Software Engineer',
            career_area='Software Engineering',
            location='Sunnyvale, CA',
            status='active',
            application_url='https://careers.google.com/jobs/results/67890'
        )
        job_swe.skills = ['Python', 'JavaScript', 'React', 'Docker']

        db.session.add_all([job_da, job_swe])
        db.session.flush()

        # Job Applications for User A
        app_google = JobApplication(
            user_id=user_a.id,
            job_id=job_swe.id,
            company_id=company_google.company_id,
            company_name='Google',
            job_title='Full Stack Software Engineer',
            status='Interview',
            notes='Interviewer praised system design fundamentals; requested deeper concurrency mastery.'
        )
        app_tcs = JobApplication(
            user_id=user_a.id,
            company_name='TCS',
            job_title='Software Developer',
            status='Applied'
        )
        db.session.add_all([app_google, app_tcs])

        # Saved Job for User A
        saved_job = SavedJob(user_id=user_a.id, job_id=job_da.id)
        db.session.add(saved_job)

        # Course Enrollment for User A
        enrollment = CourseEnrollment(
            user_id=user_a.id,
            skill_name='Docker',
            course_title='Mastering Docker: Hands-on Labs',
            provider='Docker Official Docs',
            url='https://docs.docker.com/get-started/',
            status='in_progress',
            progress=40
        )
        db.session.add(enrollment)

        # Questions in bank
        q1 = Question(
            company_id=company_google.company_id,
            question_type='technical',
            difficulty_level='medium',
            question='Explain the difference between process and thread.',
            answer='Processes have separate address space, threads share memory within process.'
        )
        q2 = Question(
            company_id=company_google.company_id,
            question_type='aptitude',
            difficulty_level='easy',
            question='A train travelling at 60 km/h crosses a pole in 9 seconds. Length of train?',
            answer='150 meters'
        )
        db.session.add_all([q1, q2])

        # 2. User B (Empty/Isolated Profile)
        user_b = User(
            name='Bob Builder',
            email='bob@example.com',
            user_type='fresher'
        )
        user_b.set_password('bobpassword123')
        db.session.add(user_b)

        db.session.commit()

        user_a_id = user_a.id
        user_b_id = user_b.id

        return {
            'user_a_id': user_a_id,
            'user_b_id': user_b_id,
            'job_swe_id': job_swe.id,
            'job_da_id': job_da.id,
            'company_google_id': company_google.company_id
        }


def test_user_profile_tool(app, agent_test_data):
    """1. Test get_user_profile returns genuine structured profile."""
    with app.app_context():
        user_a_id = agent_test_data['user_a_id']
        prof = CareerTools.get_user_profile(user_a_id)

        assert prof['found'] is True
        assert prof['name'] == 'Alice Wonderland'
        assert prof['degree'] == 'B.S. in Computer Science'
        assert 'Python' in prof['skills']
        assert 'JavaScript' in prof['skills']
        assert prof['target_role'] == 'Full Stack Engineer'


def test_resume_summary_tool_and_no_resume(app, agent_test_data):
    """2 & 15. Test get_resume_summary for present vs missing resume."""
    with app.app_context():
        # User A has resume
        res_a = CareerTools.get_resume_summary(agent_test_data['user_a_id'])
        assert res_a['resume_available'] is True
        assert res_a['ats_score'] == 82
        assert 'sample_resume_alice.pdf' in res_a['filename']

        # User B has no resume
        res_b = CareerTools.get_resume_summary(agent_test_data['user_b_id'])
        assert res_b['resume_available'] is False
        assert 'No resume uploaded' in res_b['message']


def test_application_statistics(app, agent_test_data):
    """3. Test get_application_statistics returns exact DB counts."""
    with app.app_context():
        stats_a = CareerTools.get_application_statistics(agent_test_data['user_a_id'])
        assert stats_a['total_applications'] == 2
        assert stats_a['breakdown']['interview'] == 1
        assert stats_a['breakdown']['applied'] == 1

        stats_b = CareerTools.get_application_statistics(agent_test_data['user_b_id'])
        assert stats_b['total_applications'] == 0


def test_user_applications_filtered(app, agent_test_data):
    """4. Test get_user_applications filtering by company and status."""
    with app.app_context():
        user_a_id = agent_test_data['user_a_id']
        all_apps = CareerTools.get_user_applications(user_a_id)
        assert all_apps['count'] == 2

        google_apps = CareerTools.get_user_applications(user_a_id, company='Google')
        assert google_apps['count'] == 1
        assert google_apps['applications'][0]['company_name'] == 'Google'
        assert google_apps['applications'][0]['status'] == 'Interview'


def test_saved_jobs_tool(app, agent_test_data):
    """5. Test get_saved_jobs returns user's actual saved jobs."""
    with app.app_context():
        saved = CareerTools.get_saved_jobs(agent_test_data['user_a_id'])
        assert saved['count'] == 1
        assert saved['saved_jobs'][0]['title'] == 'Data Analyst'

        saved_b = CareerTools.get_saved_jobs(agent_test_data['user_b_id'])
        assert saved_b['count'] == 0


def test_matching_jobs_engine(app, agent_test_data):
    """6. Test get_matching_jobs returns scored recommendations."""
    with app.app_context():
        matches = CareerTools.get_matching_jobs(agent_test_data['user_a_id'])
        assert matches['found'] is True
        assert len(matches['recommendations']) > 0
        top = matches['recommendations'][0]
        assert top['match_score'] > 0
        assert top['title'] is not None


def test_job_fit_analysis(app, agent_test_data):
    """7. Test analyze_job_fit against active job."""
    with app.app_context():
        user_a_id = agent_test_data['user_a_id']
        job_id = agent_test_data['job_swe_id']
        fit = CareerTools.analyze_job_fit(user_a_id, job_id=job_id)

        assert fit['target_type'] == 'job'
        assert fit['company_name'] == 'Google'
        assert 'Python' in fit['matching_skills'] or 'JavaScript' in fit['matching_skills']
        assert fit['overall_score'] > 0


def test_missing_skills_tool(app, agent_test_data):
    """8 & 14. Test get_missing_skills identifies true gaps."""
    with app.app_context():
        user_a_id = agent_test_data['user_a_id']
        # User A possesses Python, JavaScript, React. Missing Docker, SQL, etc.
        gaps = CareerTools.get_missing_skills(user_a_id, role='Full Stack Engineer')
        assert 'Python' in gaps['matching_skills']
        assert 'SQL' in gaps['missing_skills'] or 'Docker' in gaps['missing_skills']


def test_recommended_courses_tool(app, agent_test_data):
    """9 & 13. Test get_recommended_courses maps to genuine learning resources."""
    with app.app_context():
        courses = CareerTools.get_recommended_courses(agent_test_data['user_a_id'], skills=['SQL', 'Docker'])
        assert courses['count'] >= 1
        skills_found = [c['skill'] for c in courses['recommended_courses']]
        assert 'SQL' in skills_found or 'Docker' in skills_found


def test_course_progress_tool(app, agent_test_data):
    """10. Test get_course_progress returns actual enrollment metrics."""
    with app.app_context():
        prog = CareerTools.get_course_progress(agent_test_data['user_a_id'])
        assert prog['total_enrolled'] == 1
        assert prog['courses'][0]['skill_name'] == 'Docker'
        assert prog['courses'][0]['progress'] == 40


def test_interview_feedback_tool_present_and_absent(app, agent_test_data):
    """11 & 17. Test get_latest_interview_feedback for presence and absence."""
    with app.app_context():
        # User A has feedback notes on Google interview
        fb_a = CareerTools.get_latest_interview_feedback(agent_test_data['user_a_id'])
        assert fb_a['has_feedback'] is True
        assert 'concurrency' in fb_a['feedback_notes'].lower()

        # User B has no feedback
        fb_b = CareerTools.get_latest_interview_feedback(agent_test_data['user_b_id'])
        assert fb_b['has_feedback'] is False
        assert "don't have recorded interview feedback" in fb_b['message']


def test_company_roles_tool(app, agent_test_data):
    """12. Test get_company_roles returns active jobs and career areas."""
    with app.app_context():
        comp_info = CareerTools.get_company_roles(company_name='Google')
        assert comp_info['found'] is True
        assert comp_info['company_name'] == 'Google'
        assert comp_info['active_jobs_count'] == 2
        assert len(comp_info['career_areas']) >= 1


def test_career_roadmap_tool(app, agent_test_data):
    """13. Test get_career_roadmap constructs multi-dimensional roadmap."""
    with app.app_context():
        rm = CareerTools.get_career_roadmap(agent_test_data['user_a_id'], target_role='Full Stack Engineer')
        assert rm['target_role'] == 'Full Stack Engineer'
        assert rm['current_position']['name'] == 'Alice Wonderland'
        assert len(rm['skill_gaps']) > 0


def test_next_best_actions_tool(app, agent_test_data):
    """14 & 16. Test get_next_best_actions prioritizes real actions."""
    with app.app_context():
        actions_a = CareerTools.get_next_best_actions(agent_test_data['user_a_id'])
        assert actions_a['count'] > 0
        titles = [a['title'] for a in actions_a['actions']]
        assert any('Docker' in t or 'Learning' in t or 'Profile' in t for t in titles)


def test_agent_strict_user_isolation_security(app, agent_test_data):
    """19. CRITICAL SECURITY TEST: Verify User B cannot access User A's data through agent."""
    with app.app_context():
        agent = CareerMateAgent()
        user_a = db.session.get(User, agent_test_data['user_a_id'])
        user_b = db.session.get(User, agent_test_data['user_b_id'])

        # User B asks for application stats
        res_b_apps = agent.process_message(user_b, "How many jobs have I applied for?")
        assert "Total Applications Tracked**: **0**" in res_b_apps['response']
        assert "Google" not in res_b_apps['response']

        # User B asks for resume
        res_b_resume = agent.process_message(user_b, "What is my ATS score?")
        assert "haven't uploaded a resume yet" in res_b_resume['response']

        # User B asks for interview feedback
        res_b_interview = agent.process_message(user_b, "What did my interview feedback say?")
        assert "don't have recorded interview feedback" in res_b_interview['response']
        assert "concurrency" not in res_b_interview['response']


def test_agent_conversational_context(app, agent_test_data):
    """22. Test multi-turn conversational context tracking."""
    with app.app_context():
        agent = CareerMateAgent()
        user_a = db.session.get(User, agent_test_data['user_a_id'])

        # Turn 1: User asks about Google
        history = [
            {'message': "Tell me about Google", 'response': "Google is a leading tech company with Data Analyst and Software Engineer roles."}
        ]

        # Turn 2: User asks follow up "How many applications did I make for them?"
        res2 = agent.process_message(user_a, "How many applications did I make for them?", history=history)
        assert res2['intent'] == 'USER_APPLICATIONS'
        assert "Google" in res2['response']


# ==========================================
# FULL-PAGE CONVERSATION REST API TESTS
# ==========================================

def test_conversations_crud_and_search(client, auth_user, app):
    """Test Conversation creation, listing, searching, renaming, and deleting."""
    # Log in
    client.post('/auth/login', data={'email': auth_user.email, 'password': 'testpassword123'}, follow_redirects=True)

    # 1. Create conversation
    res = client.post('/api/assistant/conversations', json={'title': 'Data Science Roadmap Chat'})
    assert res.status_code == 201
    conv_data = res.get_json()['conversation']
    conv_id = conv_data['id']
    assert conv_data['title'] == 'Data Science Roadmap Chat'

    # 2. List conversations
    res_list = client.get('/api/assistant/conversations')
    assert res_list.status_code == 200
    list_json = res_list.get_json()
    assert list_json['total'] >= 1
    assert any(c['id'] == conv_id for c in list_json['conversations'])

    # 3. Search conversation
    res_search = client.get('/api/assistant/conversations?q=Roadmap')
    assert res_search.status_code == 200
    assert len(res_search.get_json()['conversations']) >= 1

    # 4. Rename conversation
    res_patch = client.patch(f'/api/assistant/conversations/{conv_id}', json={'title': 'Renamed Roadmap'})
    assert res_patch.status_code == 200
    assert res_patch.get_json()['conversation']['title'] == 'Renamed Roadmap'

    # 5. Send message into conversation
    res_msg = client.post(f'/api/assistant/conversations/{conv_id}/messages', json={'content': 'What is my current career status?'})
    assert res_msg.status_code == 200
    msg_json = res_msg.get_json()
    assert 'Career Status' in msg_json['assistant_message']['content'] or 'CareerMate' in msg_json['assistant_message']['content']

    # 6. Retrieve thread
    res_thread = client.get(f'/api/assistant/conversations/{conv_id}')
    assert res_thread.status_code == 200
    assert len(res_thread.get_json()['messages']) == 2

    # 7. Delete conversation
    res_del = client.delete(f'/api/assistant/conversations/{conv_id}')
    assert res_del.status_code == 200
    assert res_del.get_json()['success'] is True


def test_conversation_user_isolation(client, app, agent_test_data):
    """Test User B cannot access or modify User A's conversation thread."""
    with app.app_context():
        # Create conversation for User A
        conv_a = Conversation(user_id=agent_test_data['user_a_id'], title="User A Confidential Chat")
        db.session.add(conv_a)
        db.session.commit()
        conv_a_id = conv_a.id

    # Log in as User B (bob@example.com)
    client.post('/auth/login', data={'email': 'bob@example.com', 'password': 'bobpassword123'}, follow_redirects=True)

    # User B attempts to read User A's conversation
    res_get = client.get(f'/api/assistant/conversations/{conv_a_id}')
    assert res_get.status_code == 404

    # User B attempts to rename User A's conversation
    res_patch = client.patch(f'/api/assistant/conversations/{conv_a_id}', json={'title': 'Hacked Title'})
    assert res_patch.status_code == 404

    # User B attempts to delete User A's conversation
    res_delete = client.delete(f'/api/assistant/conversations/{conv_a_id}')
    assert res_delete.status_code == 404


def test_image_intelligence_extraction(app, agent_test_data):
    """Test image classification and career entity extraction."""
    with app.app_context():
        user_a_id = agent_test_data['user_a_id']
        sample_jd_text = """
        Google Data Analyst Role
        Responsibilities: Build scalable data models and dashboards.
        Requirements: Python, SQL, Power BI, Statistics.
        """
        extracted = ImageIntelligence.classify_and_extract_career_data(sample_jd_text, user_a_id)

        assert extracted['doc_type'] == 'job_description'
        assert 'Python' in extracted['extracted_skills']
        assert 'SQL' in extracted['extracted_skills']
        assert 'Power BI' in extracted['extracted_skills'] or 'Statistics' in extracted['extracted_skills']
        # User A already has Python in profile
        assert 'Python' in extracted['matching_skills']
        # User A lacks Power BI
        assert 'Power BI' in extracted['missing_skills']


def test_voice_and_audio_endpoints(client, auth_user):
    """Test transcribe and speak endpoints."""
    client.post('/auth/login', data={'email': auth_user.email, 'password': 'testpassword123'}, follow_redirects=True)

    res_transcribe = client.post('/api/assistant/transcribe', json={'text': 'Show my matching jobs'})
    assert res_transcribe.status_code == 200
    assert res_transcribe.get_json()['transcript'] == 'Show my matching jobs'

    res_speak = client.post('/api/assistant/speak', json={'text': 'Here are your top jobs.'})
    assert res_speak.status_code == 200
    assert res_speak.get_json()['success'] is True


def test_chatbot_legacy_api_routes(client, auth_user, agent_test_data):
    """Test legacy web chat endpoints (/chatbot/api/message, /chatbot/api/history, /chatbot/api/clear)."""
    client.post('/auth/login', data={'email': auth_user.email, 'password': 'testpassword123'}, follow_redirects=True)

    # Send message
    resp = client.post('/chatbot/api/message', json={'message': 'What is my current career status?'})
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'Career Status' in data['response'] or 'CareerMate' in data['response']

    # Get history
    hist_resp = client.get('/chatbot/api/history')
    assert hist_resp.status_code == 200
    hist_data = hist_resp.get_json()
    assert len(hist_data) >= 1

    # Clear history
    clear_resp = client.post('/chatbot/api/clear')
    assert clear_resp.status_code == 200
    assert clear_resp.get_json()['success'] is True
