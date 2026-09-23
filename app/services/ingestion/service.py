from datetime import datetime
from app.extensions import db
from app.models.company import Company
from app.models.job import Job
from app.models.job_source import JobSource
from app.services.ingestion.arbeitnow_adapter import ArbeitnowAdapter
from app.services.ingestion.remotive_adapter import RemotiveAdapter
from app.services.ingestion.greenhouse_adapter import GreenhouseAdapter

# Verified official company career portals for core technology companies
OFFICIAL_CAREERS_PORTALS = {
    'Google': {'url': 'https://careers.google.com', 'website': 'https://about.google', 'industry': 'Technology & Internet', 'hq': 'Mountain View, CA'},
    'Amazon': {'url': 'https://www.amazon.jobs', 'website': 'https://www.aboutamazon.com', 'industry': 'Cloud & E-Commerce', 'hq': 'Seattle, WA'},
    'Microsoft': {'url': 'https://careers.microsoft.com', 'website': 'https://www.microsoft.com', 'industry': 'Software & Cloud Services', 'hq': 'Redmond, WA'},
    'TCS': {'url': 'https://www.tcs.com/careers', 'website': 'https://www.tcs.com', 'industry': 'IT Services & Consulting', 'hq': 'Mumbai, India'},
    'Infosys': {'url': 'https://www.infosys.com/careers.html', 'website': 'https://www.infosys.com', 'industry': 'IT Services & Digital Solutions', 'hq': 'Bengaluru, India'},
    'Accenture': {'url': 'https://www.accenture.com/careers', 'website': 'https://www.accenture.com', 'industry': 'Management & Technology Consulting', 'hq': 'Dublin, Ireland'},
    'Deloitte': {'url': 'https://www2.deloitte.com/careers', 'website': 'https://www.deloitte.com', 'industry': 'Professional Services & Advisory', 'hq': 'London, UK'},
    'IBM': {'url': 'https://www.ibm.com/careers', 'website': 'https://www.ibm.com', 'industry': 'Enterprise Technology & AI', 'hq': 'Armonk, NY'},
    'Wipro': {'url': 'https://careers.wipro.com', 'website': 'https://www.wipro.com', 'industry': 'IT Services & Consulting', 'hq': 'Bengaluru, India'},
    'Zoho': {'url': 'https://www.zoho.com/careers/', 'website': 'https://www.zoho.com', 'industry': 'Enterprise Software & SaaS', 'hq': 'Chennai, India'}
}

