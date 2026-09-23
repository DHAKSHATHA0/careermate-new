import requests
from datetime import datetime
from app.services.ingestion.base_adapter import BaseJobAdapter

class RemotiveAdapter(BaseJobAdapter):
    """Adapter for Remotive verified remote tech jobs API."""
    
    API_URL = "https://remotive.com/api/remote-jobs?limit=25"
    
    def __init__(self):
        super(RemotiveAdapter, self).__init__(
            name="Remotive",
            source_type="public_job_board",
            base_url="https://remotive.com"
        )
        
    def fetch_raw_jobs(self, limit=25):
        try:
            resp = requests.get(self.API_URL, headers={'User-Agent': 'CareerMate/1.0'}, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                return data.get('jobs', [])[:limit]
        except Exception as e:
            print(f"[RemotiveAdapter] Error fetching jobs: {e}")
        return []
        
    def normalize_job(self, raw_item):
        title = self.clean_text(raw_item.get('title', ''))
        company_name = self.clean_text(raw_item.get('company_name', ''))
        if not title or not company_name:
            return None
            
        description_raw = raw_item.get('description', '')
        description = self.clean_text(description_raw)
        
        tags = raw_item.get('tags', [])
        skills = self.extract_and_normalize_skills(description, tags=tags)
        
        career_area = self.infer_career_area(title, description)
        
        category = raw_item.get('category', '')
        if 'software' in category.lower():
            career_area = 'Software Engineering'
        elif 'data' in category.lower():
            career_area = 'Data Analytics'
        elif 'devops' in category.lower():
            career_area = 'Cloud & DevOps'
        elif 'design' in category.lower():
            career_area = 'Design'
        elif 'product' in category.lower():
            career_area = 'Product Management'
            
        location = raw_item.get('candidate_required_location', 'Worldwide / Remote')
        job_type = raw_item.get('job_type', 'full_time')
        emp_type = 'Full-time' if job_type == 'full_time' else ('Contract' if 'contract' in job_type else 'Full-time')
        
        # Parse salary if present
        salary_str = raw_item.get('salary', '')
        salary_min = None
        salary_max = None
        
        # Posted timestamp
        pub_date = raw_item.get('publication_date')
        posted_at = datetime.utcnow()
        if pub_date:
            try:
                posted_at = datetime.fromisoformat(pub_date.replace('Z', '+00:00'))
            except Exception:
                posted_at = datetime.utcnow()
                
        external_id = str(raw_item.get('id') or f"remotive-{company_name}-{title}")
        app_url = raw_item.get('url', f"https://remotive.com/remote-jobs/{external_id}")
        company_logo = raw_item.get('company_logo_url')
        
        return {
            'company': {
                'name': company_name,
                'logo_url': company_logo,
                'official_website': None,
                'official_careers_url': app_url,
                'industry': 'Software & Internet',
                'description': f"{company_name} is hiring for remote technology positions worldwide.",
                'headquarters': 'Remote First',
                'locations': [location] if location else ['Remote'],
                'source': self.name
            },
            'job': {
                'external_job_id': external_id,
                'title': title,
                'career_area': career_area,
                'description': description[:3500],
                'responsibilities': None,
                'required_qualifications': None,
                'preferred_qualifications': None,
                'skills': skills,
                'location': location,
                'country': 'Global',
                'employment_type': emp_type,
                'work_mode': 'Remote',
                'experience_min': None,
                'experience_max': None,
                'salary_min': salary_min,
                'salary_max': salary_max,
                'currency': 'USD',
                'posted_at': posted_at,
                'application_url': app_url,
                'source_url': app_url,
                'source_platform': self.name,
                'status': 'active'
            }
        }
