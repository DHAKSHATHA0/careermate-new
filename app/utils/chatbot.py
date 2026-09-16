import os
from app.models.company import Company
from app.models.question import Question

class ChatbotRAG:
    """RAG-style chatbot using local knowledge base from Companies/Questions tables and user context"""
    
    def __init__(self):
        self.openai_api_key = os.environ.get('OPENAI_API_KEY')
        if self.openai_api_key and ('placeholder' in self.openai_api_key or 'test' in self.openai_api_key):
            self.openai_api_key = None
    
    def get_knowledge_base(self):
        """Retrieve knowledge base from database"""
        companies = Company.query.all()
        knowledge = []
        
        for company in companies:
            company_info = {
                'company_name': company.company_name,
                'description': company.description,
                'eligibility': company.eligibility,
                'salary': company.salary,
                'selection_process': company.selection_process,
                'questions': []
            }
            
            # Add questions for this company
            questions = Question.query.filter_by(company_id=company.company_id).all()
            for q in questions:
                company_info['questions'].append({
                    'type': q.question_type,
                    'difficulty': q.difficulty_level,
                    'question': q.question,
                    'answer': q.answer
                })
            
            knowledge.append(company_info)
        
        return knowledge
    
    def format_knowledge_base(self, knowledge):
        """Format knowledge base into context string"""
        context = "Knowledge Base:\n\n"
        
        for company in knowledge:
            context += f"Company: {company['company_name']}\n"
            if company['description']:
                context += f"Description: {company['description']}\n"
            if company['eligibility']:
                context += f"Eligibility: {company['eligibility']}\n"
            if company['salary']:
                context += f"Salary: {company['salary']}\n"
            if company['selection_process']:
                context += f"Selection Process: {company['selection_process']}\n"
            
            if company['questions']:
                context += "Sample Questions:\n"
                for q in company['questions'][:3]:
                    context += f"  - [{q['type'].upper()}] {q['question']}\n"
                    if q['answer']:
                        context += f"    Answer: {q['answer']}\n"
            
            context += "\n"
        
        return context
    
    def _fallback_expert_response(self, user_message, knowledge_base):
        """Intelligent local career guidance when OpenAI key is not provided"""
        msg = user_message.lower()
        
        # Check company specific queries
        for comp in knowledge_base:
            c_name = comp['company_name'].lower()
            if c_name in msg:
                ans = f"### 🏢 {comp['company_name']} Career Overview\n\n"
                if comp['description']:
                    ans += f"**Overview**: {comp['description']}\n\n"
                if comp['eligibility']:
                    ans += f"**Eligibility**: {comp['eligibility']}\n\n"
                if comp['salary']:
                    ans += f"**Package / Compensation**: {comp['salary']}\n\n"
                if comp['selection_process']:
                    ans += f"**Selection Process**: {comp['selection_process']}\n\n"
                if comp['questions']:
                    ans += "**Sample Interview Questions**:\n"
                    for q in comp['questions']:
                        ans += f"- **[{q['type'].title()}]** {q['question']}\n"
                return ans
                
        # Handle CareerMate core prompts
        if "ready for this job" in msg or "am i ready" in msg or "job readiness" in msg:
            return (
                "### 🎯 Evaluating Your Job Readiness\n\n"
                "To determine if you're ready for your target position:\n\n"
                "1. **Check Your ATS Resume Score**: Visit the **Resume Analyzer** (`/resume/analyzer`) to verify your resume achieves an ATS compatibility score of 75%+.\n"
                "2. **Run Job Fit Analysis**: Use **Job Fit Analysis** (`/job-fit`) against target job descriptions to identify exact keyword alignment.\n"
                "3. **Address Priority Skill Gaps**: Check your **Skill Gap Analysis** (`/skill-gap`) to ensure you possess all high-priority technical requirements.\n\n"
                "💡 *Tip: Having 2-3 demonstrated portfolio projects that showcase end-to-end deployment dramatically elevates candidate conversion.*"
            )
            
        elif "skill gap" in msg or "biggest skill" in msg or "what am i missing" in msg:
            return (
                "### 🔍 Identifying & Bridging Skill Gaps\n\n"
                "CareerMate analyzes the difference between your current profile and industry requirements:\n\n"
                "- **High Priority**: Core language fluency (e.g. Python, SQL, Modern JavaScript) and REST API principles.\n"
                "- **Medium Priority**: Architecture frameworks (React/Node/Django), relational schema design, and containerization (Docker).\n"
                "- **Low Priority**: Advanced orchestration (Kubernetes) and microservice clustering.\n\n"
                "👉 Visit **Skill Gap Analysis** (`/skill-gap`) to view your real personalized priority matrix."
            )
            
        elif "which jobs" in msg or "should i apply" in msg or "recommend" in msg:
            comp_list = ", ".join([c['company_name'] for c in knowledge_base]) if knowledge_base else "Google, TCS, Infosys"
            return (
                "### 💼 Recommended Job Opportunities\n\n"
                f"Based on our active company database ({comp_list}):\n\n"
                "- **Service & Consulting Leaders (e.g. TCS, Infosys)**: Ideal for candidates seeking structured onboarding, aptitude assessments, and widespread tech opportunities.\n"
                "- **Product & Tech Leaders (e.g. Google)**: Requires strong algorithmic problem-solving, clean code architecture, and deep system design skills.\n\n"
                "👉 Explore all matched positions on your **Job Recommendations** page (`/jobs`)."
            )
            
        elif "what should i learn" in msg or "learn next" in msg or "courses" in msg:
            return (
                "### 📚 Recommended Learning Track\n\n"
                "Based on the most in-demand software engineering competencies:\n\n"
                "1. **SQL & Data Persistence**: Master indexing, JOIN optimization, and transactions via PostgreSQL documentation.\n"
                "2. **Containerization (Docker)**: Learn to containerize your backend and frontend services.\n"
                "3. **Cloud Essentials (AWS/GCP)**: Understand serverless compute, storage buckets, and IAM roles.\n\n"
                "👉 Check your dedicated **Learning Recommendations** (`/learning`) for direct tutorials and estimated completion times."
            )
            
        elif "improve my resume" in msg or "resume" in msg or "ats" in msg:
            return (
                "### 📄 Resume Optimization Best Practices\n\n"
                "Here are actionable ways to enhance your ATS score:\n\n"
                "- **Use Active Action Verbs**: Start bullet points with verbs like *Architected*, *Implemented*, *Optimized*, *Reduced* rather than passive statements.\n"
                "- **Quantify Outcomes**: Include metrics (e.g., *'Reduced API response latency by 35%'*, *'Handled 10k+ requests'*).\n"
                "- **Standardize Sections**: Clearly demarcate *Experience*, *Education*, *Projects*, and *Skills*.\n"
                "- **Target Keywords**: Include relevant tools and libraries without keyword stuffing.\n\n"
                "👉 Upload your resume in **Resume Analyzer** (`/resume/analyzer`) for immediate real feedback."
            )
            
        elif "roadmap" in msg or "where should i go" in msg:
            return (
                "### 🗺️ Your Career Roadmap Journey\n\n"
                "The structured path from foundation to career achievement:\n\n"
                "1. **Current Profile**: Baseline skills & preferences established.\n"
                "2. **Core Skills**: Fluency in algorithms and core languages.\n"
                "3. **Advanced Skills**: Modern framework mastery & database design.\n"
                "4. **Projects**: Full-stack applications with authenticated databases.\n"
                "5. **Deployment**: Containerized services deployed to cloud infrastructure.\n"
                "6. **Interview Preparation**: Aptitude & technical problem sets.\n"
                "7. **Job Ready**: ATS-optimized resume & targeted applications.\n"
                "8. **Target Career**: Transition into your dream engineering role.\n\n"
                "👉 Track your live progress on the **Career Roadmap** (`/roadmap`) page."
            )
            
        else:
            return (
                f"### CareerMate Intelligence\n\n"
                f"I'm here to assist with your career direction. You can ask me about:\n\n"
                f"- **Company Intelligence**: Eligibility, hiring processes, salary packages, and practice questions for {', '.join([c['company_name'] for c in knowledge_base])}.\n"
                f"- **Resume Guidance**: Strategies to maximize ATS scores and highlight achievements.\n"
                f"- **Skill Priorities**: What technologies to learn next for your target role.\n"
                f"- **Career Progression**: How to complete your roadmap milestones."
            )

    def generate_response(self, user_message, knowledge_base_context):
        """Generate response using LLM API or structured local knowledge"""
        knowledge = self.get_knowledge_base()
        
        if self.openai_api_key:
            try:
                from openai import OpenAI
                client = OpenAI(api_key=self.openai_api_key)
                system_prompt = f"""You are CareerMate's AI Career Intelligence Assistant. 
Tagline: "Know your fit. Find your gap. Build your career."
Ground answers in this company & platform context:
{knowledge_base_context}

Be encouraging, professional, concise, and provide actionable markdown formatting with clear headings and bullet points."""
                
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message}
                    ],
                    temperature=0.3,
                    max_tokens=600
                )
                response_text = response.choices[0].message.content
            except Exception as e:
                print(f"OpenAI call failed, falling back to local intelligence: {e}")
                response_text = self._fallback_expert_response(user_message, knowledge)
        else:
            response_text = self._fallback_expert_response(user_message, knowledge)
            
        return {
            'message': user_message,
            'response': response_text,
            'sources': self._extract_sources(user_message, knowledge_base_context)
        }
    
    def _extract_sources(self, user_message, context):
        """Extract relevant sources from knowledge base"""
        sources = []
        user_lower = user_message.lower()
        
        if 'google' in user_lower:
            sources.append('Google Company Intelligence')
        if 'tcs' in user_lower:
            sources.append('TCS Company Intelligence')
        if 'infosys' in user_lower:
            sources.append('Infosys Company Intelligence')
        if 'resume' in user_lower or 'ats' in user_lower:
            sources.append('CareerMate Resume Engine')
        if 'skill' in user_lower:
            sources.append('CareerMate Skill Graph')
        if 'roadmap' in user_lower:
            sources.append('Career Progression Framework')
            
        return sources if sources else ['CareerMate Knowledge Base']
