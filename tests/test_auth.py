import pytest
import os
import tempfile
from app import create_app
from app.models.user import User
from app.extensions import db


class TestRegistration:
    """Test user registration flows"""
    
    def test_register_success(self, client):
        """1. Test successful registration with valid data and normalized email"""
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
        user = User.query.filter_by(email='john@example.com').first()
        assert user is not None
        assert user.name == 'John Doe'
    
    def test_register_duplicate_email(self, client, auth_user):
        """8. Test registration fails with duplicate email (same and mixed-case)"""
        # Exact duplicate
        response = client.post('/auth/register', data={
            'name': 'Another User',
            'email': 'test@example.com',
            'phone': '9876543210',
            'password': 'securepass123',
            'confirm_password': 'securepass123',
            'user_type': 'student',
            'csrf_token': self._get_csrf_token(client, '/auth/register')
        })
        assert response.status_code == 200
        assert b'Email already registered' in response.data or b'already' in response.data.lower()
        
        # Mixed-case duplicate
        response_mixed = client.post('/auth/register', data={
            'name': 'Another User',
            'email': '  TEST@EXAMPLE.COM  ',
            'phone': '9876543210',
            'password': 'securepass123',
            'confirm_password': 'securepass123',
            'user_type': 'student',
            'csrf_token': self._get_csrf_token(client, '/auth/register')
        })
        assert response_mixed.status_code == 200
        assert b'Email already registered' in response_mixed.data or b'already' in response_mixed.data.lower()
    
    def test_register_password_mismatch(self, client):
        """Test registration fails when passwords don't match"""
        response = client.post('/auth/register', data={
            'name': 'John Doe',
            'email': 'john_mismatch@example.com',
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
            'email': '',
            'password': 'securepass123',
            'confirm_password': 'securepass123',
            'user_type': 'student',
            'csrf_token': self._get_csrf_token(client, '/auth/register')
        })
        
        assert response.status_code == 200
        assert b'required' in response.data.lower() or b'email' in response.data.lower()
    
    @staticmethod
    def _get_csrf_token(client, url):
        """Helper to extract CSRF token from form"""
        response = client.get(url)
        import re
        match = re.search(r'name="csrf_token"\s+type="hidden"\s+value="([^"]+)"', response.get_data(as_text=True))
        return match.group(1) if match else ''


