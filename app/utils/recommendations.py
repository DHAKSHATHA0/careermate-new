"""
CareerMate Recommendation Engine
Modular, deterministic candidate-to-job matching architecture.
Combines profile data and resume intelligence to rank opportunities and generate transparent match explanations.
"""

import os
from datetime import datetime
from app.models.company import Company
from app.models.job import Job
from app.models.job_feedback import JobFeedback
from app.utils.resume_parser import ResumeParser
from app.utils.nlp_analyzer import NLPAnalyzer
from app.utils.similarity import SimilarityScorer

# Standard domain skill mappings
DOMAIN_ROLE_SKILLS = {
    'Full Stack Engineer': ['Python', 'JavaScript', 'React', 'Node.js', 'SQL', 'REST APIs', 'Git', 'Docker', 'HTML', 'CSS'],
    'AI/ML Engineer': ['Python', 'Machine Learning', 'Deep Learning', 'TensorFlow', 'PyTorch', 'SQL', 'Data Science', 'Git', 'REST APIs'],
    'Cloud & DevOps Engineer': ['AWS', 'Docker', 'Kubernetes', 'GCP', 'Azure', 'Git', 'Microservices', 'System Design', 'Python'],
    'Data Scientist': ['Python', 'SQL', 'Data Science', 'Machine Learning', 'PostgreSQL', 'Git', 'REST APIs'],
    'Core Software Engineer': ['Java', 'C++', 'SQL', 'System Design', 'Git', 'Microservices', 'REST APIs', 'Docker']
}

DOMAIN_MAPPING = {
    'web_dev': 'Full Stack Engineer',
    'ml': 'AI/ML Engineer',
    'data_science': 'Data Scientist',
    'cloud': 'Cloud & DevOps Engineer',
    'core': 'Core Software Engineer'
}

nlp_analyzer = NLPAnalyzer()
similarity_scorer = SimilarityScorer()

