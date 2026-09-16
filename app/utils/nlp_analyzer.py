import re
import spacy
from collections import Counter

class NLPAnalyzer:
    """NLP analysis for resume content"""
    
    def __init__(self):
        try:
            self.nlp = spacy.load('en_core_web_sm')
        except OSError:
            raise Exception("spaCy model not found. Run: python -m spacy download en_core_web_sm")
    
    # Common technical keywords by domain
    TECHNICAL_KEYWORDS = {
        'web_dev': ['html', 'css', 'javascript', 'react', 'vue', 'angular', 'nodejs', 'express', 'django', 'flask', 'rest', 'api', 'responsive', 'bootstrap'],
        'data_science': ['python', 'r', 'sql', 'pandas', 'numpy', 'matplotlib', 'seaborn', 'scikit-learn', 'tensorflow', 'keras', 'data analysis', 'visualization'],
        'ml': ['machine learning', 'deep learning', 'neural networks', 'tensorflow', 'pytorch', 'scikit-learn', 'nlp', 'computer vision', 'classification', 'regression'],
        'cloud': ['aws', 'azure', 'gcp', 'docker', 'kubernetes', 'ci/cd', 'jenkins', 'devops', 'terraform', 'cloudformation', 'serverless'],
        'core': ['c++', 'java', 'system design', 'algorithms', 'data structures', 'oops', 'design patterns', 'multithreading', 'memory management']
    }
    
    # Common soft skills
    SOFT_SKILLS = ['communication', 'leadership', 'teamwork', 'problem solving', 'time management', 'critical thinking', 'collaboration', 'adaptability']
    
    # Grammar issues patterns
    GRAMMAR_PATTERNS = {
        'passive_voice': r'\b(was|were|is|are|been|be)\s+\w+ed\b',
        'weak_verbs': r'\b(did|made|got|went|said|tried)\b',
        'repeated_words': r'\b(\w+)\s+\1\b'
    }
    
    def extract_keywords(self, text):
        """Extract technical keywords from resume"""
        text_lower = text.lower()
        keywords = []
        
        # Extract technical keywords
        for domain, keywords_list in self.TECHNICAL_KEYWORDS.items():
            for keyword in keywords_list:
                if keyword in text_lower:
                    keywords.append(keyword)
        
        # Extract soft skills
        for skill in self.SOFT_SKILLS:
            if skill in text_lower:
                keywords.append(skill)
        
        # Remove duplicates and return
        return list(set(keywords))
    
    def check_grammar_issues(self, text):
        """Check for common grammar issues"""
        issues = []
        
        # Check for passive voice
        passive_matches = re.findall(self.GRAMMAR_PATTERNS['passive_voice'], text, re.IGNORECASE)
        if passive_matches:
            issues.append({
                'type': 'Passive Voice',
                'count': len(passive_matches),
                'suggestion': 'Use active voice for stronger impact (e.g., "Developed" instead of "Was developed")'
            })
        
        # Check for weak verbs
        weak_matches = re.findall(self.GRAMMAR_PATTERNS['weak_verbs'], text, re.IGNORECASE)
        if weak_matches:
            issues.append({
                'type': 'Weak Verbs',
                'count': len(weak_matches),
                'suggestion': 'Replace weak verbs with action verbs (e.g., "Implemented", "Designed", "Optimized")'
            })
        
        # Check for repeated words
        repeated_matches = re.findall(self.GRAMMAR_PATTERNS['repeated_words'], text, re.IGNORECASE)
        if repeated_matches:
            issues.append({
                'type': 'Repeated Words',
                'count': len(repeated_matches),
                'suggestion': 'Avoid repeating the same word in close proximity'
            })
        
        return issues
    
    def analyze_formatting(self, text):
        """Analyze resume formatting"""
        issues = []
        lines = text.split('\n')
        
        # Check for very long lines (likely formatting issues)
        long_lines = [line for line in lines if len(line) > 100]
        if len(long_lines) > len(lines) * 0.3:
            issues.append({
                'type': 'Line Length',
                'severity': 'medium',
                'suggestion': 'Many lines are very long. Consider breaking them into shorter lines for better readability.'
            })
        
        # Check for consistent spacing
        empty_lines = [line for line in lines if line.strip() == '']
        if len(empty_lines) < len(lines) * 0.1:
            issues.append({
                'type': 'Spacing',
                'severity': 'low',
                'suggestion': 'Add more white space between sections for better readability.'
            })
        
        # Check for section headers (common resume sections)
        sections = ['experience', 'education', 'skills', 'projects', 'certifications', 'awards']
        found_sections = sum(1 for section in sections if section in text.lower())
        
        if found_sections < 2:
            issues.append({
                'type': 'Structure',
                'severity': 'high',
                'suggestion': 'Resume should have clear sections (Experience, Education, Skills, etc.)'
            })
        
        return issues
    
    def extract_entities(self, text):
        """Extract named entities (companies, locations, etc.)"""
        doc = self.nlp(text[:1000000])  # Limit to first 1M chars for performance
        
        entities = {
            'organizations': [],
            'locations': [],
            'dates': []
        }
        
        for ent in doc.ents:
            if ent.label_ == 'ORG':
                entities['organizations'].append(ent.text)
            elif ent.label_ == 'GPE':
                entities['locations'].append(ent.text)
            elif ent.label_ == 'DATE':
                entities['dates'].append(ent.text)
        
        # Remove duplicates
        entities['organizations'] = list(set(entities['organizations']))
        entities['locations'] = list(set(entities['locations']))
        entities['dates'] = list(set(entities['dates']))
        
        return entities
