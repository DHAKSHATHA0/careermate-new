"""
CareerMate Multimodal Image Intelligence & OCR Pipeline
Provides computer vision preprocessing, OCR extraction, and semantic document classification
for career-related images (job descriptions, assessment results, resumes, interview feedback, certificates).
"""

import os
import re
import json
import logging
import numpy as np
from PIL import Image

try:
    import cv2
except ImportError:
    cv2 = None

try:
    import pytesseract
    # Check default Windows Tesseract installations if not already in PATH
    possible_tesseract_paths = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        os.path.expanduser(r"~\AppData\Local\Programs\Tesseract-OCR\tesseract.exe")
    ]
    for p in possible_tesseract_paths:
        if os.path.exists(p):
            pytesseract.pytesseract.tesseract_cmd = p
            break
except ImportError:
    pytesseract = None

from app.services.career_tools import CareerTools, SKILL_LEARNING_RESOURCES
from app.utils.recommendations import DOMAIN_ROLE_SKILLS

logger = logging.getLogger(__name__)

# Known skill vocabulary for entity extraction
ALL_KNOWN_SKILLS = [
    'Python', 'JavaScript', 'TypeScript', 'React', 'Angular', 'Vue', 'Node.js',
    'Django', 'Flask', 'FastAPI', 'Java', 'Spring Boot', 'C++', 'C#', '.NET',
    'SQL', 'PostgreSQL', 'MySQL', 'MongoDB', 'Redis', 'Docker', 'Kubernetes',
    'AWS', 'Azure', 'GCP', 'Git', 'REST APIs', 'GraphQL', 'Microservices',
    'Machine Learning', 'Deep Learning', 'TensorFlow', 'PyTorch', 'Data Science',
    'Pandas', 'NumPy', 'Power BI', 'Tableau', 'Excel', 'Statistics', 'System Design',
    'Algorithms', 'Data Structures', 'Linux', 'CI/CD', 'HTML', 'CSS'
]


