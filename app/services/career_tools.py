"""
CareerMate AI Tools & Services Layer
Controlled internal tools wrapping existing CareerMate database models,
recommendation engines, resume parsers, and learning modules.

CRITICAL SECURITY RULE:
All user-specific queries are strictly scoped to the authenticated user's ID.
Never fabricate data if a record is not found.
"""

import os
from datetime import datetime
from app.extensions import db
from app.models.user import User
from app.models.resume import Resume
from app.models.job import Job
from app.models.company import Company
from app.models.job_application import JobApplication, APPLICATION_STATUSES
from app.models.saved_job import SavedJob
from app.models.job_analysis import JobAnalysis
from app.models.enrollment import CourseEnrollment
from app.models.question import Question
from app.models.skill import Skill
from app.utils.profile import calculate_profile_completeness
from app.utils.resume_parser import ResumeParser
from app.utils.nlp_analyzer import NLPAnalyzer
from app.utils.similarity import SimilarityScorer
from app.utils.recommendations import JobRecommendationEngine, DOMAIN_ROLE_SKILLS, DOMAIN_MAPPING

nlp_analyzer = NLPAnalyzer()
similarity_scorer = SimilarityScorer()

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
    'TensorFlow': {'type': 'Official Tutorials', 'provider': 'TensorFlow.org', 'url': 'https://www.tensorflow.org/tutorials', 'difficulty': 'Intermediate - Advanced', 'time': '3-4 weeks', 'impact': 'Model Training'},
    'PyTorch': {'type': 'Deep Learning with PyTorch', 'provider': 'PyTorch.org', 'url': 'https://pytorch.org/tutorials/', 'difficulty': 'Intermediate - Advanced', 'time': '3-4 weeks', 'impact': 'Model Architecture'},
    'System Design': {'type': 'System Architecture Guide', 'provider': 'System Design Primer', 'url': 'https://github.com/donnemartin/system-design-primer', 'difficulty': 'Advanced', 'time': '4 weeks', 'impact': 'High-Scale Engineering'},
    'Git': {'type': 'Version Control Book', 'provider': 'Pro Git Book', 'url': 'https://git-scm.com/book/en/v2', 'difficulty': 'Beginner', 'time': '1 week', 'impact': 'Collaboration'},
    'REST APIs': {'type': 'API Design Guide', 'provider': 'RESTful API Tutorial', 'url': 'https://restfulapi.net/', 'difficulty': 'Intermediate', 'time': '1 week', 'impact': 'Service Architecture'},
    'Data Science': {'type': 'Data Science Track', 'provider': 'Python Data Science Handbook', 'url': 'https://jakevdp.github.io/PythonDataScienceHandbook/', 'difficulty': 'Intermediate', 'time': '4-5 weeks', 'impact': 'Analytics & Modeling'},
    'PostgreSQL': {'type': 'Relational Database Mastery', 'provider': 'PostgreSQL Docs', 'url': 'https://www.postgresql.org/docs/', 'difficulty': 'Intermediate', 'time': '2 weeks', 'impact': 'Database Optimization'},
    'Power BI': {'type': 'Business Analytics Mastery', 'provider': 'Microsoft Learn', 'url': 'https://learn.microsoft.com/en-us/power-bi/', 'difficulty': 'Beginner - Intermediate', 'time': '2-3 weeks', 'impact': 'Business Intelligence'},
    'Pandas': {'type': 'Data Analysis Toolkit', 'provider': 'Pandas Official Docs', 'url': 'https://pandas.pydata.org/docs/', 'difficulty': 'Beginner - Intermediate', 'time': '2 weeks', 'impact': 'Data Manipulation'},
    'Java': {'type': 'Java Programming Track', 'provider': 'Oracle Java Tutorials', 'url': 'https://docs.oracle.com/javase/tutorial/', 'difficulty': 'Intermediate', 'time': '4 weeks', 'impact': 'Enterprise Backend'},
    'C++': {'type': 'Modern C++ Guide', 'provider': 'isocpp.org', 'url': 'https://isocpp.org/get-started', 'difficulty': 'Intermediate - Advanced', 'time': '4-6 weeks', 'impact': 'Low-Level Systems'}
}


