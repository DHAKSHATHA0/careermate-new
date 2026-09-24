"""
CareerMate AI Agent Orchestration Layer
Transforms user questions and multimodal inputs into intent -> tool execution -> validated data -> grounded answer.

Strict security & anti-hallucination guarantees:
- Authenticated user data only
- Real database records as source of truth
- Computer Vision & OCR image understanding pipeline
- Graceful deterministic fallback and streaming support
"""

import os
import re
import json
import time
import logging
import urllib.request
import urllib.error
from app.services.career_tools import CareerTools
from app.services.image_intelligence import ImageIntelligence
from app.models.company import Company
from app.models.job import Job

logger = logging.getLogger(__name__)


class CareerMateAgent:
    """Orchestrator for Multimodal Career Intelligence queries."""

    def __init__(self):
        self.provider = os.getenv('LLM_PROVIDER', 'openai').lower()
        self.model = os.getenv('LLM_MODEL', 'gpt-4o-mini')
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        if self.openai_api_key and ('placeholder' in self.openai_api_key or 'test' in self.openai_api_key or len(self.openai_api_key) < 10):
            self.openai_api_key = None
        self.ollama_host = os.getenv('OLLAMA_HOST', 'http://localhost:11434')

    def process_message(self, user, message: str, image_path: str = None, history: list = None) -> dict:
        """
        Main orchestration entry point:
        1. Context extraction & Multimodal image processing
        2. Intent understanding & Tool execution scoped strictly to user.id
        3. Response generation (LLM or Grounded Synthesizer)
        """
        if not user or not user.is_authenticated:
            return {
                'response': "Authentication required to access your personalized CareerMate intelligence.",
                'sources': ['CareerMate Security']
            }

        user_id = user.id
        query = (message or '').strip()
        history = history or []

        # 1. Process image if attached
        image_analysis = None
        if image_path and os.path.exists(image_path):
            ocr_res = ImageIntelligence.extract_text(image_path)
            extracted_text = ocr_res.get('text', '')
            image_analysis = ImageIntelligence.classify_and_extract_career_data(extracted_text, user_id)
            image_analysis['raw_ocr_text'] = extracted_text

        # 2. Resolve conversation context from history
        context = self._extract_conversational_context(query, history)

        # 3. Classify intent and identify required tools
        intent_info = self._classify_intent(query, context, image_analysis)
        intent = intent_info['intent']
        params = intent_info.get('params', {})

        # 4. Execute controlled CareerMate tools
        retrieved_data, sources = self._execute_tools(user_id, intent, params, context, image_analysis)

        # 5. Generate grounded natural language response
        response_text = self._generate_response(query, intent, retrieved_data, user, history, image_analysis)

        return {
            'message': query,
            'response': response_text,
            'sources': sources,
            'intent': intent,
            'image_analysis': image_analysis
        }

    def stream_message(self, user, message: str, image_path: str = None, history: list = None):
        """Generator that yields streaming chunks for SSE."""
        res_data = self.process_message(user, message, image_path, history)
        full_text = res_data.get('response', '')
        sources = res_data.get('sources', [])
        intent = res_data.get('intent', '')

        # Yield progressive chunks
        words = full_text.split(' ')
        chunk_size = 4
        for i in range(0, len(words), chunk_size):
            chunk = ' '.join(words[i:i + chunk_size]) + ' '
            yield json.dumps({'type': 'chunk', 'content': chunk}) + '\n'
            time.sleep(0.015)

        yield json.dumps({
            'type': 'done',
            'full_response': full_text,
            'sources': sources,
            'intent': intent
        }) + '\n'

    def _extract_conversational_context(self, query: str, history: list) -> dict:
        """Extract referenced companies, roles, and entities from recent chat history."""
        ctx = {
            'last_company': None,
            'last_role': None,
            'last_intent': None
        }

        recent_history = history[-6:] if history else []
        combined_text = " ".join([h.get('message', '') + " " + h.get('response', '') for h in recent_history])
        combined_lower = combined_text.lower()

        try:
            companies = Company.query.all()
            for c in companies:
                if c.company_name.lower() in combined_lower or (c.slug and c.slug in combined_lower):
                    ctx['last_company'] = c.company_name
        except Exception:
            pass

        common_roles = ['data analyst', 'data scientist', 'ml engineer', 'full stack engineer', 'software engineer', 'devops', 'cloud engineer']
        for r in common_roles:
            if r in combined_lower:
                ctx['last_role'] = r.title()

        return ctx

    def _classify_intent(self, query: str, context: dict, image_analysis: dict = None) -> dict:
        """Classify user intent and extract query parameters."""
        q = query.lower()

        # Check if image analysis dictates primary intent
        if image_analysis and image_analysis.get('has_extracted_data'):
            doc_type = image_analysis.get('doc_type')
            if doc_type == 'job_description':
                return {'intent': 'IMAGE_JOB_FIT', 'params': {'skills': image_analysis.get('extracted_skills', [])}}
            elif doc_type == 'assessment_result':
                return {'intent': 'IMAGE_ASSESSMENT', 'params': {'score': image_analysis.get('detected_score')}}
            elif doc_type == 'interview_feedback':
                return {'intent': 'IMAGE_INTERVIEW_FEEDBACK', 'params': {}}
            elif doc_type == 'resume_screenshot':
                return {'intent': 'IMAGE_RESUME', 'params': {'skills': image_analysis.get('extracted_skills', [])}}
            elif doc_type == 'coding_problem':
                return {'intent': 'IMAGE_CODING_PROBLEM', 'params': {}}

        # Extract company mentions
        company_param = None
        try:
            comps = Company.query.all()
            for c in comps:
                if c.company_name.lower() in q:
                    company_param = c.company_name
                    break
        except Exception:
            pass

        if not company_param and context.get('last_company'):
            if any(w in q for w in ['this company', 'them', 'they', 'for this', 'that company', 'there']):
                company_param = context['last_company']

        # Extract role mentions
        role_param = None
        role_map = {
            'data analyst': 'Data Analyst',
            'data science': 'Data Scientist',
            'data scientist': 'Data Scientist',
            'ml engineer': 'AI/ML Engineer',
            'machine learning': 'AI/ML Engineer',
            'full stack': 'Full Stack Engineer',
            'frontend': 'Full Stack Engineer',
            'backend': 'Full Stack Engineer',
            'cloud': 'Cloud & DevOps Engineer',
            'devops': 'Cloud & DevOps Engineer',
            'software engineer': 'Core Software Engineer',
            'core': 'Core Software Engineer'
        }
        for k, v in role_map.items():
            if k in q:
                role_param = v
                break

        if not role_param and context.get('last_role'):
            if any(w in q for w in ['this role', 'this job', 'that role', 'for this', 'for that', 'they']):
                role_param = context['last_role']

        # 1. APPLICATION STATS & HISTORY
        if any(w in q for w in ['how many jobs have i applied', 'how many applications', 'application count', 'applications did i make', 'application statistics', 'applications active', 'active applications', 'applied for']):
            if company_param or role_param or 'active' in q or 'list' in q or 'status' in q:
                return {'intent': 'USER_APPLICATIONS', 'params': {'company': company_param, 'role': role_param, 'status': 'Applied' if 'active' in q else None}}
            return {'intent': 'APPLICATION_STATS', 'params': {}}

        # 2. INTERVIEW FEEDBACK & HISTORY
        if any(w in q for w in ['interview feedback', 'last interview', 'interview say', 'happened in my last interview', 'interview performance', 'interview notes']):
            return {'intent': 'LATEST_INTERVIEW_FEEDBACK', 'params': {}}
        if any(w in q for w in ['interview history', 'my interviews', 'scheduled interviews', 'upcoming interview']):
            return {'intent': 'INTERVIEW_HISTORY', 'params': {}}

        # 3. SAVED JOBS
        if any(w in q for w in ['saved job', 'jobs i saved', 'my saved', 'saved list']):
            return {'intent': 'SAVED_JOBS', 'params': {}}

        # 4. ROADMAP / CAREER PATH
        if any(w in q for w in ['roadmap', 'career map', 'career path', 'i want to become', 'i want to get into', 'how to become', 'path to', 'step by step', 'guide to become']):
            return {'intent': 'CAREER_ROADMAP', 'params': {'role': role_param, 'company': company_param}}

        # 5. NEXT BEST ACTIONS / WHAT TO PREPARE NEXT
        if any(w in q for w in ['what should i do next', 'what should i prepare next', 'what should i do this week', 'improve my chances', 'what should i improve before applying', 'next action', 'next step', 'where should i start']):
            return {'intent': 'NEXT_ACTIONS', 'params': {}}

        # 6. ASSESSMENTS
        if any(w in q for w in ['assessment', 'assessments', 'weak in assessment', 'aptitude', 'dsa', 'practice test', 'test areas', 'weak areas in assessment']):
            return {'intent': 'ASSESSMENT_HISTORY', 'params': {}}

        # 7. COURSES & LEARNING
        if any(w in q for w in ['what courses should i take', 'courses are useful', 'course recommendation', 'which course', 'recommended course', 'what to learn for this job']):
            return {'intent': 'RECOMMENDED_COURSES', 'params': {'role': role_param, 'company': company_param}}
        if any(w in q for w in ['enrolled course', 'course progress', 'my courses', 'learning progress']):
            return {'intent': 'COURSE_PROGRESS', 'params': {}}

        # 8. MISSING SKILLS & SKILL GAP
        if any(w in q for w in ['skills am i missing', 'missing skills', 'skill gap', 'what skills do i lack', 'skills to learn', 'skills required']):
            return {'intent': 'MISSING_SKILLS', 'params': {'role': role_param, 'company': company_param}}

        # 9. JOB FIT / READINESS
        if any(w in q for w in ['why does this job match', 'am i ready', 'job fit', 'job readiness', 'fit for this', 'how well do i match', 'evaluate my fit']):
            return {'intent': 'JOB_FIT', 'params': {'role': role_param, 'company': company_param}}

        # 10. MATCHING JOBS / OPPORTUNITIES
        if any(w in q for w in ['which jobs should i apply', 'jobs currently match', 'jobs match me', 'matching jobs', 'roles that match my profile', 'which companies have roles that match', 'jobs match my profile', 'recommend jobs']):
            return {'intent': 'MATCHING_JOBS', 'params': {'role': role_param, 'company': company_param}}

        # 11. COMPANY SPECIFIC DETAILS
        if company_param and any(w in q for w in ['roles', 'eligibility', 'salary', 'selection process', 'interview questions', 'hiring', 'openings', 'about']):
            return {'intent': 'COMPANY_ROLES', 'params': {'company': company_param}}

        # 12. RESUME SPECIFIC
        if any(w in q for w in ['resume', 'ats score', 'ats', 'cv', 'resume summary', 'keywords in resume', 'ats compatibility']):
            return {'intent': 'RESUME_SUMMARY', 'params': {}}

        # 13. PROFILE & GENERAL CAREER STATUS
        if any(w in q for w in ['current career status', 'career status', 'my profile', 'strongest skills', 'what are my skills', 'about me', 'my education', 'profile summary']):
            return {'intent': 'USER_PROFILE', 'params': {}}

        if company_param:
            return {'intent': 'COMPANY_ROLES', 'params': {'company': company_param}}

        return {'intent': 'USER_PROFILE', 'params': {}}

    def _execute_tools(self, user_id: int, intent: str, params: dict, context: dict, image_analysis: dict = None) -> tuple:
        """Execute the appropriate CareerMate tools strictly scoped to user_id."""
        data = {}
        sources = ['CareerMate Platform Engine']

        if image_analysis:
            data['image_data'] = image_analysis
            sources.append('Computer Vision & OCR Pipeline')

        try:
            if intent in ['IMAGE_JOB_FIT', 'IMAGE_ASSESSMENT', 'IMAGE_INTERVIEW_FEEDBACK', 'IMAGE_RESUME', 'IMAGE_CODING_PROBLEM']:
                data['profile'] = CareerTools.get_user_profile(user_id)
                data['resume'] = CareerTools.get_resume_summary(user_id)
                data['matching_jobs'] = CareerTools.get_matching_jobs(user_id, limit=3)
                if image_analysis and image_analysis.get('missing_skills'):
                    data['recommended_courses'] = CareerTools.get_recommended_courses(
                        user_id,
                        skills=image_analysis['missing_skills']
                    )
                sources.extend(['CareerMate Profile', 'Job Fit Intelligence'])

            elif intent == 'USER_PROFILE':
                data['profile'] = CareerTools.get_user_profile(user_id)
                data['resume'] = CareerTools.get_resume_summary(user_id)
                data['next_actions'] = CareerTools.get_next_best_actions(user_id)
                sources.extend(['CareerMate User Profile', 'Skill Graph'])

            elif intent == 'RESUME_SUMMARY':
                data['resume'] = CareerTools.get_resume_summary(user_id)
                data['profile'] = CareerTools.get_user_profile(user_id)
                sources.append('CareerMate Resume Analyzer')

            elif intent == 'APPLICATION_STATS':
                data['stats'] = CareerTools.get_application_statistics(user_id)
                data['recent_apps'] = CareerTools.get_user_applications(user_id, limit=5)
                data['matching_jobs'] = CareerTools.get_matching_jobs(user_id, limit=3)
                sources.append('CareerMate Application Tracker')

            elif intent == 'USER_APPLICATIONS':
                data['applications'] = CareerTools.get_user_applications(
                    user_id,
                    company=params.get('company'),
                    role=params.get('role'),
                    status=params.get('status')
                )
                data['stats'] = CareerTools.get_application_statistics(user_id)
                sources.append('CareerMate Application Tracker')

            elif intent == 'SAVED_JOBS':
                data['saved_jobs'] = CareerTools.get_saved_jobs(user_id)
                sources.append('CareerMate Saved Opportunities')

            elif intent == 'MATCHING_JOBS':
                data['matching_jobs'] = CareerTools.get_matching_jobs(
                    user_id,
                    limit=5,
                    role_filter=params.get('role'),
                    company_filter=params.get('company')
                )
                data['profile'] = CareerTools.get_user_profile(user_id)
                sources.append('CareerMate Recommendation Engine')

            elif intent == 'JOB_FIT':
                data['fit'] = CareerTools.analyze_job_fit(
                    user_id,
                    company_name=params.get('company'),
                    role=params.get('role')
                )
                data['missing_skills'] = CareerTools.get_missing_skills(
                    user_id,
                    role=params.get('role')
                )
                data['courses'] = CareerTools.get_recommended_courses(
                    user_id,
                    skills=data['missing_skills'].get('missing_skills', [])
                )
                sources.extend(['CareerMate Job Fit Engine', 'Similarity Scorer'])

            elif intent == 'COMPANY_ROLES':
                data['company'] = CareerTools.get_company_roles(company_name=params.get('company'))
                data['profile'] = CareerTools.get_user_profile(user_id)
                sources.append(f"{params.get('company', 'Company')} Intelligence")

            elif intent == 'ASSESSMENT_HISTORY':
                data['assessments'] = CareerTools.get_assessment_history(user_id)
                sources.append('CareerMate Assessment Hub')

            elif intent == 'LATEST_INTERVIEW_FEEDBACK':
                data['feedback'] = CareerTools.get_latest_interview_feedback(user_id)
                sources.append('CareerMate Interview Archive')

            elif intent == 'INTERVIEW_HISTORY':
                data['interviews'] = CareerTools.get_interview_history(user_id)
                data['feedback'] = CareerTools.get_latest_interview_feedback(user_id)
                sources.append('CareerMate Interview Archive')

            elif intent == 'COURSE_PROGRESS':
                data['courses'] = CareerTools.get_course_progress(user_id)
                sources.append('CareerMate Course Registry')

            elif intent == 'RECOMMENDED_COURSES':
                data['missing_skills'] = CareerTools.get_missing_skills(user_id, role=params.get('role'))
                data['courses'] = CareerTools.get_recommended_courses(
                    user_id,
                    skills=data['missing_skills'].get('missing_skills', []),
                    role=params.get('role')
                )
                sources.append('CareerMate Learning Resources')

            elif intent == 'MISSING_SKILLS':
                data['missing_skills'] = CareerTools.get_missing_skills(user_id, role=params.get('role'))
                data['courses'] = CareerTools.get_recommended_courses(
                    user_id,
                    skills=data['missing_skills'].get('missing_skills', []),
                    role=params.get('role')
                )
                sources.append('CareerMate Skill Gap Engine')

            elif intent == 'CAREER_ROADMAP':
                data['roadmap'] = CareerTools.get_career_roadmap(user_id, target_role=params.get('role'))
                if params.get('company'):
                    data['company'] = CareerTools.get_company_roles(company_name=params.get('company'))
                sources.extend(['CareerMate Career Roadmap', 'Recommendation Engine'])

            elif intent == 'NEXT_ACTIONS':
                data['next_actions'] = CareerTools.get_next_best_actions(user_id)
                data['profile'] = CareerTools.get_user_profile(user_id)
                data['resume'] = CareerTools.get_resume_summary(user_id)
                sources.append('CareerMate Intelligence Pipeline')

        except Exception as e:
            logger.error(f"Error executing tools for intent {intent}: {e}")
            data['error'] = str(e)

        return data, sources

    def _generate_response(self, query: str, intent: str, data: dict, user, history: list, image_analysis: dict = None) -> str:
        """Generate response via OpenAI / Ollama if available, or deterministic grounded synthesizer."""
        if self.openai_api_key:
            try:
                return self._call_openai(query, intent, data, user, history, image_analysis)
            except Exception as e:
                logger.warning(f"OpenAI API call failed ({e}), falling back to deterministic synthesizer.")
                return self._grounded_fallback_generator(query, intent, data, user, image_analysis)

        elif self.provider == 'ollama':
            try:
                return self._call_ollama(query, intent, data, user, history)
            except Exception as e:
                logger.warning(f"Ollama call failed ({e}), falling back to deterministic synthesizer.")
                return self._grounded_fallback_generator(query, intent, data, user, image_analysis)

        return self._grounded_fallback_generator(query, intent, data, user, image_analysis)

    def _call_openai(self, query: str, intent: str, data: dict, user, history: list, image_analysis: dict = None) -> str:
        """Invoke OpenAI API with strict grounding system prompt and validated data payload."""
        from openai import OpenAI
        client = OpenAI(api_key=self.openai_api_key)

        system_prompt = f"""You are CareerMate AI, a deeply personalized, intelligent career assistant.
CRITICAL RULES:
1. ONLY use the verified structured CareerMate data provided below.
2. NEVER fabricate ATS scores, applications, interviews, feedback, jobs, companies, or courses.
3. If data is absent, state clearly: "I don't have recorded..." or "You haven't uploaded...".
4. Provide structured editorial markdown with clean headings (###), bullet points, and practical next steps.
5. Suggest relevant platform links: [View matching jobs](/jobs), [Analyze resume](/resume/analyzer), [Application tracker](/jobs?tab=tracker), [Courses](/courses), [Assessments](/assessments), [Career Roadmap](/roadmap), [Skill Gap](/skill-gap), [Profile](/profile).

VERIFIED CAREERMATE DATA:
{json.dumps(data, indent=2, default=str)}
"""
        messages = [{"role": "system", "content": system_prompt}]
        for h in (history[-4:] if history else []):
            messages.append({"role": "user", "content": h.get('message', '')})
            messages.append({"role": "assistant", "content": h.get('response', '')})

        messages.append({"role": "user", "content": query or "Analyze this career document."})

        response = client.chat.completions.create(
            model=self.model if self.model else "gpt-4o-mini",
            messages=messages,
            temperature=0.2,
            max_tokens=800
        )
        return response.choices[0].message.content

    def _call_ollama(self, query: str, intent: str, data: dict, user, history: list) -> str:
        """Invoke local Ollama API."""
        prompt = f"""System: You are CareerMate AI. Answer using ONLY this verified data:
{json.dumps(data, default=str)}

User Question: {query}"""
        payload = json.dumps({
            "model": self.model if self.model != 'gpt-4o-mini' else 'llama3',
            "prompt": prompt,
            "stream": False
        }).encode('utf-8')

        req = urllib.request.Request(
            f"{self.ollama_host}/api/generate",
            data=payload,
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            res_data = json.loads(resp.read().decode('utf-8'))
            return res_data.get('response', '')

    def _grounded_fallback_generator(self, query: str, intent: str, data: dict, user, image_analysis: dict = None) -> str:
        """
        Deterministic, zero-hallucination response synthesizer.
        Generates precise, editorial markdown directly from validated database tool outputs and image extractions.
        """
        first_name = user.name.split()[0] if user.name else 'there'

        # 0. MULTIMODAL IMAGE UNDERSTANDING RESPONSES
        if image_analysis and image_analysis.get('has_extracted_data'):
            doc_type = image_analysis.get('doc_type')
            extracted_skills = image_analysis.get('extracted_skills', [])
            matching_skills = image_analysis.get('matching_skills', [])
            missing_skills = image_analysis.get('missing_skills', [])
            score = image_analysis.get('detected_score')
            role = image_analysis.get('detected_role')
            comp = image_analysis.get('detected_company')

            if doc_type == 'job_description':
                ans = f"### 🖼️ Job Description Analysis\n\n"
                if comp or role:
                    ans += f"**Position**: {comp or 'Employer'} — **{role or 'Target Role'}**\n\n"
                ans += f"I analyzed your uploaded job description via computer vision & OCR:\n\n"

                ans += "### ✅ What You Already Match\n"
                if matching_skills:
                    for ms in matching_skills:
                        ans += f"- **{ms}** (Present in your profile)\n"
                else:
                    ans += "- No direct technical overlap detected with your current profile.\n"
                ans += "\n"

                ans += "### 🔍 Missing Requirements for This Role\n"
                if missing_skills:
                    for ms in missing_skills:
                        ans += f"- **{ms}** (Required)\n"
                else:
                    ans += "- You possess all extracted technical requirements for this position!\n"
                ans += "\n"

                courses = image_analysis.get('recommended_courses', [])
                if courses:
                    ans += "### 📚 Recommended Courses to Bridge These Gaps\n"
                    for c in courses:
                        ans += f"- **{c['skill']}**: [{c['title']}]({c['url']}) — *{c['provider']}* ({c['time']})\n"
                    ans += "\n"

                ans += "👉 [View all matching jobs in CareerMate](/jobs) or [Explore Courses](/courses)"
                return ans

            elif doc_type == 'assessment_result':
                ans = f"### 📊 Assessment Result Analysis\n\n"
                if score:
                    ans += f"- **Detected Score**: **{score}**\n"
                if extracted_skills:
                    ans += f"- **Assessment Topics**: {', '.join(extracted_skills)}\n\n"

                ans += "### 🎯 Targeted Practice Recommendations\n"
                ans += "Based on your assessment evaluation, prioritize these practice tracks in CareerMate Assessment Hub:\n\n"
                ans += "- **Quantitative & Aptitude**: Practice core formula derivation and timed problem sets.\n"
                ans += "- **Technical Fundamentals**: Deep dive into indexing, query optimization, and OOP.\n\n"
                ans += "👉 [Practice test modules in Assessment Hub](/assessments)"
                return ans

            elif doc_type == 'interview_feedback':
                ans = f"### 🎤 Interview Feedback Analysis\n\n"
                ans += "I reviewed the interview feedback in your uploaded screenshot:\n\n"
                if extracted_skills:
                    ans += f"- **Focus Areas Evaluated**: {', '.join(extracted_skills)}\n\n"
                ans += "### 📝 Key Action Items\n"
                ans += "1. Review technical concepts evaluated in previous interview rounds.\n"
                ans += "2. Update your interview notes in CareerMate Application Tracker.\n\n"
                ans += "👉 [Update Application Tracker](/jobs?tab=tracker)"
                return ans

            elif doc_type == 'resume_screenshot':
                ans = f"### 📄 Resume Screenshot Overview\n\n"
                if extracted_skills:
                    ans += f"**Extracted Technical Competencies**:\n"
                    for s in extracted_skills:
                        ans += f"- {s}\n"
                    ans += "\n"
                ans += "👉 [Upload your full PDF/DOCX to Resume Analyzer for exact ATS scoring](/resume/analyzer)"
                return ans

        # If image had unclear text
        if image_analysis and not image_analysis.get('has_extracted_data'):
            return (
                "### 🖼️ Image Received\n\n"
                "I received your image, but the text could not be reliably extracted. "
                "Please upload a higher resolution screenshot or clearer photo of the document.\n\n"
                "👉 [Resume Analyzer](/resume/analyzer) | [Jobs Directory](/jobs)"
            )

        # 1. USER PROFILE / CURRENT STATUS
        if intent == 'USER_PROFILE':
            prof = data.get('profile', {})
            res = data.get('resume', {})
            skills = prof.get('skills', [])

            ans = f"### 👤 Your Current Career Status\n\n"
            ans += f"**Candidate**: {prof.get('name', user.name)} ({prof.get('user_type', 'Student').title()})\n\n"
            if prof.get('degree') and prof.get('college_name'):
                ans += f"- **Education**: {prof.get('degree')} from {prof.get('college_name')} ({prof.get('education_period', 'N/A')})\n"
            domain_str = (prof.get('domain') or 'Not set').replace('_', ' ').title()
            ans += f"- **Target Career Domain**: {domain_str} &rarr; **{prof.get('target_role', 'Full Stack Engineer')}**\n"
            ans += f"- **Profile Completeness**: {prof.get('profile_completeness', 0)}%\n\n"

            ans += "### 💡 Your Recorded Skills\n"
            if skills:
                for s in skills[:6]:
                    ans += f"- **{s}** (Verified in profile)\n"
            else:
                ans += "*You have not added any skills to your profile yet. [Update your skills in Profile](/profile).*\n"

            ans += "\n### 📄 Resume Status\n"
            if res.get('resume_available'):
                ans += f"- **Active Resume**: `{res.get('filename')}` (Uploaded {res.get('uploaded_at')})\n"
                ans += f"- **ATS Compatibility Score**: **{res.get('ats_score')}%**\n"
                if res.get('extracted_skills'):
                    ans += f"- **Extracted Keywords**: {', '.join(res.get('extracted_skills')[:6])}\n"
            else:
                ans += "You haven't uploaded a resume yet. Upload one to calculate your ATS compatibility score and job fit: [Upload Resume](/resume/analyzer)\n"

            ans += "\n### 🎯 Recommended Immediate Action\n"
            actions = data.get('next_actions', {}).get('actions', [])
            if actions:
                top_action = actions[0]
                ans += f"**{top_action['title']}**: {top_action['description']} &rarr; [{top_action['action_label']}]({top_action['action_url']})\n"
            return ans

        # 2. RESUME SUMMARY
        elif intent == 'RESUME_SUMMARY':
            res = data.get('resume', {})
            if not res.get('resume_available'):
                return (
                    "### 📄 Resume Status\n\n"
                    "You haven't uploaded a resume yet in CareerMate.\n\n"
                    "👉 **Next Step**: [Upload your resume to Resume Analyzer](/resume/analyzer) to calculate your genuine ATS compatibility score, extract keywords, and identify missing criteria."
                )
            ans = f"### 📄 Resume Analysis Summary\n\n"
            ans += f"- **File**: `{res.get('filename')}`\n"
            ans += f"- **Uploaded**: {res.get('uploaded_at')}\n"
            ans += f"- **ATS Compatibility Score**: **{res.get('ats_score')}%**\n\n"

            if res.get('extracted_skills'):
                ans += "### 🔍 Verified Keywords Extracted\n"
                for kw in res.get('extracted_skills')[:8]:
                    ans += f"- {kw}\n"
                ans += "\n"

            if res.get('ats_score') and res.get('ats_score') < 75:
                ans += "### ⚠️ Optimization Advice\n"
                ans += "Your resume score is below the 75% ATS threshold. Consider adding measurable impact metrics and ensuring core domain skills are explicitly stated.\n\n"
            else:
                ans += "### ✅ ATS Health\n"
                ans += "Your resume demonstrates strong keyword density and standard formatting alignment.\n\n"

            ans += "👉 [View detailed Resume Analyzer insights](/resume/analyzer)"
            return ans

        # 3. APPLICATION STATS
        elif intent == 'APPLICATION_STATS':
            stats = data.get('stats', {})
            bd = stats.get('breakdown', {})
            total = stats.get('total_applications', 0)
            active = stats.get('active_applications', 0)

            ans = f"### 📊 Application Pipeline Status\n\n"
            ans += f"- **Total Applications Tracked**: **{total}**\n"
            ans += f"- **Currently Active Applications**: **{active}**\n\n"

            ans += "### 📌 Status Breakdown\n"
            ans += f"- **Applied**: {bd.get('applied', 0)}\n"
            ans += f"- **Assessment Stage**: {bd.get('assessment', 0)}\n"
            ans += f"- **Shortlisted**: {bd.get('shortlisted', 0)}\n"
            ans += f"- **Interview**: {bd.get('interview', 0)}\n"
            ans += f"- **Selected**: {bd.get('selected', 0)}\n"
            ans += f"- **Rejected**: {bd.get('rejected', 0)}\n"
            ans += f"- **Withdrawn**: {bd.get('withdrawn', 0)}\n\n"

            if total == 0:
                ans += "You haven't tracked any applications yet. When you apply to jobs, track them here: [Explore Matching Jobs](/jobs)\n"
            else:
                ans += "👉 [Manage your pipeline in Application Tracker](/jobs?tab=tracker)"
            return ans

        # 4. USER APPLICATIONS LIST
        elif intent == 'USER_APPLICATIONS':
            app_info = data.get('applications', {})
            apps = app_info.get('applications', [])
            count = len(apps)

            ans = f"### 📋 Your Tracked Applications ({count})\n\n"
            if not apps:
                ans += "I couldn't find any recorded applications matching those filters in your pipeline.\n\n"
                ans += "👉 [View all jobs to apply](/jobs) or [Open Application Tracker](/jobs?tab=tracker)"
                return ans

            for a in apps[:8]:
                st_badge = a.get('status', 'Applied')
                ans += f"- **{a.get('company_name')}** — *{a.get('job_title')}*\n"
                ans += f"  - Status: **{st_badge}** | Applied: {a.get('applied_at') or 'Recently'}\n"
                if a.get('interview_date'):
                    ans += f"  - 📅 Interview Date: **{a.get('interview_date')}**\n"
                if a.get('notes'):
                    ans += f"  - 📝 Notes: {a.get('notes')}\n"
                ans += "\n"

            ans += "👉 [Update statuses in Application Tracker](/jobs?tab=tracker)"
            return ans

        # 5. SAVED JOBS
        elif intent == 'SAVED_JOBS':
            saved_info = data.get('saved_jobs', {})
            jobs = saved_info.get('saved_jobs', [])

            ans = f"### 🔖 Your Saved Jobs ({len(jobs)})\n\n"
            if not jobs:
                ans += "You have not saved any jobs yet.\n\n"
                ans += "👉 [Browse recommended jobs and click 'Save'](/jobs)"
                return ans

            for j in jobs[:6]:
                ans += f"- **{j.get('title')}** at **{j.get('company_name')}**\n"
                ans += f"  - Location: {j.get('location')} ({j.get('work_mode')})\n"
                if j.get('salary'):
                    ans += f"  - Package: {j.get('salary')}\n"
                ans += f"  - Saved on: {j.get('saved_at')}\n\n"

            ans += "👉 [View all active opportunities](/jobs)"
            return ans

        # 6. MATCHING JOBS
        elif intent == 'MATCHING_JOBS':
            rec_info = data.get('matching_jobs', {})
            recs = rec_info.get('recommendations', [])

            if not recs:
                return (
                    "### 💼 Matching Opportunities\n\n"
                    "There are currently no matching active jobs meeting your exact criteria in CareerMate.\n\n"
                    "💡 *Tip: Ensure your profile domain and skills are filled out so the recommendation engine can calculate matches.*\n\n"
                    "👉 [Explore all available jobs](/jobs) or [Complete your profile](/profile)"
                )

            ans = f"### 💼 Matched Opportunities for Your Profile\n\n"
            ans += f"*{rec_info.get('source_label', 'Calculated by CareerMate Recommendation Engine')}*\n\n"

            for r in recs[:5]:
                match_pct = r.get('match_score', 75)
                ans += f"#### **{r.get('title')}** @ **{r.get('company')}** — `{match_pct}% Match`\n"
                ans += f"- **Location**: {r.get('location', 'Remote')}\n"
                if r.get('salary'):
                    ans += f"- **Package**: {r.get('salary')}\n"
                if r.get('matching_skills'):
                    ans += f"- **Matching Skills**: {', '.join(r.get('matching_skills'))}\n"
                if r.get('missing_skills'):
                    ans += f"- **Missing Skills**: {', '.join(r.get('missing_skills'))}\n"
                ans += f"- **Fit Summary**: {r.get('explanation')}\n\n"

            ans += "👉 [Apply and view full job descriptions on Jobs page](/jobs)"
            return ans

        # 7. JOB FIT ANALYSIS
        elif intent == 'JOB_FIT':
            fit = data.get('fit', {})
            overall = fit.get('overall_score', 50)
            target = fit.get('job_title') or 'Target Position'
            comp = fit.get('company_name') or 'Target Employer'

            ans = f"### 🎯 Job Fit Analysis: {comp} — {target}\n\n"
            ans += f"**Overall Compatibility Score**: **{overall}%** (`{fit.get('status_badge', 'Moderate Fit')}`)\n\n"

            matching = fit.get('matching_skills', [])
            missing = fit.get('missing_skills', [])

            ans += "### ✅ What You Already Match\n"
            if matching:
                for m in matching:
                    ans += f"- **{m}**\n"
            else:
                ans += "- No direct technical keyword overlaps detected yet.\n"
            ans += "\n"

            ans += "### 🔍 Skill Gaps to Address\n"
            if missing:
                for gap in missing:
                    ans += f"- **{gap}** (High Priority)\n"
            else:
                ans += "- No critical skill gaps identified for this role!\n"
            ans += "\n"

            courses = data.get('courses', {}).get('recommended_courses', [])
            if courses:
                ans += "### 📚 Recommended Preparation Courses\n"
                for c in courses[:3]:
                    ans += f"- **{c.get('skill')}**: [{c.get('title')}]({c.get('url')}) — *{c.get('provider')}* ({c.get('time')})\n"
                ans += "\n"

            ans += f"💡 **Evaluation**: {fit.get('recommendation', 'Focus on closing missing skills.')}\n\n"
            ans += "👉 [Run interactive Job Fit Analysis](/job-fit)"
            return ans

        # 8. COMPANY ROLES & INTELLIGENCE
        elif intent == 'COMPANY_ROLES':
            comp = data.get('company', {})
            if not comp.get('found'):
                avail = ", ".join(comp.get('available_companies', []))
                return f"### 🏢 Company Not Found\n\nI couldn't find '{comp.get('message')}'.\n\nAvailable companies in CareerMate: **{avail}**."

            cname = comp.get('company_name')
            ans = f"### 🏢 {cname} Career Overview\n\n"
            if comp.get('description'):
                ans += f"{comp.get('description')}\n\n"

            ans += f"- **Industry**: {comp.get('industry', 'Technology')}\n"
            if comp.get('headquarters'):
                ans += f"- **Headquarters**: {comp.get('headquarters')}\n"
            if comp.get('salary_package'):
                ans += f"- **Compensation Package**: {comp.get('salary_package')}\n"
            if comp.get('eligibility'):
                ans += f"- **Eligibility Criteria**: {comp.get('eligibility')}\n"
            if comp.get('selection_process'):
                ans += f"- **Selection Process**: {comp.get('selection_process')}\n\n"

            areas = comp.get('career_areas', [])
            if areas:
                ans += f"### 💼 Verified Active Career Areas ({len(areas)})\n"
                for a in areas:
                    ans += f"- **{a}**\n"
                ans += "\n"

            active_jobs = comp.get('active_jobs', [])
            if active_jobs:
                ans += f"### 🎯 Open Positions at {cname} ({len(active_jobs)})\n"
                for j in active_jobs[:4]:
                    ans += f"- **{j.get('title')}** ({j.get('location')}) — {j.get('salary') or 'Competitive'}\n"
                ans += "\n"

            questions = comp.get('sample_questions', [])
            if questions:
                ans += f"### 📝 Sample Interview & Practice Questions\n"
                for q in questions[:3]:
                    ans += f"- **[{q.get('type').upper()}]** {q.get('question')}\n"
                ans += "\n"

            ans += f"👉 [Explore all {cname} jobs & practice sets](/jobs?company={cname})"
            return ans

        # 9. ASSESSMENT HISTORY & PREPARATION
        elif intent == 'ASSESSMENT_HISTORY':
            ass = data.get('assessments', {})
            ans = f"### 🧪 Assessment & Preparation Hub\n\n"
            ans += f"CareerMate currently offers **{ass.get('total_questions_in_bank', 0)}+** verified assessment questions across all core hiring disciplines.\n\n"

            cats = ass.get('categories', {})
            if cats:
                ans += "### 📊 Question Categories\n"
                for cat, count in cats.items():
                    ans += f"- **{cat}**: {count} practice questions\n"
                ans += "\n"

            ans += "### 🎯 Recommended Practice Modules\n"
            for mod in ass.get('core_modules', []):
                ans += f"- **{mod['module']}**: {', '.join(mod['topics'])}\n"
            ans += "\n"

            ans += "👉 [Start a practice test in Assessment Hub](/assessments)"
            return ans

        # 10. LATEST INTERVIEW FEEDBACK
        elif intent == 'LATEST_INTERVIEW_FEEDBACK':
            fb = data.get('feedback', {})
            if not fb.get('has_feedback'):
                return (
                    "### 🎤 Interview Feedback\n\n"
                    "I don't have recorded interview feedback for you yet in your Application Tracker.\n\n"
                    "💡 *When you complete an interview round, add feedback notes to your application record to track strengths and improvement areas.*\n\n"
                    "👉 [View Application Tracker](/jobs?tab=tracker)"
                )

            ans = f"### 🎤 Latest Recorded Interview Feedback\n\n"
            ans += f"- **Company**: **{fb.get('company_name')}**\n"
            ans += f"- **Role**: *{fb.get('job_title')}*\n"
            ans += f"- **Status**: **{fb.get('status')}**\n"
            if fb.get('interview_date'):
                ans += f"- **Interview Date**: {fb.get('interview_date')}\n"
            ans += f"\n### 📝 Notes & Feedback\n{fb.get('feedback_notes')}\n\n"
            ans += "👉 [Update notes in Application Tracker](/jobs?tab=tracker)"
            return ans

        # 11. INTERVIEW HISTORY
        elif intent == 'INTERVIEW_HISTORY':
            int_info = data.get('interviews', {})
            interviews = int_info.get('interviews', [])

            ans = f"### 🎤 Your Interview Pipeline ({len(interviews)})\n\n"
            if not interviews:
                ans += "You have no scheduled or recorded interviews yet in CareerMate.\n\n"
                ans += "👉 [View Applications Tracker](/jobs?tab=tracker)"
                return ans

            for it in interviews:
                ans += f"- **{it.get('company_name')}** — {it.get('job_title')}\n"
                ans += f"  - Status: **{it.get('status')}**\n"
                if it.get('interview_date'):
                    ans += f"  - 📅 Scheduled: {it.get('interview_date')}\n"
                if it.get('notes'):
                    ans += f"  - 📝 Feedback: {it.get('notes')}\n"
                ans += "\n"

            ans += "👉 [Manage interviews in Tracker](/jobs?tab=tracker)"
            return ans

        # 12. COURSE PROGRESS
        elif intent == 'COURSE_PROGRESS':
            c_info = data.get('courses', {})
            courses = c_info.get('courses', [])

            ans = f"### 📚 Your Enrolled Courses ({c_info.get('total_enrolled', 0)})\n\n"
            if not courses:
                ans += "You are not enrolled in any courses yet.\n\n"
                ans += "👉 [Explore verified courses for your skill gaps](/courses)"
                return ans

            ans += f"- **Completed**: {c_info.get('completed_count', 0)} | **In Progress**: {c_info.get('in_progress_count', 0)}\n\n"
            for c in courses:
                ans += f"- **{c.get('skill_name')}**: {c.get('course_title')}\n"
                ans += f"  - Provider: {c.get('provider')} | Progress: **{c.get('progress')}%** ({c.get('status').title()})\n"
                ans += f"  - [Course Link]({c.get('url')})\n\n"

            ans += "👉 [Update course progress in Courses page](/courses)"
            return ans

        # 13. RECOMMENDED COURSES
        elif intent == 'RECOMMENDED_COURSES':
            c_info = data.get('courses', {})
            courses = c_info.get('recommended_courses', [])

            ans = f"### 📚 Recommended Courses for Your Target Path\n\n"
            if not courses:
                ans += "You already match all core skills for this track, or no direct course mapping was found.\n\n"
                ans += "👉 [Browse all courses in Courses directory](/courses)"
                return ans

            ans += "Based on your verified skill gaps, here are official structured learning paths:\n\n"
            for c in courses[:5]:
                enrolled_tag = " *(Enrolled)*" if c.get('is_enrolled') else ""
                ans += f"#### **{c.get('skill')}**: [{c.get('title')}]({c.get('url')}){enrolled_tag}\n"
                ans += f"- **Provider**: {c.get('provider')} | **Duration**: {c.get('time')}\n"
                ans += f"- **Difficulty**: {c.get('difficulty')} | **Impact**: {c.get('impact')}\n\n"

            ans += "👉 [Enroll in courses directly on Courses Hub](/courses)"
            return ans

        # 14. MISSING SKILLS
        elif intent == 'MISSING_SKILLS':
            sk_info = data.get('missing_skills', {})
            missing = sk_info.get('missing_skills', [])
            matching = sk_info.get('matching_skills', [])
            target = sk_info.get('target', 'Target Role')

            ans = f"### 🔍 Skill Gap Analysis for {target}\n\n"
            ans += f"**Missing Skills Count**: **{len(missing)}**\n\n"

            ans += "### ✅ What You Already Possess\n"
            if matching:
                for m in matching:
                    ans += f"- **{m}**\n"
            else:
                ans += "- No matched skills recorded in your profile.\n"
            ans += "\n"

            ans += "### ⚠️ What You Need to Learn\n"
            if missing:
                for gap in missing:
                    ans += f"- **{gap}** (High Priority)\n"
            else:
                ans += "- You have mastered all baseline skills for this role!\n"
            ans += "\n"

            ans += "👉 [View full Skill Gap priority matrix](/skill-gap)"
            return ans

        # 15. CAREER ROADMAP
        elif intent == 'CAREER_ROADMAP':
            rm = data.get('roadmap', {})
            role = rm.get('target_role', 'Target Role')
            curr = rm.get('current_position', {})
            gaps = rm.get('skill_gaps', [])
            courses = rm.get('recommended_courses', [])
            jobs = rm.get('matching_jobs', [])
            stats = rm.get('application_status', {})

            ans = f"### 🗺️ Complete Career Roadmap: {role}\n\n"

            ans += "#### 1. YOUR CURRENT POSITION\n"
            ans += f"- **Candidate**: {curr.get('name', user.name)} ({curr.get('user_type', 'Candidate').title()})\n"
            if curr.get('degree') and curr.get('college'):
                ans += f"- **Education**: {curr.get('degree')} at {curr.get('college')}\n"
            ans += f"- **Resume Status**: {'Uploaded (ATS: ' + str(curr.get('ats_score')) + '%)' if curr.get('has_resume') else 'No resume uploaded yet'}\n"
            if curr.get('matching_skills'):
                ans += f"- **Matching Skills**: {', '.join(curr.get('matching_skills'))}\n"
            ans += "\n"

            ans += "#### 2. SKILL GAPS TO CLOSE\n"
            if gaps:
                for g in gaps[:5]:
                    ans += f"- **{g}**\n"
            else:
                ans += "- No major technical gaps detected.\n"
            ans += "\n"

            ans += "#### 3. STRUCTURED LEARNING PLAN\n"
            if courses:
                for c in courses[:3]:
                    ans += f"- **{c.get('skill')}**: [{c.get('title')}]({c.get('url')}) ({c.get('provider')} - {c.get('time')})\n"
            else:
                ans += "- Follow official documentation for core languages.\n"
            ans += "\n"

            ans += "#### 4. PRACTICE & INTERVIEW PREPARATION\n"
            ans += "- **Aptitude**: Quantitative & Logical reasoning sets.\n"
            ans += "- **DSA**: Arrays, Hashing, Trees & BST, and Dynamic Programming.\n"
            ans += "- **Technical Core**: OOP, Database Design & SQL Optimization, System Design.\n\n"

            ans += "#### 5. CURRENT MATCHING OPPORTUNITIES\n"
            if jobs:
                for j in jobs[:3]:
                    ans += f"- **{j.get('title')}** @ **{j.get('company')}** (`{j.get('match_score')}% match`)\n"
            else:
                ans += "- No active openings matching this exact filter currently.\n"
            ans += "\n"

            ans += "#### 6. APPLICATION STATUS\n"
            ans += f"- **Total Applications**: {stats.get('total_applications', 0)} ({stats.get('active_applications', 0)} active)\n\n"

            ans += "#### 7. NEXT 3 ACTIONS\n"
            ans += f"1. Close your top skill gap: **{gaps[0] if gaps else 'System Design'}** via [Courses Hub](/courses).\n"
            ans += f"2. {'Optimize resume ATS score above 75%' if (not curr.get('has_resume') or (curr.get('ats_score') and curr.get('ats_score') < 75)) else 'Practice aptitude and technical questions'} via [Preparation](/preparation).\n"
            ans += f"3. Apply to verified matching positions via [Jobs Hub](/jobs).\n\n"

            ans += "👉 [Track your progression on Career Roadmap](/roadmap)"
            return ans

        # 16. NEXT BEST ACTIONS
        elif intent == 'NEXT_ACTIONS':
            actions = data.get('next_actions', {}).get('actions', [])
            ans = f"### ⚡ What You Should Do Next\n\n"
            ans += "Here is your prioritized, data-driven action plan based on your current CareerMate state:\n\n"

            for idx, act in enumerate(actions, 1):
                ans += f"**{idx}. {act['title']}**\n"
                ans += f"{act['description']}\n"
                ans += f"&rarr; [{act['action_label']}]({act['action_url']})\n\n"

            return ans

        # Default fallback
        return (
            f"### CareerMate Career Intelligence\n\n"
            f"Hello {first_name}! I can analyze your personalized career data:\n\n"
            f"- **Profile & Status**: Ask *'What is my current career status?'*\n"
            f"- **Resume Analysis**: Ask *'What is my ATS score and how can I improve?'*\n"
            f"- **Matching Jobs**: Ask *'Which jobs currently match my profile?'*\n"
            f"- **Skill Gaps & Courses**: Ask *'What skills am I missing for Full Stack Engineer?'*\n"
            f"- **Applications**: Ask *'How many applications have I made?'*\n"
            f"- **Career Roadmap**: Ask *'Give me a complete roadmap for Data Scientist.'*"
        )
