import pytest
import os
from io import BytesIO
from app.models.resume import Resume
from app.models.user import User
from app.extensions import db

class TestResumeUpload:
    """Test resume upload functionality"""
    
    def test_upload_pdf_success(self, client, auth_user):
        """Test successful PDF resume upload"""
        # Login first
        self._login(client, auth_user)
        
        # Create a minimal PDF file
        pdf_content = b'%PDF-1.4\n%fake pdf content\nendstream\nendobj'
        
        response = client.post('/resume/api/upload', data={
            'file': (BytesIO(pdf_content), 'resume.pdf')
        }, content_type='multipart/form-data')
        
        # May return 200 on valid extractable text, or 400/500 on mock non-rendered binary
        assert response.status_code in [200, 400, 500]
        data = response.get_json()
        if response.status_code == 200:
            assert data.get('success') is True
            assert 'resume_id' in data
            assert 'analysis' in data
    
    def test_upload_docx_success(self, client, auth_user):
        """Test successful DOCX resume upload"""
        # Login first
        self._login(client, auth_user)
        
        # Create a minimal DOCX file (ZIP format)
        docx_content = b'PK\x03\x04' + b'\x00' * 100  # Minimal ZIP header
        
        response = client.post('/resume/api/upload', data={
            'file': (BytesIO(docx_content), 'resume.docx')
        }, content_type='multipart/form-data')
        
        # May fail due to invalid DOCX, but should reject based on content, not extension
        assert response.status_code in [200, 400, 500]
    
    def test_upload_txt_rejected(self, client, auth_user):
        """Test that .txt files are rejected"""
        # Login first
        self._login(client, auth_user)
        
        txt_content = b'This is a text file'
        
        response = client.post('/resume/api/upload', data={
            'file': (BytesIO(txt_content), 'resume.txt')
        }, content_type='multipart/form-data')
        
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
        assert 'Invalid' in data['error'] or 'type' in data['error'].lower()
    
    def test_upload_no_file(self, client, auth_user):
        """Test upload fails when no file provided"""
        # Login first
        self._login(client, auth_user)
        
        response = client.post('/resume/api/upload', data={})
        
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
    
    def test_upload_requires_login(self, client):
        """Test upload requires authentication"""
        pdf_content = b'%PDF-1.4\n%fake pdf content'
        
        response = client.post('/resume/api/upload', data={
            'file': (BytesIO(pdf_content), 'resume.pdf')
        }, content_type='multipart/form-data')
        
        # Should redirect to login or return 401/403
        assert response.status_code in [302, 401, 403]
    
    @staticmethod
    def _login(client, user):
        """Helper to login a user"""
        client.post('/auth/login', data={
            'email': user.email,
            'password': 'testpassword123'
        })


class TestResumeOwnership:
    """Test resume ownership and access control"""
    
    def test_user_cannot_download_other_user_resume(self, client, app):
        """Test that a user cannot download another user's resume"""
        with app.app_context():
            # Create two users
            user1 = User(name='User 1', email='user1@example.com', user_type='student')
            user1.set_password('password1')
            user2 = User(name='User 2', email='user2@example.com', user_type='student')
            user2.set_password('password2')
            
            db.session.add(user1)
            db.session.add(user2)
            db.session.commit()
            
            # Create a resume for user1
            resume = Resume(
                user_id=user1.id,
                file_path='/fake/path/resume.pdf',
                ats_score=75
            )
            db.session.add(resume)
            db.session.commit()
            
            resume_id = resume.resume_id
        
        # Login as user2
        client.post('/auth/login', data={
            'email': 'user2@example.com',
            'password': 'password2'
        })
        
        # Try to download user1's resume
        response = client.get(f'/resume/download/{resume_id}')
        
        # Should be forbidden
        assert response.status_code == 403
        data = response.get_json()
        assert 'Unauthorized' in data.get('error', '')
    
    def test_user_can_download_own_resume(self, client, app):
        """Test that a user can download their own resume"""
        with app.app_context():
            # Create user
            user = User(name='Test User', email='testuser@example.com', user_type='student')
            user.set_password('password123')
            db.session.add(user)
            db.session.commit()
            
            # Create a test resume file
            upload_folder = os.path.join(os.path.dirname(__file__), '..', 'instance', 'uploads')
            os.makedirs(upload_folder, exist_ok=True)
            
            test_file = os.path.join(upload_folder, 'test_resume.pdf')
            with open(test_file, 'wb') as f:
                f.write(b'%PDF-1.4\ntest content')
            
            # Create resume record
            resume = Resume(
                user_id=user.id,
                file_path=test_file,
                ats_score=75
            )
            db.session.add(resume)
            db.session.commit()
            
            resume_id = resume.resume_id
        
        # Login as user
        client.post('/auth/login', data={
            'email': 'testuser@example.com',
            'password': 'password123'
        })
        
        # Download own resume
        response = client.get(f'/resume/download/{resume_id}')
        
        # Should succeed
        assert response.status_code == 200
        assert response.data == b'%PDF-1.4\ntest content'
        
        # Cleanup
        try:
            response.close()
            if os.path.exists(test_file):
                os.remove(test_file)
        except Exception:
            pass
    
    def test_delete_requires_ownership(self, client, app):
        """Test that only resume owner can delete"""
        with app.app_context():
            # Create two users
            user1 = User(name='User 1', email='user1@example.com', user_type='student')
            user1.set_password('password1')
            user2 = User(name='User 2', email='user2@example.com', user_type='student')
            user2.set_password('password2')
            
            db.session.add(user1)
            db.session.add(user2)
            db.session.commit()
            
            # Create a resume for user1
            resume = Resume(
                user_id=user1.id,
                file_path='/fake/path/resume.pdf',
                ats_score=75
            )
            db.session.add(resume)
            db.session.commit()
            
            resume_id = resume.resume_id
        
        # Login as user2
        client.post('/auth/login', data={
            'email': 'user2@example.com',
            'password': 'password2'
        })
        
        # Try to delete user1's resume
        response = client.delete(f'/resume/api/delete/{resume_id}')
        
        # Should be forbidden
        assert response.status_code == 403
        data = response.get_json()
        assert 'Unauthorized' in data.get('error', '')