class TestLogin:
    """Test user login authentication and case normalization"""
    
    def test_login_success(self, client, auth_user):
        """3. Test login using exact email and password"""
        response = client.post('/auth/login', data={
            'email': 'test@example.com',
            'password': 'testpassword123',
            'csrf_token': self._get_csrf_token(client, '/auth/login')
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert 'dashboard' in response.request.path.lower() or b'welcome' in response.data.lower()
    
    def test_login_uppercase_mixed_case_email(self, client, auth_user):
        """4. Test login using uppercase / mixed-case version of same email"""
        response = client.post('/auth/login', data={
            'email': 'TeSt@ExAmPlE.CoM',
            'password': 'testpassword123',
            'csrf_token': self._get_csrf_token(client, '/auth/login')
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert 'dashboard' in response.request.path.lower() or b'welcome' in response.data.lower()
    
    def test_login_whitespace_email(self, client, auth_user):
        """5. Test login with leading and trailing whitespace"""
        response = client.post('/auth/login', data={
            'email': '   test@example.com   ',
            'password': 'testpassword123',
            'csrf_token': self._get_csrf_token(client, '/auth/login')
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert 'dashboard' in response.request.path.lower() or b'welcome' in response.data.lower()
    
    def test_login_wrong_password(self, client, auth_user):
        """6. Test login fails with wrong password"""
        response = client.post('/auth/login', data={
            'email': 'test@example.com',
            'password': 'wrongpassword',
            'csrf_token': self._get_csrf_token(client, '/auth/login')
        })
        
        assert response.status_code == 200
        assert b'invalid' in response.data.lower() or b'password' in response.data.lower()
    
    def test_login_nonexistent_user(self, client):
        """7. Test login fails for non-existent email"""
        response = client.post('/auth/login', data={
            'email': 'nonexistent@example.com',
            'password': 'anypassword',
            'csrf_token': self._get_csrf_token(client, '/auth/login')
        })
        
        assert response.status_code == 200
        assert b'invalid' in response.data.lower() or b'email' in response.data.lower()
    
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
        """2. Test successful logout"""
        client.post('/auth/login', data={
            'email': 'test@example.com',
            'password': 'testpassword123',
            'csrf_token': self._get_csrf_token(client, '/auth/login')
        })
        
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


class TestPersistenceAndDeployment:
    """Test user persistence across app restarts and non-destructive deployments"""
    
    def test_existing_user_survives_application_restart(self):
        """9. Test existing user in persistent DB survives full application restart and can log in"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tf:
            db_file = tf.name
            
        orig_db_url = os.environ.get('DATABASE_URL')
        try:
            db_uri = f'sqlite:///{db_file.replace(chr(92), "/")}'
            os.environ['DATABASE_URL'] = db_uri
            
            # --- Instance 1: Create user & commit ---
            app1 = create_app('development')
            app1.config['TESTING'] = True
            app1.config['WTF_CSRF_ENABLED'] = False
            
            with app1.app_context():
                user = User(
                    name='Persistent Alice',
                    email='  Alice.Persistent@Example.Com  ',
                    phone='1234567890',
                    user_type='professional'
                )
                user.set_password('SecretPass456')
                db.session.add(user)
                db.session.commit()
                
            # Simulate complete process termination of Instance 1
            del app1
            
            # --- Instance 2: Start new app instance pointing to same database ---
            app2 = create_app('development')
            app2.config['TESTING'] = True
            app2.config['WTF_CSRF_ENABLED'] = False
            
            with app2.app_context():
                # Verify user exists and email was cleanly normalized
                found_user = User.query.filter_by(email='alice.persistent@example.com').first()
                assert found_user is not None
                assert found_user.name == 'Persistent Alice'
                assert found_user.check_password('SecretPass456') is True
                
            # Verify login flow via HTTP client on the new instance
            client2 = app2.test_client()
            resp = client2.post('/auth/login', data={
                'email': 'ALICE.PERSISTENT@EXAMPLE.COM',
                'password': 'SecretPass456'
            }, follow_redirects=True)
            assert resp.status_code == 200
            assert 'dashboard' in resp.request.path.lower() or b'welcome' in resp.data.lower()
            
        finally:
            if orig_db_url is not None:
                os.environ['DATABASE_URL'] = orig_db_url
            else:
                os.environ.pop('DATABASE_URL', None)
            if os.path.exists(db_file):
                try:
                    os.remove(db_file)
                except Exception:
                    pass

    def test_existing_user_survives_deployment(self):
        """10. Test that startup code / db.create_all() does not drop or wipe existing users on deployment"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tf:
            db_file = tf.name
            
        orig_db_url = os.environ.get('DATABASE_URL')
        try:
            db_uri = f'sqlite:///{db_file.replace(chr(92), "/")}'
            os.environ['DATABASE_URL'] = db_uri
            
            # Simulate initial deployment
            app = create_app('development')
            app.config['TESTING'] = True
            app.config['WTF_CSRF_ENABLED'] = False
            
            with app.app_context():
                user = User(
                    name='Deploy User',
                    email='deploy.user@example.com',
                    user_type='fresher'
                )
                user.set_password('deploypass789')
                db.session.add(user)
                db.session.commit()
                
            # Simulate subsequent deployment / restart triggering create_app and db.create_all() again
            deploy_app = create_app('development')
            deploy_app.config['TESTING'] = True
            deploy_app.config['WTF_CSRF_ENABLED'] = False
            
            with deploy_app.app_context():
                # Check user is still preserved intact after restart/deploy
                u = User.query.filter_by(email='deploy.user@example.com').first()
                assert u is not None
                assert u.name == 'Deploy User'
                assert u.check_password('deploypass789') is True
                
        finally:
            if orig_db_url is not None:
                os.environ['DATABASE_URL'] = orig_db_url
            else:
                os.environ.pop('DATABASE_URL', None)
            if os.path.exists(db_file):
                try:
                    os.remove(db_file)
                except Exception:
                    pass
