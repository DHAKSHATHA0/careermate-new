from flask import Flask
from flask_login import LoginManager
from app.extensions import db, login_manager
import os

def create_app(config_name='development'):
    """Flask app factory"""
    app = Flask(__name__, instance_relative_config=True)
    
    # Load config
    from config import config
    app.config.from_object(config[config_name])
    
    # Load .env
    from dotenv import load_dotenv
    load_dotenv()
    
    # Override with environment variables
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', app.config.get('SECRET_KEY', 'dev-secret-key-careermate'))
    
    instance_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'instance'))
    os.makedirs(instance_dir, exist_ok=True)
    
    if config_name != 'testing':
        # Load instance config (secrets)
        try:
            app.config.from_pyfile('config.py')
        except FileNotFoundError:
            pass
        
        # Resolve database URL reliably based on environment
        db_url = os.getenv('DATABASE_URL')
        if not db_url or db_url == 'sqlite:///careermate.db' or db_url == 'sqlite:///instance/careermate.db':
            db_path = os.path.join(instance_dir, 'careermate.db').replace('\\', '/')
            db_url = f'sqlite:///{db_path}'
        elif db_url.startswith('postgres://'):
            db_url = db_url.replace('postgres://', 'postgresql://', 1)
        app.config['SQLALCHEMY_DATABASE_URI'] = db_url
    else:
        # Enforce in-memory DB and test flags for test environment
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
    
    # Ensure instance/uploads exists
    os.makedirs(app.config.get('UPLOAD_FOLDER', os.path.join(instance_dir, 'uploads')), exist_ok=True)
    
    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    
    # Register blueprints
    from app.routes import auth_bp, main_bp, chatbot_bp, resume_bp, company_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(chatbot_bp)
    app.register_blueprint(resume_bp)
    app.register_blueprint(company_bp)
    
    # Import all models to ensure metadata registration
    from app import models
    
    # Create tables if not existing
    with app.app_context():
        db.create_all()
    
    return app
