import requests
from datetime import datetime
from app.services.ingestion.base_adapter import BaseJobAdapter

class ArbeitnowAdapter(BaseJobAdapter):
    """Adapter for Arbeitnow verified tech jobs API."""
    
    API_URL = "https://www.arbeitnow.com/api/job-board-api"
    
    def __init__(self):
        super(ArbeitnowAdapter, self).__init__(
            name="Arbeitnow",
            source_type="public_job_board",
            base_url="https://www.arbeitnow.com"
        )
        
    def fetch_raw_jobs(self, limit=20):
        try:
            resp = requests.get(self.API_URL, headers={'User-Agent': 'CareerMate/1.0'}, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                return data.get('data', [])[:limit]
        except Exception as e:
            print(f"[ArbeitnowAdapter] Error fetching jobs: {e}")
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
        
        location = raw_item.get('location', 'Remote')
        is_remote = raw_item.get('remote', False)
        work_mode = 'Remote' if is_remote else ('Hybrid' if 'hybrid' in location.lower() else 'On-site')
        
        # Posted timestamp
        created_at_ts = raw_item.get('created_at')
        posted_at = datetime.utcnow()
        if created_at_ts:
            try:
                if isinstance(created_at_ts, (int, float)):
                    posted_at = datetime.utcfromtimestamp(created_at_ts)
                else:
                    posted_at = datetime.fromisoformat(str(created_at_ts).replace('Z', '+00:00'))
            except Exception:
                posted_at = datetime.utcnow()
                
        external_id = str(raw_item.get('slug') or raw_item.get('id') or f"{company_name}-{title}")
        app_url = raw_item.get('url', f"https://www.arbeitnow.com/jobs/{external_id}")
        
        return {
            'company': {
                'name': company_name,
                'official_website': None,
                'official_careers_url': app_url,
                'industry': 'Technology',
                'description': f"Active employer offering engineering & tech positions.",
                'headquarters': location if location != 'Remote' else None,
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
                'employment_type': 'Full-time' if 'part' not in title.lower() else 'Part-time',
                'work_mode': work_mode,
                'experience_min': None,
                'experience_max': None,
                'salary_min': None,
                'salary_max': None,
                'currency': 'USD',
                'posted_at': posted_at,
                'application_url': app_url,
                'source_url': app_url,
                'source_platform': self.name,
                'status': 'active'
            }
        }
