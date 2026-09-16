import pytest
from app.models.user import User
from app.extensions import db

class TestRegistration:
    """Test user registration"""
    
    def test_register_success(self, client):
        """Test successful registration with valid data"""
        response = client.post('/auth/register', data={
            'name': 'John Doe',
            'email': 'john@example.com',
            'phone': '9876543210',
            'password': 'securepass123',
            'confirm_password': 'securepass123',
            'user_type': 'student',
            'csrf_token': self._get_csrf_token(client, '/auth/register')
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert User.query.filter_by(email='john@example.com').first() is not None
    
    def test_register_duplicate_email(self, client, auth_user):
        """Test registration fails with duplicate email"""
        response = client.post('/auth/register', data={
            'name': 'Another User',
            'email': 'test@example.com',  # Same as auth_user
            'phone': '9876543210',
            'password': 'securepass123',
            'confirm_password': 'securepass123',
            'user_type': 'student',
            'csrf_token': self._get_csrf_token(client, '/auth/register')
        })
        
        assert response.status_code == 200
        assert b'Email already registered' in response.data or b'already' in response.data.lower()
    
    def test_register_password_mismatch(self, client):
        """Test registration fails when passwords don't match"""
        response = client.post('/auth/register', data={
            'name': 'John Doe',
            'email': 'john@example.com',
            'phone': '9876543210',
            'password': 'securepass123',
            'confirm_password': 'differentpass123',
            'user_type': 'student',
            'csrf_token': self._get_csrf_token(client, '/auth/register')
        })
        
        assert response.status_code == 200
        assert b'must match' in response.data.lower() or b'password' in response.data.lower()
    
    def test_register_missing_required_field(self, client):
        """Test registration fails with missing required field"""
        response = client.post('/auth/register', data={
            'name': 'John Doe',
            'email': '',  # Missing email
            'password': 'securepass123',
            'confirm_password': 'securepass123',
            'user_type': 'student',
            'csrf_token': self._get_csrf_token(client, '/auth/register')
        })
        
        assert response.status_code == 200
        # Should show validation error
        assert b'required' in response.data.lower() or b'email' in response.data.lower()
    
    @staticmethod
    def _get_csrf_token(client, url):
        """Helper to extract CSRF token from form"""
        response = client.get(url)
        # Extract csrf_token from response
        import re
        match = re.search(r'name="csrf_token"\s+type="hidden"\s+value="([^"]+)"', response.get_data(as_text=True))
        return match.group(1) if match else ''


class TestLogin:
    """Test user login"""
    
    def test_login_success(self, client, auth_user):
        """Test successful login with correct credentials"""
        response = client.post('/auth/login', data={
            'email': 'test@example.com',
            'password': 'testpassword123',
            'csrf_token': self._get_csrf_token(client, '/auth/login')
        }, follow_redirects=True)
        
        assert response.status_code == 200
        # Should redirect to dashboard after login
        assert 'dashboard' in response.request.path.lower() or b'welcome' in response.data.lower()
    
    def test_login_wrong_password(self, client, auth_user):
        """Test login fails with wrong password"""
        response = client.post('/auth/login', data={
            'email': 'test@example.com',
            'password': 'wrongpassword',
            'csrf_token': self._get_csrf_token(client, '/auth/login')
        })
        
        assert response.status_code == 200
        assert b'invalid' in response.data.lower() or b'password' in response.data.lower()
    
    def test_login_nonexistent_user(self, client):
        """Test login fails for non-existent user"""
        response = client.post('/auth/login', data={
            'email': 'nonexistent@example.com',
            'password': 'anypassword',
            'csrf_token': self._get_csrf_token(client, '/auth/login')
        })
        
        assert response.status_code == 200
        assert b'invalid' in response.data.lower() or b'email' in response.data.lower()
    
    def test_login_redirect_to_dashboard(self, client, auth_user):
        """Test login redirects to dashboard"""
        response = client.post('/auth/login', data={
            'email': 'test@example.com',
            'password': 'testpassword123',
            'csrf_token': self._get_csrf_token(client, '/auth/login')
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert b'welcome' in response.data.lower() or b'dashboard' in response.data.lower()
    
    @staticmethod
    def _get_csrf_token(client, url):
        """Helper to extract CSRF token from form"""
        response = client.get(url)
        import re
        match = re.search(r'name="csrf_token"\s+type="hidden"\s+value="([^"]+)"', response.get_data(as_text=True))
        return match.group(1) if match else ''


class TestLogout:
    """Test user logout"""
    
    def test_logout_success(self, client, auth_user):
        """Test successful logout"""
        # First login
        client.post('/auth/login', data={
            'email': 'test@example.com',
            'password': 'testpassword123',
            'csrf_token': self._get_csrf_token(client, '/auth/login')
        })
        
        # Then logout
        response = client.get('/auth/logout', follow_redirects=True)
        
        assert response.status_code == 200
        assert b'logged out' in response.data.lower() or b'index' in response.request.path.lower()
    
    @staticmethod
    def _get_csrf_token(client, url):
        """Helper to extract CSRF token from form"""
        response = client.get(url)
        import re
        match = re.search(r'name="csrf_token"\s+type="hidden"\s+value="([^"]+)"', response.get_data(as_text=True))
        return match.group(1) if match else ''