class CareerTools:
    """Class exposing vetted, secure tools for CareerMate AI Assistant."""

    @staticmethod
    def get_user_profile(user_id: int) -> dict:
        """1. Return the authenticated user's current CareerMate profile."""
        user = db.session.get(User, user_id)
        if not user:
            return {'found': False, 'message': 'User profile not found.'}

        skills = [s.skill_name for s in user.skills]
        target_role = DOMAIN_MAPPING.get(user.domain, 'Full Stack Engineer') if user.domain else 'Full Stack Engineer'
        profile_pct = calculate_profile_completeness(user)

        return {
            'found': True,
            'user_id': user.id,
            'name': user.name,
            'email': user.email,
            'phone': user.phone,
            'user_type': user.user_type,
            'domain': user.domain,
            'target_role': target_role,
            'college_name': user.college_name,
            'degree': user.degree,
            'graduation_start_year': user.graduation_start_year,
            'graduation_year': user.graduation_year,
            'education_period': user.education_period,
            'current_company': user.current_company,
            'career_goal': user.career_goal,
            'skills': skills,
            'skills_count': len(skills),
            'profile_completeness': profile_pct,
            'is_profile_complete': bool(user.domain and ((user.college_name and user.degree) or user.current_company))
        }

    @staticmethod
    def get_resume_summary(user_id: int) -> dict:
        """2. Return the authenticated user's latest resume summary & ATS metrics."""
        resumes = Resume.query.filter_by(user_id=user_id).order_by(Resume.uploaded_at.desc()).all()
        if not resumes:
            return {
                'resume_available': False,
                'message': 'No resume uploaded yet in CareerMate.'
            }

        latest = resumes[0]
        extracted_skills = []
        entities = {}
        grammar_issues_count = 0
        formatting_issues_count = 0
        preview_text = ""

        if latest.file_path and os.path.exists(latest.file_path):
            try:
                r_text = ResumeParser.extract_text(latest.file_path)
                if r_text:
                    extracted_skills = nlp_analyzer.extract_keywords(r_text)
                    entities = nlp_analyzer.extract_entities(r_text)
                    grammar_issues = nlp_analyzer.check_grammar_issues(r_text)
                    grammar_issues_count = len(grammar_issues)
                    formatting_issues = nlp_analyzer.analyze_formatting(r_text)
                    formatting_issues_count = len(formatting_issues)
                    preview_text = r_text[:400]
            except Exception as e:
                print(f"Error reading resume for user {user_id}: {e}")

        ats_score = latest.ats_score
        if ats_score is None and preview_text:
            ats_score = similarity_scorer.calculate_ats_score(preview_text)

        return {
            'resume_available': True,
            'resume_id': latest.resume_id,
            'filename': os.path.basename(latest.file_path) if latest.file_path else 'Resume',
            'uploaded_at': latest.uploaded_at.strftime('%b %d, %Y') if latest.uploaded_at else None,
            'ats_score': ats_score,
            'extracted_skills': extracted_skills[:12],
            'entities': entities,
            'grammar_issues_count': grammar_issues_count,
            'formatting_issues_count': formatting_issues_count,
            'total_resumes_count': len(resumes)
        }

    @staticmethod
    def get_application_statistics(user_id: int) -> dict:
        """3. Return actual application pipeline statistics for authenticated user."""
        apps = JobApplication.query.filter_by(user_id=user_id).all()
        breakdown = {
            'Applied': 0,
            'Assessment': 0,
            'Shortlisted': 0,
            'Interview': 0,
            'Selected': 0,
            'Rejected': 0,
            'Withdrawn': 0,
            'Saved': 0
        }
        for a in apps:
            st = a.status.title() if a.status else 'Applied'
            if st in breakdown:
                breakdown[st] += 1
            else:
                breakdown['Applied'] += 1

        active_count = breakdown['Applied'] + breakdown['Assessment'] + breakdown['Shortlisted'] + breakdown['Interview']

        return {
            'total_applications': len(apps),
            'active_applications': active_count,
            'breakdown': {
                'applied': breakdown['Applied'],
                'assessment': breakdown['Assessment'],
                'shortlisted': breakdown['Shortlisted'],
                'interview': breakdown['Interview'],
                'selected': breakdown['Selected'],
                'rejected': breakdown['Rejected'],
                'withdrawn': breakdown['Withdrawn']
            }
        }

    @staticmethod
    def get_user_applications(user_id: int, company: str = None, role: str = None, status: str = None, limit: int = 15) -> dict:
        """4. Return filtered list of user's job applications."""
        query = JobApplication.query.filter_by(user_id=user_id)
        if company:
            query = query.filter(JobApplication.company_name.ilike(f"%{company}%"))
        if role:
            query = query.filter(JobApplication.job_title.ilike(f"%{role}%"))
        if status:
            query = query.filter(JobApplication.status.ilike(f"%{status}%"))

        apps = query.order_by(JobApplication.updated_at.desc()).limit(limit).all()
        results = []
        for a in apps:
            results.append({
                'id': a.id,
                'job_id': a.job_id,
                'company_name': a.company_name,
                'job_title': a.job_title,
                'status': a.status,
                'applied_at': a.applied_at.strftime('%b %d, %Y') if a.applied_at else None,
                'interview_date': a.interview_date.strftime('%b %d, %Y') if a.interview_date else None,
                'notes': a.notes,
                'application_url': a.application_url
            })

        return {
            'count': len(results),
            'total_filtered': len(results),
            'applications': results
        }

    @staticmethod
    def get_saved_jobs(user_id: int) -> dict:
        """5. Return user's actual saved jobs."""
        saved_entries = SavedJob.query.filter_by(user_id=user_id).order_by(SavedJob.saved_at.desc()).all()
        results = []
        for s in saved_entries:
            job = s.job
            if job:
                results.append({
                    'job_id': job.id,
                    'title': job.title,
                    'company_name': job.company.company_name if job.company else 'Employer',
                    'location': job.location,
                    'work_mode': job.work_mode,
                    'salary': job.salary_display,
                    'application_url': job.application_url,
                    'saved_at': s.saved_at.strftime('%b %d, %Y') if s.saved_at else None
                })

        return {
            'count': len(results),
            'saved_jobs': results
        }

    @staticmethod
    def get_matching_jobs(user_id: int, limit: int = 5, role_filter: str = None, company_filter: str = None) -> dict:
        """6. Return personalized matched jobs calculated by CareerMate Recommendation Engine."""
        user = db.session.get(User, user_id)
        if not user:
            return {'found': False, 'recommendations': [], 'message': 'User not found.'}

        resumes = Resume.query.filter_by(user_id=user_id).order_by(Resume.uploaded_at.desc()).all()
        latest_resume = resumes[0] if resumes else None

        rec_result = JobRecommendationEngine.get_recommendations(user, latest_resume, limit=15)
        raw_recs = rec_result.get('recommendations', [])

        filtered = []
        for r in raw_recs:
            if role_filter:
                title = (r.get('title') or '').lower()
                target_role = (r.get('target_role') or '').lower()
                rf = role_filter.lower()
                if rf not in title and rf not in target_role:
                    continue
            if company_filter:
                cname = (r.get('company_name') or '').lower()
                if company_filter.lower() not in cname:
                    continue
            filtered.append(r)

        items = []
        for item in filtered[:limit]:
            items.append({
                'job_id': item.get('job_id'),
                'company_id': item.get('company_id'),
                'title': item.get('title'),
                'company': item.get('company_name'),
                'location': item.get('location'),
                'match_score': item.get('match_score'),
                'matching_skills': item.get('matching_skills', []),
                'missing_skills': item.get('missing_skills', []),
                'role_match': item.get('role_match', True),
                'education_match': item.get('education_match', True),
                'explanation': item.get('explanation'),
                'salary': item.get('salary'),
                'recommendation_source': item.get('recommendation_source')
            })

        return {
            'found': len(items) > 0,
            'source_label': rec_result.get('source_label', 'Profile & Resume Analysis'),
            'total_matches': len(filtered),
            'recommendations': items
        }

    @staticmethod
    def analyze_job_fit(user_id: int, job_id: int = None, company_id: int = None, company_name: str = None, role: str = None, custom_jd: str = None) -> dict:
        """7. Analyze candidate fit against a specific Job, Company, or Custom JD."""
        user = db.session.get(User, user_id)
        if not user:
            return {'found': False, 'message': 'User not found.'}

        resumes = Resume.query.filter_by(user_id=user_id).order_by(Resume.uploaded_at.desc()).all()
        latest_resume = resumes[0] if resumes else None

        job = None
        if job_id:
            job = db.session.get(Job, job_id)
        elif role or company_name:
            query = Job.query.filter_by(status='active')
            if company_name:
                comp = Company.query.filter(Company.company_name.ilike(f"%{company_name}%")).first()
                if comp:
                    query = query.filter_by(company_id=comp.company_id)
            if role:
                query = query.filter((Job.title.ilike(f"%{role}%")) | (Job.career_area.ilike(f"%{role}%")))
            job = query.first()

        if job:
            fit = JobRecommendationEngine.calculate_job_fit(user, job, latest_resume)
            return {
                'target_type': 'job',
                'job_id': job.id,
                'job_title': job.title,
                'company_name': job.company.company_name if job.company else 'Employer',
                'overall_score': fit.get('overall_score', 50),
                'skill_score': fit.get('skill_score', 50),
                'exp_score': fit.get('exp_score', 50),
                'edu_score': fit.get('edu_score', 50),
                'matching_skills': fit.get('matching_skills', []),
                'missing_skills': fit.get('missing_skills', []),
                'recommendation': fit.get('recommendation'),
                'status_badge': fit.get('status_badge'),
                'explanation': fit.get('explanation')
            }

        # Fallback to company or role analysis
        comp = None
        if company_id:
            comp = db.session.get(Company, company_id)
        elif company_name:
            comp = Company.query.filter(Company.company_name.ilike(f"%{company_name}%")).first()

        target_title = role or (comp.company_name if comp else 'Target Position')
        candidate = JobRecommendationEngine.get_candidate_representation(user, latest_resume)
        user_skills_lower = {s.lower() for s in candidate['all_skills']}
        target_role = role or candidate['target_role']
        required_skills = DOMAIN_ROLE_SKILLS.get(target_role, DOMAIN_ROLE_SKILLS.get('Full Stack Engineer', []))

        matching = [s for s in required_skills if s.lower() in user_skills_lower]
        missing = [s for s in required_skills if s.lower() not in user_skills_lower]
        coverage = len(matching) / max(len(required_skills), 1)
        score = int(coverage * 70 + (20 if candidate['has_resume'] else 10) + (10 if user.degree else 5))
        score = min(max(score, 20), 95)

        return {
            'target_type': 'role_or_company',
            'company_name': comp.company_name if comp else (company_name or 'Industry Standard'),
            'job_title': target_title,
            'overall_score': score,
            'matching_skills': matching,
            'missing_skills': missing,
            'recommendation': f"Closing the {len(missing)} missing technical skills will substantially improve selection odds.",
            'status_badge': "Strong Fit" if score >= 70 else ("Moderate Fit" if score >= 45 else "Skill Gap"),
            'explanation': f"Based on verified {target_role} requirements and your CareerMate profile."
        }

    @staticmethod
    def get_company_roles(company_id: int = None, company_name: str = None) -> dict:
        """8. Return actual verified active Job records & derived career areas belonging to a company."""
        comp = None
        if company_id:
            comp = db.session.get(Company, company_id)
        elif company_name:
            comp = Company.query.filter(Company.company_name.ilike(f"%{company_name.strip()}%")).first()

        if not comp:
            all_comps = Company.query.order_by(Company.company_name).all()
            return {
                'found': False,
                'message': f"Company '{company_name or company_id}' not found in CareerMate.",
                'available_companies': [c.company_name for c in all_comps]
            }

        active_jobs = [j for j in comp.jobs if j.status == 'active']
        career_areas = comp.career_areas
        sample_questions = []
        for q in comp.questions[:4]:
            sample_questions.append({
                'type': q.question_type,
                'difficulty': q.difficulty_level,
                'question': q.question,
                'answer': q.answer
            })

        jobs_data = []
        for j in active_jobs:
            jobs_data.append({
                'id': j.id,
                'title': j.title,
                'career_area': j.career_area,
                'location': j.location,
                'work_mode': j.work_mode,
                'salary': j.salary_display,
                'skills': j.skills,
                'application_url': j.application_url
            })

        return {
            'found': True,
            'company_id': comp.company_id,
            'company_name': comp.company_name,
            'industry': comp.industry,
            'description': comp.description,
            'headquarters': comp.headquarters,
            'locations': comp.locations,
            'salary_package': comp.salary,
            'eligibility': comp.eligibility,
            'selection_process': comp.selection_process,
            'career_areas': career_areas,
            'active_jobs_count': len(active_jobs),
            'active_jobs': jobs_data,
            'sample_questions': sample_questions
        }

    @staticmethod
    def get_assessment_history(user_id: int) -> dict:
        """9. Return available assessment intelligence, practice topics, and platform question banks."""
        questions = Question.query.all()
        by_type = {}
        by_difficulty = {}
        for q in questions:
            t = q.question_type.title()
            d = q.difficulty_level.title()
            by_type[t] = by_type.get(t, 0) + 1
            by_difficulty[d] = by_difficulty.get(d, 0) + 1

        companies_with_questions = Company.query.join(Question).distinct().all()

        return {
            'total_questions_in_bank': len(questions),
            'categories': by_type,
            'difficulty_distribution': by_difficulty,
            'companies_with_prep': [c.company_name for c in companies_with_questions],
            'core_modules': [
                {'module': 'Aptitude & Quantitative', 'topics': ['Number System', 'Percentages & Profit/Loss', 'Time & Work', 'Probability']},
                {'module': 'Logical & Verbal Ability', 'topics': ['Logical Reasoning', 'Data Interpretation', 'Reading Comprehension']},
                {'module': 'Data Structures & Algorithms', 'topics': ['Arrays & Two Pointers', 'Hashing', 'Trees & BST', 'Dynamic Programming']},
                {'module': 'Technical & Core Engineering', 'topics': ['OOP Concepts', 'DBMS & SQL', 'Operating Systems', 'System Design']}
            ]
        }

    @staticmethod
    def get_interview_history(user_id: int) -> dict:
        """10. Return interview records and stage progress for authenticated user."""
        apps = JobApplication.query.filter_by(user_id=user_id).filter(
            (JobApplication.status == 'Interview') |
            (JobApplication.interview_date != None) |
            (JobApplication.status.in_(['Shortlisted', 'Selected', 'Rejected']))
        ).order_by(JobApplication.updated_at.desc()).all()

        results = []
        for a in apps:
            results.append({
                'id': a.id,
                'company_name': a.company_name,
                'job_title': a.job_title,
                'status': a.status,
                'interview_date': a.interview_date.strftime('%b %d, %Y') if a.interview_date else None,
                'notes': a.notes,
                'applied_at': a.applied_at.strftime('%b %d, %Y') if a.applied_at else None
            })

        return {
            'count': len(results),
            'interviews': results
        }

    @staticmethod
    def get_latest_interview_feedback(user_id: int) -> dict:
        """11. Return the most recent recorded interview feedback or notes."""
        apps_with_notes = JobApplication.query.filter_by(user_id=user_id).filter(
            JobApplication.notes != None,
            JobApplication.notes != ''
        ).order_by(JobApplication.updated_at.desc()).all()

        if not apps_with_notes:
            return {
                'has_feedback': False,
                'message': "I don't have recorded interview feedback for you yet in your Application Tracker."
            }

        latest = apps_with_notes[0]
        return {
            'has_feedback': True,
            'application_id': latest.id,
            'company_name': latest.company_name,
            'job_title': latest.job_title,
            'status': latest.status,
            'interview_date': latest.interview_date.strftime('%b %d, %Y') if latest.interview_date else None,
            'feedback_notes': latest.notes,
            'recorded_at': latest.updated_at.strftime('%b %d, %Y') if latest.updated_at else None
        }

    @staticmethod
    def get_course_progress(user_id: int) -> dict:
        """12. Return actual enrolled courses and completion metrics for authenticated user."""
        enrollments = CourseEnrollment.query.filter_by(user_id=user_id).order_by(CourseEnrollment.updated_at.desc()).all()
        results = []
        completed_count = 0
        in_progress_count = 0

        for e in enrollments:
            if e.status == 'completed' or e.progress == 100:
                completed_count += 1
            else:
                in_progress_count += 1
            results.append({
                'id': e.id,
                'skill_name': e.skill_name,
                'course_title': e.course_title,
                'provider': e.provider,
                'url': e.url,
                'status': e.status,
                'progress': e.progress,
                'enrolled_at': e.enrolled_at.strftime('%b %d, %Y') if e.enrolled_at else None,
                'updated_at': e.updated_at.strftime('%b %d, %Y') if e.updated_at else None
            })

        return {
            'total_enrolled': len(enrollments),
            'completed_count': completed_count,
            'in_progress_count': in_progress_count,
            'courses': results
        }

    @staticmethod
    def get_recommended_courses(user_id: int, skills: list = None, role: str = None, job_id: int = None) -> dict:
        """13. Retrieve verified CareerMate courses mapped directly to required missing skills."""
        user = db.session.get(User, user_id)
        resumes = Resume.query.filter_by(user_id=user_id).order_by(Resume.uploaded_at.desc()).all() if user else []
        latest_resume = resumes[0] if resumes else None

        target_skills = skills or []
        if not target_skills:
            if job_id:
                job = db.session.get(Job, job_id)
                if job:
                    fit = JobRecommendationEngine.calculate_job_fit(user, job, latest_resume)
                    target_skills = fit.get('missing_skills', [])
            elif role:
                reqs = DOMAIN_ROLE_SKILLS.get(role, DOMAIN_ROLE_SKILLS.get('Full Stack Engineer', []))
                cand = JobRecommendationEngine.get_candidate_representation(user, latest_resume)
                cand_skills_lower = {s.lower() for s in cand['all_skills']}
                target_skills = [s for s in reqs if s.lower() not in cand_skills_lower]
            elif user:
                target_role = DOMAIN_MAPPING.get(user.domain, 'Full Stack Engineer')
                reqs = DOMAIN_ROLE_SKILLS.get(target_role, DOMAIN_ROLE_SKILLS.get('Full Stack Engineer', []))
                cand = JobRecommendationEngine.get_candidate_representation(user, latest_resume)
                cand_skills_lower = {s.lower() for s in cand['all_skills']}
                target_skills = [s for s in reqs if s.lower() not in cand_skills_lower]

        enrolled_skills = set()
        if user:
            enrolled = CourseEnrollment.query.filter_by(user_id=user.id).all()
            enrolled_skills = {e.skill_name.lower() for e in enrolled}

        recommended = []
        for s in target_skills:
            res = SKILL_LEARNING_RESOURCES.get(s)
            if res:
                recommended.append({
                    'skill': s,
                    'title': f"Mastering {s}: {res['type']}",
                    'provider': res['provider'],
                    'url': res['url'],
                    'difficulty': res['difficulty'],
                    'time': res['time'],
                    'impact': res['impact'],
                    'is_enrolled': s.lower() in enrolled_skills
                })

        return {
            'target_skills': target_skills,
            'count': len(recommended),
            'recommended_courses': recommended
        }

    @staticmethod
    def get_missing_skills(user_id: int, job_id: int = None, role: str = None) -> dict:
        """14. Return exact missing technical skills based on real job fit or domain standards."""
        user = db.session.get(User, user_id)
        if not user:
            return {'found': False, 'missing_skills': []}

        resumes = Resume.query.filter_by(user_id=user_id).order_by(Resume.uploaded_at.desc()).all()
        latest_resume = resumes[0] if resumes else None

        if job_id:
            job = db.session.get(Job, job_id)
            if job:
                fit = JobRecommendationEngine.calculate_job_fit(user, job, latest_resume)
                return {
                    'target': f"{job.company.company_name if job.company else 'Employer'} — {job.title}",
                    'matching_skills': fit.get('matching_skills', []),
                    'missing_skills': fit.get('missing_skills', []),
                    'total_missing': len(fit.get('missing_skills', []))
                }

        target_role = role or (DOMAIN_MAPPING.get(user.domain, 'Full Stack Engineer') if user.domain else 'Full Stack Engineer')
        required_skills = DOMAIN_ROLE_SKILLS.get(target_role, DOMAIN_ROLE_SKILLS.get('Full Stack Engineer', []))
        candidate = JobRecommendationEngine.get_candidate_representation(user, latest_resume)
        cand_skills_lower = {s.lower() for s in candidate['all_skills']}

        matching = [s for s in required_skills if s.lower() in cand_skills_lower]
        missing = [s for s in required_skills if s.lower() not in cand_skills_lower]

        return {
            'target': target_role,
            'matching_skills': matching,
            'missing_skills': missing,
            'total_missing': len(missing),
            'all_required': required_skills
        }

    @staticmethod
    def get_career_roadmap(user_id: int, target_role: str = None) -> dict:
        """15. Build comprehensive structured career roadmap grounded in real user and job data."""
        user = db.session.get(User, user_id)
        if not user:
            return {'found': False, 'message': 'User not found.'}

        resumes = Resume.query.filter_by(user_id=user_id).order_by(Resume.uploaded_at.desc()).all()
        latest_resume = resumes[0] if resumes else None

        role = target_role or (DOMAIN_MAPPING.get(user.domain, 'Full Stack Engineer') if user.domain else 'Full Stack Engineer')
        skills_info = CareerTools.get_missing_skills(user_id, role=role)
        courses_info = CareerTools.get_recommended_courses(user_id, skills=skills_info['missing_skills'])
        matching_jobs_info = CareerTools.get_matching_jobs(user_id, limit=3, role_filter=role)
        app_stats = CareerTools.get_application_statistics(user_id)

        return {
            'target_role': role,
            'current_position': {
                'name': user.name,
                'user_type': user.user_type,
                'degree': user.degree,
                'college': user.college_name,
                'has_resume': bool(latest_resume),
                'ats_score': latest_resume.ats_score if latest_resume else None,
                'matching_skills': skills_info['matching_skills']
            },
            'skill_gaps': skills_info['missing_skills'],
            'recommended_courses': courses_info['recommended_courses'][:4],
            'matching_jobs': matching_jobs_info['recommendations'],
            'application_status': app_stats
        }

    @staticmethod
    def get_next_best_actions(user_id: int) -> dict:
        """16. Determine prioritized actionable tasks grounded in actual user state."""
        user = db.session.get(User, user_id)
        if not user:
            return {'actions': []}

        resumes = Resume.query.filter_by(user_id=user_id).order_by(Resume.uploaded_at.desc()).all()
        latest_resume = resumes[0] if resumes else None
        profile_pct = calculate_profile_completeness(user)
        enrolled_courses = CourseEnrollment.query.filter_by(user_id=user_id).all()
        in_progress_courses = [e for e in enrolled_courses if e.status != 'completed' and e.progress < 100]
        apps = JobApplication.query.filter_by(user_id=user_id).all()

        actions = []

        if not latest_resume:
            actions.append({
                'priority': 1,
                'title': 'Upload Your Resume to Unlock ATS Analysis',
                'description': 'Upload your PDF or DOCX resume to calculate keyword fit and ATS compatibility.',
                'action_label': 'Analyze Resume',
                'action_url': '/resume/analyzer'
            })
        elif latest_resume.ats_score and latest_resume.ats_score < 75:
            actions.append({
                'priority': 1,
                'title': f"Improve ATS Compatibility (Current Score: {latest_resume.ats_score}%)",
                'description': 'Incorporate action verbs, quantitative outcomes, and relevant tech keywords.',
                'action_label': 'Review Resume',
                'action_url': '/resume/analyzer'
            })

        if profile_pct < 80:
            actions.append({
                'priority': 2,
                'title': f"Complete Your Profile Details ({profile_pct}% complete)",
                'description': 'Add your target domain, education timeline, and technical skills.',
                'action_label': 'Edit Profile',
                'action_url': '/profile'
            })

        if in_progress_courses:
            course = in_progress_courses[0]
            actions.append({
                'priority': 3,
                'title': f"Continue Learning Track: {course.skill_name} ({course.progress}%)",
                'description': f"Progress in '{course.course_title}' to close high-priority technical gaps.",
                'action_label': 'View Courses',
                'action_url': '/courses'
            })
        else:
            actions.append({
                'priority': 3,
                'title': 'Enroll in Target Role Learning Track',
                'description': 'Start official tutorials and documentation for your missing technical skills.',
                'action_label': 'Explore Courses',
                'action_url': '/courses'
            })

        if len(apps) == 0:
            actions.append({
                'priority': 4,
                'title': 'Review Verified Job Recommendations',
                'description': 'Explore active positions with high compatibility scores tailored to your profile.',
                'action_label': 'View Matching Jobs',
                'action_url': '/jobs'
            })
        else:
            actions.append({
                'priority': 4,
                'title': f"Track Active Applications ({len(apps)} total in pipeline)",
                'description': 'Keep notes updated and track upcoming interview dates.',
                'action_label': 'Application Tracker',
                'action_url': '/jobs?tab=tracker'
            })

        return {
            'count': len(actions),
            'actions': actions
        }
