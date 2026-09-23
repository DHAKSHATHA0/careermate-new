import re
import html
from abc import ABC, abstractmethod
from app.utils.nlp_analyzer import NLPAnalyzer

SKILL_CANONICAL_MAP = {
    'js': 'JavaScript',
    'javascript': 'JavaScript',
    'ts': 'TypeScript',
    'typescript': 'TypeScript',
    'react': 'React',
    'reactjs': 'React',
    'react.js': 'React',
    'node': 'Node.js',
    'nodejs': 'Node.js',
    'node.js': 'Node.js',
    'python': 'Python',
    'py': 'Python',
    'django': 'Django',
    'flask': 'Flask',
    'fastapi': 'FastAPI',
    'postgres': 'PostgreSQL',
    'postgresql': 'PostgreSQL',
    'sql': 'SQL',
    'mysql': 'MySQL',
    'mongodb': 'MongoDB',
    'mongo': 'MongoDB',
    'redis': 'Redis',
    'docker': 'Docker',
    'k8s': 'Kubernetes',
    'kubernetes': 'Kubernetes',
    'aws': 'AWS',
    'amazon web services': 'AWS',
    'gcp': 'GCP',
    'google cloud': 'GCP',
    'azure': 'Azure',
    'ml': 'Machine Learning',
    'machine learning': 'Machine Learning',
    'ai': 'Artificial Intelligence',
    'deep learning': 'Deep Learning',
    'pytorch': 'PyTorch',
    'tensorflow': 'TensorFlow',
    'git': 'Git',
    'rest': 'REST APIs',
    'restful': 'REST APIs',
    'rest api': 'REST APIs',
    'rest apis': 'REST APIs',
    'graphql': 'GraphQL',
    'microservices': 'Microservices',
    'system design': 'System Design',
    'ci/cd': 'CI/CD',
    'linux': 'Linux',
    'java': 'Java',
    'c++': 'C++',
    'c#': 'C#',
    'golang': 'Go',
    'go': 'Go',
    'rust': 'Rust',
    'spark': 'Apache Spark',
    'hadoop': 'Hadoop',
    'tableau': 'Tableau',
    'power bi': 'Power BI',
    'excel': 'Excel'
}

CAREER_AREA_PATTERNS = [
    ('AI / Machine Learning', [r'\b(machine learning|deep learning|ml|ai|artificial intelligence|nlp|computer vision|llm|data scientist)\b']),
    ('Data Analytics', [r'\b(data analyst|data analytics|business intelligence|bi analyst|tableau|power bi|sql analyst)\b']),
    ('Cloud & DevOps', [r'\b(devops|sre|site reliability|cloud engineer|aws|kubernetes|infrastructure|platform engineer)\b']),
    ('Cybersecurity', [r'\b(security|cybersecurity|infosec|soc analyst|penetration|vulnerability)\b']),
    ('Product Management', [r'\b(product manager|product management|technical product manager|scrum master|agile coach)\b']),
    ('Design', [r'\b(ui/ux|ux designer|ui designer|product designer|visual designer)\b']),
    ('QA & Testing', [r'\b(qa|quality assurance|sdet|test automation|software tester)\b']),
    ('Software Engineering', [r'\b(software engineer|developer|backend|frontend|full stack|fullstack|web developer|core engineer|mobile developer|ios|android)\b'])
]

class BaseJobAdapter(ABC):
    """Abstract Base Class for verified external job source adapters."""
    
    def __init__(self, name, source_type, base_url):
        self.name = name
        self.source_type = source_type
        self.base_url = base_url
        self.nlp = NLPAnalyzer()
        
    @abstractmethod
    def fetch_raw_jobs(self, limit=20):
        """Fetch raw job records from verified external API or endpoint."""
        pass
        
    @abstractmethod
    def normalize_job(self, raw_item):
        """Normalize raw external record into standardized dict conforming to CareerMate Job schema."""
        pass

    def clean_text(self, text):
        """Sanitize HTML entities and tags from raw text."""
        if not text:
            return ""
        # Remove HTML tags
        clean = re.sub(r'<[^>]+>', ' ', text)
        clean = html.unescape(clean)
        # Normalize whitespace
        clean = re.sub(r'\s+', ' ', clean).strip()
        return clean

    def extract_and_normalize_skills(self, text, tags=None):
        """Extract and canonicalize technical skills from tags and job text."""
        extracted = set()
        
        # 1. Tags provided by source API
        if tags and isinstance(tags, list):
            for t in tags:
                clean_t = str(t).strip().lower()
                if clean_t in SKILL_CANONICAL_MAP:
                    extracted.add(SKILL_CANONICAL_MAP[clean_t])
                elif len(clean_t) > 1 and not clean_t.isdigit():
                    extracted.add(str(t).strip().title())

        # 2. Text keyword extraction via NLP
        if text:
            nlp_keywords = self.nlp.extract_keywords(text)
            for k in nlp_keywords:
                k_lower = k.lower().strip()
                if k_lower in SKILL_CANONICAL_MAP:
                    extracted.add(SKILL_CANONICAL_MAP[k_lower])
                elif len(k) >= 3 and k.istitle():
                    extracted.add(k)
                    
        # 3. Direct matching for high-priority technical skills in text
        text_lower = (text or "").lower()
        for k_term, canonical in SKILL_CANONICAL_MAP.items():
            pattern = r'\b' + re.escape(k_term) + r'\b'
            if re.search(pattern, text_lower):
                extracted.add(canonical)

        return sorted(list(extracted))

    def infer_career_area(self, title, description=""):
        """Deterministically deduce career category from job title and content."""
        search_target = f"{title} {description}".lower()
        for area_name, patterns in CAREER_AREA_PATTERNS:
            for pat in patterns:
                if re.search(pat, search_target):
                    return area_name
        return 'Software Engineering'
