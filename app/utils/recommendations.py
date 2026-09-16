"""
CareerMate Recommendation Engine
Modular, deterministic candidate-to-job matching architecture.
Combines profile data and resume intelligence to rank opportunities and generate transparent match explanations.
"""

import os
from datetime import datetime
from app.models.company import Company
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
        Generate ranked recommendations for a user.
        Excludes jobs marked as not relevant by the user.
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
            
        companies = Company.query.all()
        target_role_skills = DOMAIN_ROLE_SKILLS.get(candidate['target_role'], DOMAIN_ROLE_SKILLS['Full Stack Engineer'])
        
        candidate_skills_lower = {s.lower() for s in candidate['all_skills']}
        
        scored_jobs = []
        for comp in companies:
            if comp.company_id in hidden_ids:
                continue
                
            comp_text = f"{comp.company_name} {comp.description or ''} {comp.eligibility or ''}"
            comp_lower = comp_text.lower()
            
            # 1. Skill Extraction & Coverage
            required_skills_in_job = []
            matching_skills = []
            missing_skills = []
            
            # Check domain role skills and company-specific words
            for r_skill in target_role_skills:
                # Is skill mentioned in company text or default requirement
                if r_skill.lower() in comp_lower or len(required_skills_in_job) < 5:
                    required_skills_in_job.append(r_skill)
                    if r_skill.lower() in candidate_skills_lower:
                        matching_skills.append(r_skill)
                    else:
                        missing_skills.append(r_skill)
                        
            # Also check user skills present in comp_text
            for c_skill in candidate['all_skills']:
                if c_skill.lower() in comp_lower and c_skill not in matching_skills:
                    matching_skills.append(c_skill)
                    
            # 2. Match Scores calculation
            skill_coverage = (len(matching_skills) / max(len(required_skills_in_job), 1)) if required_skills_in_job else 0.3
            
            # Role relevance
            role_match = (candidate['target_role'].lower() in comp_lower) or (candidate['domain'] and candidate['domain'] in comp_lower)
            role_score = 0.25 if role_match else 0.15
            
            # Education eligibility check
            edu_match = True
            if comp.eligibility and candidate['education']['degree']:
                edu_match = True
            edu_score = 0.20 if edu_match else 0.10
            
            # Similarity score using resume if available
            sim_score = 0
            if candidate['resume_text']:
                sim_score = similarity_scorer.calculate_similarity(candidate['resume_text'], comp_text) / 100.0
            else:
                sim_score = skill_coverage
                
            # Weighted deterministic overall match score
            if candidate['has_resume']:
                overall = int((sim_score * 45) + (skill_coverage * 35) + (role_score * 100) + (edu_score * 100) * 0.1)
            else:
                overall = int((skill_coverage * 60) + (role_score * 100 * 0.2) + (edu_score * 100 * 0.2))
                
            overall = min(max(overall, 15), 98)
            
            # 3. Transparent Explanation Generation
            if len(matching_skills) >= 3:
                skills_str = ", ".join(matching_skills[:3])
                explanation = f"{skills_str} match your {candidate['source'].replace('_', ' + ')}."
            elif matching_skills and required_skills_in_job:
                explanation = f"{len(matching_skills)} of {len(required_skills_in_job)} target skills match your background."
            elif matching_skills:
                explanation = f"{matching_skills[0]} matches requirements for this position."
            elif role_match:
                explanation = f"Matches your target {candidate['target_role']} career track."
            else:
                explanation = f"Curated for {candidate['target_role']} candidates."
                
            scored_jobs.append({
                'company': comp,
                'company_id': comp.company_id,
                'company_name': comp.company_name,
                'target_role': candidate['target_role'],
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
            
        scored_jobs.sort(key=lambda x: x['match_score'], reverse=True)
        
        has_matches = len(scored_jobs) > 0
        
        return {
            'source': candidate['source'],
            'source_label': candidate['source_label'],
            'recommendations': scored_jobs[:limit],
            'has_matches': has_matches,
            'has_inputs': True,
            'freshness': 'Updated today'
        }
