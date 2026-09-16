from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

class SimilarityScorer:
    """Calculate resume-to-job similarity using TF-IDF and cosine similarity"""
    
    def __init__(self):
        self.vectorizer = TfidfVectorizer(
            max_features=500,
            stop_words='english',
            ngram_range=(1, 2),
            min_df=1,
            max_df=0.9
        )
    
    def calculate_similarity(self, resume_text, job_description):
        """
        Calculate similarity between resume and job description
        Returns: similarity score (0-100)
        """
        if not resume_text or not job_description:
            return 0
        
        try:
            # Vectorize both texts
            texts = [resume_text, job_description]
            tfidf_matrix = self.vectorizer.fit_transform(texts)
            
            # Calculate cosine similarity
            similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
            
            # Convert to percentage (0-100)
            score = int(similarity * 100)
            
            return score
        except Exception as e:
            print(f"Error calculating similarity: {str(e)}")
            return 0
    
    def extract_missing_keywords(self, resume_text, job_description):
        """
        Extract keywords from job description that are missing in resume
        Returns: list of missing keywords
        """
        # Convert to lowercase for comparison
        resume_lower = resume_text.lower()
        job_lower = job_description.lower()
        
        # Extract words from job description
        job_words = set(job_lower.split())
        resume_words = set(resume_lower.split())
        
        # Find missing words (in job but not in resume)
        missing = job_words - resume_words
        
        # Filter out common stop words and short words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'from', 'is', 'are', 'was', 'were', 'be', 'been', 'being'}
        missing = [word for word in missing if word not in stop_words and len(word) > 2]
        
        # Sort by frequency in job description
        missing_sorted = sorted(missing, key=lambda x: job_lower.count(x), reverse=True)
        
        return missing_sorted[:15]  # Return top 15 missing keywords
    
    def get_matching_keywords(self, resume_text, job_description):
        """
        Extract keywords that appear in both resume and job description
        Returns: list of matching keywords
        """
        resume_lower = resume_text.lower()
        job_lower = job_description.lower()
        
        # Extract words from job description
        job_words = set(job_lower.split())
        resume_words = set(resume_lower.split())
        
        # Find matching words
        matching = job_words & resume_words
        
        # Filter out common stop words and short words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'from', 'is', 'are', 'was', 'were', 'be', 'been', 'being'}
        matching = [word for word in matching if word not in stop_words and len(word) > 2]
        
        return sorted(matching)
    
    def calculate_ats_score(self, resume_text):
        """
        Calculate ATS (Applicant Tracking System) score
        Based on: formatting, keywords, structure
        Returns: score (0-100)
        """
        score = 0
        
        # Check for common sections (20 points)
        sections = ['experience', 'education', 'skills', 'projects']
        found_sections = sum(1 for section in sections if section in resume_text.lower())
        score += (found_sections / len(sections)) * 20
        
        # Check for contact information (15 points)
        contact_patterns = {
            'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            'phone': r'\b\d{10}\b|\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
            'linkedin': r'linkedin\.com'
        }
        
        import re
        contact_found = sum(1 for pattern in contact_patterns.values() if re.search(pattern, resume_text))
        score += (contact_found / len(contact_patterns)) * 15
        
        # Check for action verbs (20 points)
        action_verbs = ['developed', 'designed', 'implemented', 'managed', 'led', 'created', 'built', 'optimized', 'improved', 'achieved']
        action_verbs_found = sum(1 for verb in action_verbs if verb in resume_text.lower())
        score += min((action_verbs_found / len(action_verbs)) * 20, 20)
        
        # Check for quantifiable achievements (20 points)
        quantifiable_patterns = [
            r'\d+%',  # Percentages
            r'\$\d+',  # Money
            r'\d+\s*(hours|days|weeks|months|years)',  # Time
            r'\d+\s*(projects|clients|users|servers)'  # Quantities
        ]
        
        quantifiable_found = sum(1 for pattern in quantifiable_patterns if re.search(pattern, resume_text))
        score += (quantifiable_found / len(quantifiable_patterns)) * 20
        
        # Check for technical keywords (15 points)
        tech_keywords = ['python', 'java', 'javascript', 'sql', 'aws', 'docker', 'git', 'api', 'database', 'html', 'css']
        tech_found = sum(1 for keyword in tech_keywords if keyword in resume_text.lower())
        score += min((tech_found / len(tech_keywords)) * 15, 15)
        
        # Check for proper formatting (10 points)
        lines = resume_text.split('\n')
        if len(lines) > 10:  # Reasonable length
            score += 10
        
        return min(int(score), 100)