class ImageIntelligence:
    """Computer Vision, OCR, and career intelligence processing pipeline."""

    @staticmethod
    def preprocess_image(image_path: str) -> np.ndarray:
        """
        OpenCV image preprocessing pipeline:
        Resizing, grayscale conversion, bilateral denoising, and adaptive contrast enhancement (CLAHE).
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image not found at {image_path}")

        if cv2 is not None:
            # Read image
            img = cv2.imread(image_path)
            if img is None:
                # Attempt PIL read and convert to cv2 format
                pil_img = Image.open(image_path).convert('RGB')
                img = np.array(pil_img)[:, :, ::-1]

            # Resize if excessively large while preserving aspect ratio
            h, w = img.shape[:2]
            max_dim = 1800
            if max(h, w) > max_dim:
                scale = max_dim / float(max(h, w))
                img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)

            # Grayscale conversion
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            # Denoise
            denoised = cv2.bilateralFilter(gray, 9, 75, 75)

            # Contrast enhancement with CLAHE
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(denoised)

            return enhanced
        else:
            # PIL Fallback
            pil_img = Image.open(image_path).convert('L')
            return np.array(pil_img)

    @staticmethod
    def extract_text(image_path: str) -> dict:
        """
        Extract text using Tesseract OCR with OpenCV preprocessed image.
        Returns extracted text and confidence status.
        """
        if not os.path.exists(image_path):
            return {'text': '', 'success': False, 'message': 'Image file missing.'}

        try:
            preprocessed = ImageIntelligence.preprocess_image(image_path)

            text = ""
            if pytesseract is not None:
                try:
                    # Run Tesseract OCR with layout analysis
                    custom_config = r'--oem 3 --psm 6'
                    text = pytesseract.image_to_string(preprocessed, config=custom_config)
                    if not text.strip():
                        # Try standard PSM 3 mode
                        text = pytesseract.image_to_string(preprocessed)
                except Exception as t_err:
                    logger.info(f"Tesseract binary execution note: {t_err}")

            if not text.strip():
                # Fallback PIL OCR attempt
                pil_img = Image.open(image_path)
                try:
                    text = pytesseract.image_to_string(pil_img) if pytesseract else ""
                except Exception:
                    text = ""

            cleaned_text = text.strip()
            return {
                'text': cleaned_text,
                'success': bool(cleaned_text),
                'word_count': len(cleaned_text.split()) if cleaned_text else 0
            }
        except Exception as e:
            logger.error(f"Image text extraction error: {e}")
            return {
                'text': '',
                'success': False,
                'error': str(e)
            }

    @staticmethod
    def classify_and_extract_career_data(ocr_text: str, user_id: int) -> dict:
        """
        Classify document intent and extract structured entities (Skills, Scores, Roles, Companies).
        Integrates with authenticated CareerMate profile and recommendation data.
        """
        t_lower = ocr_text.lower() if ocr_text else ""

        # 1. Identify skills mentioned in image
        extracted_skills = []
        for sk in ALL_KNOWN_SKILLS:
            # Word boundary regex search
            pattern = r'\b' + re.escape(sk.lower()) + r'\b'
            if re.search(pattern, t_lower):
                extracted_skills.append(sk)

        # 2. Classify Document Type
        doc_type = 'general_career_document'
        confidence = 'high' if len(ocr_text.split()) > 15 else 'low'

        # Check for Job Description
        jd_keywords = ['job description', 'responsibilities', 'requirements', 'qualifications', 'role', 'experience required', 'full-time', 'skills required', 'apply now']
        if any(k in t_lower for k in jd_keywords) or (len(extracted_skills) >= 3 and ('engineer' in t_lower or 'developer' in t_lower or 'analyst' in t_lower)):
            doc_type = 'job_description'

        # Check for Assessment Result
        elif any(k in t_lower for k in ['assessment', 'score', 'quiz', 'test result', 'marks', 'percentage', 'passed', 'failed', 'accuracy', 'questions answered']):
            doc_type = 'assessment_result'

        # Check for Interview Feedback
        elif any(k in t_lower for k in ['interview feedback', 'interview evaluation', 'interviewer', 'round 1', 'round 2', 'technical round', 'hiring manager']):
            doc_type = 'interview_feedback'

        # Check for Resume Screenshot
        elif any(k in t_lower for k in ['curriculum vitae', 'education', 'gpa', 'cgpa', 'work experience', 'projects', 'summary of qualifications']) and len(extracted_skills) >= 3:
            doc_type = 'resume_screenshot'

        # Check for Certificate
        elif any(k in t_lower for k in ['certificate of completion', 'has successfully completed', 'issued on', 'certified in', 'credential id']):
            doc_type = 'certificate'

        # Check for Coding / DSA Problem
        elif any(k in t_lower for k in ['example 1:', 'constraints:', 'input:', 'output:', 'time complexity', 'space complexity', 'given an array', 'given a string']):
            doc_type = 'coding_problem'

        # 3. Extract specific metrics
        # Scores (e.g. 85%, 17/20, 62/100)
        score_match = re.search(r'(\b\d{1,3})\s*%', ocr_text)
        fraction_match = re.search(r'(\b\d{1,3})\s*/\s*(\d{1,3})\b', ocr_text)
        detected_score = None
        if score_match:
            detected_score = f"{score_match.group(1)}%"
        elif fraction_match:
            detected_score = f"{fraction_match.group(1)}/{fraction_match.group(2)}"

        # Target role extraction
        detected_role = None
        role_candidates = ['Full Stack Engineer', 'Software Engineer', 'Data Analyst', 'Data Scientist', 'AI/ML Engineer', 'Cloud & DevOps Engineer', 'Frontend Developer', 'Backend Developer']
        for r in role_candidates:
            if r.lower() in t_lower:
                detected_role = r
                break

        # Company extraction
        detected_company = None
        company_candidates = ['Google', 'TCS', 'Infosys', 'Microsoft', 'Amazon', 'Meta', 'Stripe', 'Figma', 'Adobe', 'Oracle', 'IBM', 'Accenture', 'Wipro']
        for c in company_candidates:
            if c.lower() in t_lower:
                detected_company = c
                break

        # 4. Correlate with authenticated user data
        profile = CareerTools.get_user_profile(user_id)
        user_skills_set = set(s.lower() for s in profile.get('skills', []))
        resume = CareerTools.get_resume_summary(user_id)
        if resume.get('extracted_skills'):
            for rsk in resume.get('extracted_skills'):
                user_skills_set.add(rsk.lower())

        matching_skills = [s for s in extracted_skills if s.lower() in user_skills_set]
        missing_skills = [s for s in extracted_skills if s.lower() not in user_skills_set]

        # Recommended courses for missing skills
        recommended_courses = []
        for ms in missing_skills:
            res = SKILL_LEARNING_RESOURCES.get(ms)
            if res:
                recommended_courses.append({
                    'skill': ms,
                    'title': f"Mastering {ms}: {res['type']}",
                    'provider': res['provider'],
                    'url': res['url'],
                    'time': res['time']
                })

        return {
            'doc_type': doc_type,
            'confidence': confidence,
            'extracted_skills': extracted_skills,
            'matching_skills': matching_skills,
            'missing_skills': missing_skills,
            'recommended_courses': recommended_courses[:4],
            'detected_score': detected_score,
            'detected_role': detected_role,
            'detected_company': detected_company,
            'ocr_word_count': len(ocr_text.split()) if ocr_text else 0,
            'has_extracted_data': bool(extracted_skills or detected_score or detected_role or detected_company or len(ocr_text.strip()) > 20)
        }