class IngestionService:
    """Service orchestrating real job ingestion from verified adapters."""
    
    def __init__(self):
        self.adapters = [
            ArbeitnowAdapter(),
            RemotiveAdapter(),
            GreenhouseAdapter()
        ]
        
    @classmethod
    def sync_all_sources(cls, limit_per_adapter=20):
        """Classmethod helper to instantiate and sync all adapters."""
        return cls().sync_all(limit_per_adapter=limit_per_adapter)

    def sync_all(self, limit_per_adapter=20):
        """Run all registered adapters and persist normalized jobs."""
        stats = {
            'synced_jobs': 0,
            'updated_jobs': 0,
            'companies_synced': 0,
            'sources': []
        }
        
        # 1. Update official metadata for established core companies
        self._ensure_verified_official_portals()
        
        # 2. Ingest from verified external adapters
        for adapter in self.adapters:
            source_stat = self._sync_adapter(adapter, limit=limit_per_adapter)
            stats['sources'].append(source_stat)
            stats['synced_jobs'] += source_stat.get('new_jobs', 0)
            stats['updated_jobs'] += source_stat.get('updated_jobs', 0)
            
        db.session.commit()
        return stats
        
    def _ensure_verified_official_portals(self):
        """Ensure core companies have verified official website and career portal URLs."""
        for comp_name, info in OFFICIAL_CAREERS_PORTALS.items():
            company = Company.query.filter_by(company_name=comp_name).first()
            if not company:
                company = Company(
                    company_name=comp_name,
                    industry=info['industry'],
                    official_website=info['website'],
                    official_careers_url=info['url'],
                    headquarters=info['hq'],
                    description=f"{comp_name} is a global industry leader with active engineering and placement tracks.",
                    source='Official Company Portal'
                )
                company.locations = [info['hq']]
                db.session.add(company)
            else:
                if not company.official_careers_url:
                    company.official_careers_url = info['url']
                if not company.official_website:
                    company.official_website = info['website']
                if not company.industry:
                    company.industry = info['industry']
                if not company.headquarters:
                    company.headquarters = info['hq']
                company.last_verified_at = datetime.utcnow()
                
        db.session.flush()

    def _sync_adapter(self, adapter, limit=20):
        stat = {
            'adapter_name': adapter.name,
            'new_jobs': 0,
            'updated_jobs': 0,
            'status': 'success'
        }
        
        # Track JobSource record
        source_rec = JobSource.query.filter_by(name=adapter.name).first()
        if not source_rec:
            source_rec = JobSource(
                name=adapter.name,
                source_type=adapter.source_type,
                base_url=adapter.base_url
            )
            db.session.add(source_rec)
            db.session.flush()
            
        try:
            raw_jobs = adapter.fetch_raw_jobs(limit=limit)
            for raw_item in raw_jobs:
                normalized = adapter.normalize_job(raw_item)
                if not normalized or not normalized.get('company') or not normalized.get('job'):
                    continue
                    
                comp_data = normalized['company']
                job_data = normalized['job']
                
                # 1. Find or create Company
                company = Company.query.filter(
                    (Company.company_name.ilike(comp_data['name'].strip()))
                ).first()
                
                if not company:
                    company = Company(
                        company_name=comp_data['name'].strip(),
                        logo_url=comp_data.get('logo_url'),
                        official_website=comp_data.get('official_website'),
                        official_careers_url=comp_data.get('official_careers_url'),
                        industry=comp_data.get('industry', 'Technology'),
                        description=comp_data.get('description'),
                        headquarters=comp_data.get('headquarters'),
                        source=comp_data.get('source', adapter.name),
                        last_verified_at=datetime.utcnow()
                    )
                    company.locations = comp_data.get('locations', ['Remote'])
                    db.session.add(company)
                    db.session.flush()
                else:
                    if comp_data.get('logo_url') and not company.logo_url:
                        company.logo_url = comp_data['logo_url']
                    if comp_data.get('official_careers_url') and not company.official_careers_url:
                        company.official_careers_url = comp_data['official_careers_url']
                    company.last_verified_at = datetime.utcnow()
                    
                # 2. Deduplication check for Job (company_id + external_job_id or title)
                ext_id = job_data['external_job_id']
                existing_job = Job.query.filter_by(
                    company_id=company.company_id,
                    external_job_id=ext_id
                ).first()
                
                if not existing_job:
                    # Fallback check by company + exact title
                    existing_job = Job.query.filter_by(
                        company_id=company.company_id,
                        title=job_data['title'],
                        source_platform=adapter.name
                    ).first()
                    
                if existing_job:
                    # Update status and freshness
                    existing_job.status = 'active'
                    existing_job.last_verified_at = datetime.utcnow()
                    if job_data.get('description') and not existing_job.description:
                        existing_job.description = job_data['description']
                    if job_data.get('skills') and not existing_job.skills:
                        existing_job.skills = job_data['skills']
                    stat['updated_jobs'] += 1
                else:
                    new_job = Job(
                        company_id=company.company_id,
                        external_job_id=ext_id,
                        title=job_data['title'],
                        career_area=job_data['career_area'],
                        description=job_data['description'],
                        responsibilities=job_data.get('responsibilities'),
                        required_qualifications=job_data.get('required_qualifications'),
                        preferred_qualifications=job_data.get('preferred_qualifications'),
                        location=job_data.get('location', 'Remote'),
                        country=job_data.get('country', 'Global'),
                        employment_type=job_data.get('employment_type', 'Full-time'),
                        work_mode=job_data.get('work_mode', 'Remote'),
                        experience_min=job_data.get('experience_min'),
                        experience_max=job_data.get('experience_max'),
                        salary_min=job_data.get('salary_min'),
                        salary_max=job_data.get('salary_max'),
                        currency=job_data.get('currency', 'USD'),
                        posted_at=job_data.get('posted_at', datetime.utcnow()),
                        application_url=job_data['application_url'],
                        source_url=job_data.get('source_url'),
                        source_platform=adapter.name,
                        status='active',
                        last_verified_at=datetime.utcnow()
                    )
                    new_job.skills = job_data.get('skills', [])
                    db.session.add(new_job)
                    stat['new_jobs'] += 1
                    
            source_rec.last_synced_at = datetime.utcnow()
            source_rec.status = 'active'
        except Exception as e:
            stat['status'] = f"error: {str(e)}"
            if source_rec:
                source_rec.status = 'degraded'
                
        return stat