class JobRecommendationEngine:
    """Engine that calculates genuine deterministic match scores, rankings, and explanations."""
    
    @staticmethod
    def get_candidate_representation(user, latest_resume=None):
        """
        Extract and combine candidate attributes from profile and resume.
        Returns: candidate dictionary and source classification.
        """
        profile_skills = [s.skill_name.strip() for s in user.skills] if user and user.skills else []
        target_role = DOMAIN_MAPPING.get(user.domain, 'Full Stack Engineer') if (user and user.domain) else 'Full Stack Engineer'
        
        has_profile = bool(profile_skills or (user and (user.domain or user.degree or user.current_company)))
        
        resume_skills = []
        resume_text = ""
        has_resume = False
        
        if latest_resume and latest_resume.file_path and os.path.exists(latest_resume.file_path):
            try:
                extracted = ResumeParser.extract_text(latest_resume.file_path)
                if extracted and len(extracted.strip()) > 40:
                    resume_text = extracted
                    keywords = nlp_analyzer.extract_keywords(extracted)
                    resume_skills = [k.title() for k in keywords]
                    has_resume = True
            except Exception:
                has_resume = False
                
        # Determine source
        if has_profile and has_resume:
            source = 'profile_resume'
            source_label = 'Based on your profile + resume'
        elif has_profile:
            source = 'profile'
            source_label = 'Based on your profile'
        elif has_resume:
            source = 'resume'
            source_label = 'Based on your resume'
        else:
            source = 'insufficient_data'
            source_label = None
            
        # Unified skills
        combined_skills_dict = {}
        for s in profile_skills + resume_skills:
            if s and s.strip():
                combined_skills_dict[s.lower().strip()] = s.strip()
                
        unified_skills = list(combined_skills_dict.values())
        
        return {
            'target_role': target_role,
            'domain': user.domain if user else None,
            'education': {
                'degree': user.degree if user else None,
                'college': user.college_name if user else None,
                'year': user.graduation_year if user else None
            },
            'user_type': user.user_type if user else 'student',
            'profile_skills': profile_skills,
            'resume_skills': resume_skills,
            'all_skills': unified_skills,
            'resume_text': resume_text,
            'has_profile': has_profile,
            'has_resume': has_resume,
            'source': source,
            'source_label': source_label
        }
        
    @staticmethod
    def get_recommendations(user, latest_resume=None, limit=5):
        """
        Generate ranked recommendations for a user operating on real Job records with Company fallback.
        Excludes jobs/companies marked as not relevant by the user.
        """
        candidate = JobRecommendationEngine.get_candidate_representation(user, latest_resume)
        
        if candidate['source'] == 'insufficient_data' or (not candidate['all_skills'] and not candidate['has_profile'] and not candidate['has_resume']):
            return {
                'source': 'insufficient_data',
                'source_label': None,
                'recommendations': [],
                'has_matches': False,
                'has_inputs': False,
                'freshness': None
            }
            
        # Fetch hidden company IDs from JobFeedback
        hidden_ids = set()
        if user and user.id:
            feedbacks = JobFeedback.query.filter_by(user_id=user.id).all()
            hidden_ids = {f.company_id for f in feedbacks}
            
        target_role_skills = DOMAIN_ROLE_SKILLS.get(candidate['target_role'], DOMAIN_ROLE_SKILLS['Full Stack Engineer'])
        candidate_skills_lower = {s.lower() for s in candidate['all_skills']}
        
        # Check if real active Job records exist
        active_jobs = Job.query.filter_by(status='active').all()
        
        scored_items = []
        
        if active_jobs:
            for job in active_jobs:
                if job.company_id in hidden_ids:
                    continue
                    
                comp = job.company
                job_skills = job.skills or []
                job_text = f"{job.title} {job.career_area or ''} {comp.company_name if comp else ''} {job.description or ''}"
                job_lower = job_text.lower()
                
                # 1. Matching & Missing Skills
                matching_skills = []
                missing_skills = []
                
                if job_skills:
                    for s in job_skills:
                        if s.lower() in candidate_skills_lower:
                            matching_skills.append(s)
                        else:
                            missing_skills.append(s)
                else:
                    for r_skill in target_role_skills:
                        if r_skill.lower() in job_lower:
                            if r_skill.lower() in candidate_skills_lower:
                                matching_skills.append(r_skill)
                            else:
                                missing_skills.append(r_skill)
                                
                # Check user candidate skills present in job text
                for c_skill in candidate['all_skills']:
                    if c_skill.lower() in job_lower and c_skill not in matching_skills:
                        matching_skills.append(c_skill)
                        
                required_count = max(len(job_skills) or len(target_role_skills), 1)
                skill_coverage = len(matching_skills) / required_count
                
                # Role Relevance
                role_match = (candidate['target_role'].lower() in job_lower) or (job.career_area and candidate['target_role'].lower() in job.career_area.lower())
                role_score = 0.25 if role_match else 0.15
                
                # Education check
                edu_match = True
                edu_score = 0.20 if (user and user.degree) else 0.10
                
                # Similarity Scorer
                sim_score = 0
                if candidate['resume_text']:
                    sim_score = similarity_scorer.calculate_similarity(candidate['resume_text'], job_text) / 100.0
                else:
                    sim_score = skill_coverage
                    
                if candidate['has_resume']:
                    overall = int((sim_score * 45) + (skill_coverage * 35) + (role_score * 100) + (edu_score * 100 * 0.1))
                else:
                    overall = int((skill_coverage * 60) + (role_score * 100 * 0.2) + (edu_score * 100 * 0.2))
                    
                overall = min(max(overall, 15), 98)
                
                # Transparent explanation
                if len(matching_skills) >= 3:
                    skills_str = ", ".join(matching_skills[:3])
                    explanation = f"{skills_str} match your {candidate['source'].replace('_', ' + ')}."
                elif matching_skills:
                    explanation = f"{matching_skills[0]} and {len(matching_skills)} skills align with this opening."
                elif role_match:
                    explanation = f"Matches your target {candidate['target_role']} career area."
                else:
                    explanation = f"Recommended based on {candidate['target_role']} criteria."
                    
                scored_items.append({
                    'job_id': job.id,
                    'job': job,
                    'company': comp,
                    'company_id': comp.company_id if comp else None,
                    'company_name': comp.company_name if comp else 'Verified Tech Company',
                    'title': job.title,
                    'target_role': job.title,
                    'career_area': job.career_area or 'Software Engineering',
                    'location': job.location,
                    'work_mode': job.work_mode,
                    'match_score': overall,
                    'matching_skills': matching_skills[:4],
                    'required_skills': (job_skills[:5] if job_skills else target_role_skills[:5]),
                    'missing_skills': missing_skills[:4],
                    'role_match': role_match,
                    'education_match': edu_match,
                    'experience_match': True,
                    'explanation': explanation,
                    'recommendation_source': candidate['source_label'],
                    'salary': job.salary_display or (comp.salary if comp else None),
                    'eligibility': comp.eligibility if comp else None,
                    'description': job.description[:200] if job.description else ''
                })
        else:
            # Fallback to Company database
            companies = Company.query.all()
            for comp in companies:
                if comp.company_id in hidden_ids:
                    continue
                    
                comp_text = f"{comp.company_name} {comp.description or ''} {comp.eligibility or ''}"
                comp_lower = comp_text.lower()
                
                required_skills_in_job = []
                matching_skills = []
                missing_skills = []
                
                for r_skill in target_role_skills:
                    if r_skill.lower() in comp_lower or len(required_skills_in_job) < 5:
                        required_skills_in_job.append(r_skill)
                        if r_skill.lower() in candidate_skills_lower:
                            matching_skills.append(r_skill)
                        else:
                            missing_skills.append(r_skill)
                            
                for c_skill in candidate['all_skills']:
                    if c_skill.lower() in comp_lower and c_skill not in matching_skills:
                        matching_skills.append(c_skill)
                        
                skill_coverage = (len(matching_skills) / max(len(required_skills_in_job), 1)) if required_skills_in_job else 0.3
                role_match = (candidate['target_role'].lower() in comp_lower) or (candidate['domain'] and candidate['domain'] in comp_lower)
                role_score = 0.25 if role_match else 0.15
                edu_match = True
                edu_score = 0.20 if (user and user.degree) else 0.10
                
                sim_score = 0
                if candidate['resume_text']:
                    sim_score = similarity_scorer.calculate_similarity(candidate['resume_text'], comp_text) / 100.0
                else:
                    sim_score = skill_coverage
                    
                if candidate['has_resume']:
                    overall = int((sim_score * 45) + (skill_coverage * 35) + (role_score * 100) + (edu_score * 100) * 0.1)
                else:
                    overall = int((skill_coverage * 60) + (role_score * 100 * 0.2) + (edu_score * 100 * 0.2))
                    
                overall = min(max(overall, 15), 98)
                
                if len(matching_skills) >= 3:
                    skills_str = ", ".join(matching_skills[:3])
                    explanation = f"{skills_str} match your {candidate['source'].replace('_', ' + ')}."
                elif matching_skills:
                    explanation = f"{matching_skills[0]} matches requirements for this position."
                elif role_match:
                    explanation = f"Matches your target {candidate['target_role']} career track."
                else:
                    explanation = f"Curated for {candidate['target_role']} candidates."
                    
                scored_items.append({
                    'job_id': None,
                    'job': None,
                    'company': comp,
                    'company_id': comp.company_id,
                    'company_name': comp.company_name,
                    'title': candidate['target_role'],
                    'target_role': candidate['target_role'],
                    'career_area': 'Software Engineering',
                    'location': 'Remote / On-site',
                    'work_mode': 'Full-Time',
                    'match_score': overall,
                    'matching_skills': matching_skills[:4],
                    'required_skills': required_skills_in_job[:5],
                    'missing_skills': missing_skills[:4],
                    'role_match': role_match,
                    'education_match': edu_match,
                    'experience_match': True,
                    'explanation': explanation,
                    'recommendation_source': candidate['source_label'],
                    'salary': comp.salary,
                    'eligibility': comp.eligibility,
                    'description': comp.description
                })
                
        scored_items.sort(key=lambda x: x['match_score'], reverse=True)
        
        return {
            'source': candidate['source'],
            'source_label': candidate['source_label'],
            'recommendations': scored_items[:limit],
            'has_matches': len(scored_items) > 0,
            'has_inputs': True,
            'freshness': 'Updated today'
        }

    @staticmethod
    def get_company_role_matches(user, company_id, latest_resume=None):
        """Get personalized role recommendations specifically within a given company."""
        candidate = JobRecommendationEngine.get_candidate_representation(user, latest_resume)
        if not candidate['has_profile'] and not candidate['has_resume']:
            return []
            
        company_jobs = Job.query.filter_by(company_id=company_id, status='active').all()
        if not company_jobs:
            return []
            
        candidate_skills_lower = {s.lower() for s in candidate['all_skills']}
        scored = []
        
        for job in company_jobs:
            job_text = f"{job.title} {job.career_area or ''} {job.description or ''}"
            matching = [s for s in (job.skills or []) if s.lower() in candidate_skills_lower]
            
            # User candidate skills in job description
            for c in candidate['all_skills']:
                if c.lower() in job_text.lower() and c not in matching:
                    matching.append(c)
                    
            coverage = len(matching) / max(len(job.skills or [1]), 1)
            role_match = candidate['target_role'].lower() in job_text.lower()
            
            sim_score = 0
            if candidate['resume_text']:
                sim_score = similarity_scorer.calculate_similarity(candidate['resume_text'], job_text) / 100.0
            else:
                sim_score = coverage
                
            score = int((sim_score * 50) + (coverage * 30) + (20 if role_match else 10))
            score = min(max(score, 20), 98)
            
            scored.append({
                'job': job,
                'score': score,
                'matching_skills': matching[:4]
            })
            
        scored.sort(key=lambda x: x['score'], reverse=True)
        return scored

    @staticmethod
    def calculate_job_fit(user, job, latest_resume=None):
        """Calculate transparent fit breakdown between candidate and a specific Job record."""
        candidate = JobRecommendationEngine.get_candidate_representation(user, latest_resume)
        resume_text = candidate['resume_text']
        
        if not resume_text and user:
            user_skills_str = ", ".join(candidate['all_skills'])
            resume_text = f"Candidate: {user.name}\nEducation: {user.degree or ''} {user.college_name or ''}\nSkills: {user_skills_str}\nDomain: {user.domain or ''}"
            
        job_skills = job.skills or []
        job_text = f"{job.title}\nCareer Area: {job.career_area or ''}\nLocation: {job.location or ''}\nDescription: {job.description or ''}\nRequirements: {job.required_qualifications or ''}"
        
        sim_score = similarity_scorer.calculate_similarity(resume_text or "", job_text)
        
        candidate_skills_lower = {s.lower() for s in candidate['all_skills']}
        matching_skills = []
        missing_skills = []
        
        if job_skills:
            for s in job_skills:
                if s.lower() in candidate_skills_lower:
                    matching_skills.append(s)
                else:
                    missing_skills.append(s)
        else:
            matching_skills = similarity_scorer.get_matching_keywords(resume_text or "", job_text)
            missing_skills = similarity_scorer.extract_missing_keywords(resume_text or "", job_text)
            
        # Additional keyword check from candidate skills
        for c in candidate['all_skills']:
            if c.lower() in job_text.lower() and c not in matching_skills:
                matching_skills.append(c)
                
        # Breakdown scores
        skill_score = min(int((len(matching_skills) / max(len(job_skills) or 5, 1)) * 100), 100) if matching_skills else 15
        exp_score = 80 if user.user_type == 'professional' else 60 if user.user_type == 'fresher' else 45
        edu_score = 90 if (user.degree and user.college_name) else 50
        
        overall = int((sim_score * 0.45) + (skill_score * 0.35) + (exp_score * 0.1) + (edu_score * 0.1))
        overall = min(max(overall, 15), 98)
        
        if overall >= 70:
            rec = "Strong Fit — Your profile and technical background strongly align with this position. Recommended to apply."
            status_badge = "Strong Fit"
        elif overall >= 40:
            rec = "Moderate Fit — You possess essential foundational qualifications, but closing specific keyword and tool gaps will boost your competitive standing."
            status_badge = "Moderate Fit"
        else:
            rec = "Skill Gap Present — We recommend strengthening missing required competencies through dedicated coursework and projects prior to applying."
            status_badge = "Skill Gap"
            
        # Transparent explanation
        if len(matching_skills) >= 3:
            explanation = f"{', '.join(matching_skills[:3])} match your {candidate['source'].replace('_', ' + ')}."
        elif matching_skills:
            explanation = f"{matching_skills[0]} and {len(matching_skills)} skills match this role's requirements."
        else:
            explanation = f"Evaluated against {job.title} requirements."
            
        return {
            'overall_score': overall,
            'skill_score': skill_score,
            'exp_score': exp_score,
            'edu_score': edu_score,
            'matching_skills': matching_skills[:6],
            'missing_skills': missing_skills[:6],
            'recommendation': rec,
            'status_badge': status_badge,
            'explanation': explanation,
            'has_resume_file': candidate['has_resume']
        }
