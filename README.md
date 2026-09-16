# CareerMate - AI-Powered Career Guidance Platform

## Setup Instructions

### 1. Create Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Environment
```bash
cp .env.example .env
# Edit .env with your local values
```

### 4. Setup Database
```bash
# Create MySQL database
mysql -u root -p
CREATE DATABASE careermate;
EXIT;

# Run migrations (if using Alembic)
# For now, tables are created automatically on app startup
```

### 5. Download spaCy Model
```bash
python -m spacy download en_core_web_sm
```

### 6. Run Application
```bash
python run.py
```

Visit `http://localhost:5000` in your browser.

## Project Structure
- `app/` - Flask application code
- `app/models/` - SQLAlchemy database models
- `app/routes/` - Flask blueprints for routes
- `app/templates/` - Jinja2 HTML templates
- `app/static/` - CSS, JavaScript, images
- `app/utils/` - Helper utilities (resume parsing, NLP, similarity)
- `instance/` - Local configuration and uploaded files (not committed)
- `config.py` - Application configuration
- `run.py` - Application entry point

## Security Notes
- Resumes are stored in `instance/uploads/` and served only through authenticated routes
- All file uploads are validated by MIME type and file extension
- Passwords are hashed using Werkzeug's bcrypt-based hashing
- CSRF protection is enabled on all forms via Flask-WTF
