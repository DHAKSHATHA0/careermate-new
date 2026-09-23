import requests
from datetime import datetime
from app.services.ingestion.base_adapter import BaseJobAdapter

class GreenhouseAdapter(BaseJobAdapter):
    """Adapter for official public Greenhouse ATS boards (e.g., gitlab, automattic)."""
    
    BOARDS = [
        {'token': 'gitlab', 'company_name': 'GitLab', 'industry': 'DevOps & Cloud Software', 'hq': 'San Francisco, CA (All Remote)'},
        {'token': 'automattic', 'company_name': 'Automattic', 'industry': 'Web Publishing & Software', 'hq': 'San Francisco, CA (Distributed)'}
    ]
    
    def __init__(self):
        super(GreenhouseAdapter, self).__init__(
            name="Greenhouse ATS",
            source_type="ats_api",
            base_url="https://boards-api.greenhouse.io"
        )
        
    def fetch_raw_jobs(self, limit=15):
        all_jobs = []
        for board in self.BOARDS:
            url = f"https://boards-api.greenhouse.io/v1/boards/{board['token']}/jobs?content=true"
            try:
                resp = requests.get(url, headers={'User-Agent': 'CareerMate/1.0'}, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    jobs = data.get('jobs', [])
                    for j in jobs[:limit]:
                        j['_board_meta'] = board
                        all_jobs.append(j)
            except Exception as e:
                print(f"[GreenhouseAdapter] Error fetching for {board['token']}: {e}")
        return all_jobs
        
    def normalize_job(self, raw_item):
        board_meta = raw_item.get('_board_meta', {})
        company_name = board_meta.get('company_name', 'Tech Company')
        title = self.clean_text(raw_item.get('title', ''))
        if not title:
            return None
            
        content_raw = raw_item.get('content', '')
        description = self.clean_text(content_raw)
        
        # Skills & Career Area
        skills = self.extract_and_normalize_skills(description)
        career_area = self.infer_career_area(title, description)
        
        location_obj = raw_item.get('location', {})
        location_name = location_obj.get('name', 'Remote') if isinstance(location_obj, dict) else str(location_obj)
        if not location_name:
            location_name = 'Remote'
            
        is_remote = 'remote' in location_name.lower() or 'remote' in title.lower()
        work_mode = 'Remote' if is_remote else 'Hybrid'
        
        updated_at_str = raw_item.get('updated_at')
        posted_at = datetime.utcnow()
        if updated_at_str:
            try:
                posted_at = datetime.fromisoformat(updated_at_str.replace('Z', '+00:00'))
            except Exception:
                posted_at = datetime.utcnow()
                
        external_id = str(raw_item.get('id'))
        app_url = raw_item.get('absolute_url', f"https://boards.greenhouse.io/{board_meta.get('token', 'careers')}/jobs/{external_id}")
        
        return {
            'company': {
                'name': company_name,
                'official_website': f"https://www.{board_meta.get('token', 'company')}.com",
                'official_careers_url': f"https://boards.greenhouse.io/{board_meta.get('token', 'careers')}",
                'industry': board_meta.get('industry', 'Technology'),
                'description': f"{company_name} is an open, global technology leader hiring world-class talent.",
                'headquarters': board_meta.get('hq', 'Global'),
                'locations': [location_name],
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
                'location': location_name,
                'country': 'Global',
                'employment_type': 'Full-time',
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
