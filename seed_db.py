"""
Database seeding script - populate Companies, Questions, and Skills tables
Run this after creating the database: python seed_db.py
"""

from app import create_app
from app.extensions import db
from app.models.company import Company
from app.models.question import Question
from app.models.skill import Skill

def seed_database():
    """Seed database with sample companies, questions, and skills"""
    app = create_app()
    
    with app.app_context():
        # Clear existing data
        Question.query.delete()
        Company.query.delete()
        Skill.query.delete()
        
        # Seed skills (20-30 common skills)
        skills_data = [
            'Python', 'Java', 'JavaScript', 'C++', 'C#', 'Go', 'Rust', 'Ruby',
            'SQL', 'MongoDB', 'PostgreSQL', 'MySQL',
            'React', 'Vue.js', 'Angular', 'Node.js', 'Django', 'Flask',
            'AWS', 'Azure', 'GCP', 'Docker', 'Kubernetes',
            'Machine Learning', 'Deep Learning', 'Data Science', 'TensorFlow', 'PyTorch',
            'Git', 'REST APIs', 'GraphQL', 'Microservices', 'System Design'
        ]
        
        skills = {}
        for skill_name in skills_data:
            skill = Skill(skill_name=skill_name)
            db.session.add(skill)
            db.session.flush()
            skills[skill_name] = skill
        
        # Create companies
        companies_data = [
            {
                'name': 'Google',
                'description': 'Google is a multinational technology company specializing in Internet-related services and products.',
                'eligibility': 'B.Tech/B.E in Computer Science, Electronics, or related fields. CGPA >= 7.0',
                'salary': '₹60-80 LPA',
                'selection_process': 'Online Assessment (Coding) → Technical Interview (2-3 rounds) → HR Interview'
            },
            {
                'name': 'TCS',
                'description': 'Tata Consultancy Services is an Indian multinational IT services and consulting company.',
                'eligibility': 'Any graduate with 60% aggregate. No active backlogs.',
                'salary': '₹3.6-4.5 LPA',
                'selection_process': 'Online Assessment → Technical Interview → HR Interview'
            },
            {
                'name': 'Infosys',
                'description': 'Infosys is an Indian multinational information technology company providing business consulting, information technology and outsourcing services.',
                'eligibility': 'Any graduate with 60% aggregate. No active backlogs.',
                'salary': '₹3.5-4.2 LPA',
                'selection_process': 'Online Assessment → Technical Interview → HR Interview'
            }
        ]
        
        companies = {}
        for comp_data in companies_data:
            company = Company(
                company_name=comp_data['name'],
                description=comp_data['description'],
                eligibility=comp_data['eligibility'],
                salary=comp_data['salary'],
                selection_process=comp_data['selection_process']
            )
            db.session.add(company)
            db.session.flush()
            companies[comp_data['name']] = company
        
        # Create questions for Google
        google_questions = [
            {
                'type': 'technical',
                'difficulty': 'medium',
                'question': 'Write a function to reverse a linked list.',
                'answer': 'Use three pointers (prev, current, next) to reverse the links. Time: O(n), Space: O(1).'
            },
            {
                'type': 'technical',
                'difficulty': 'hard',
                'question': 'Design a system to handle distributed caching.',
                'answer': 'Use consistent hashing, replication, and cache invalidation strategies. Consider CAP theorem.'
            },
            {
                'type': 'aptitude',
                'difficulty': 'easy',
                'question': 'If a train travels 60 km/h for 2 hours, how far does it travel?',
                'answer': 'Distance = Speed × Time = 60 × 2 = 120 km'
            },
            {
                'type': 'logical',
                'difficulty': 'medium',
                'question': 'Find the missing number in an array of 1 to n.',
                'answer': 'Use sum formula: n*(n+1)/2 - sum(array). Or use XOR approach.'
            },
            {
                'type': 'verbal',
                'difficulty': 'easy',
                'question': 'What is the synonym of "Ephemeral"?',
                'answer': 'Temporary, fleeting, transient, short-lived'
            }
        ]
        
        for q_data in google_questions:
            question = Question(
                company_id=companies['Google'].company_id,
                question_type=q_data['type'],
                difficulty_level=q_data['difficulty'],
                question=q_data['question'],
                answer=q_data['answer']
            )
            db.session.add(question)
        
        # Create questions for TCS
        tcs_questions = [
            {
                'type': 'technical',
                'difficulty': 'easy',
                'question': 'What is the difference between Array and ArrayList?',
                'answer': 'Array is fixed size, ArrayList is dynamic. ArrayList is part of Collections framework.'
            },
            {
                'type': 'aptitude',
                'difficulty': 'medium',
                'question': 'What is 15% of 200?',
                'answer': '15% of 200 = (15/100) × 200 = 30'
            },
            {
                'type': 'logical',
                'difficulty': 'easy',
                'question': 'What comes next in the series: 2, 4, 8, 16, ?',
                'answer': '32 (each number is multiplied by 2)'
            },
            {
                'type': 'verbal',
                'difficulty': 'easy',
                'question': 'Choose the correct spelling: Occassion or Occasion?',
                'answer': 'Occasion (with one c and two s)'
            },
            {
                'type': 'technical',
                'difficulty': 'medium',
                'question': 'Explain the concept of inheritance in OOP.',
                'answer': 'Inheritance allows a class to inherit properties and methods from another class, promoting code reuse.'
            }
        ]
        
        for q_data in tcs_questions:
            question = Question(
                company_id=companies['TCS'].company_id,
                question_type=q_data['type'],
                difficulty_level=q_data['difficulty'],
                question=q_data['question'],
                answer=q_data['answer']
            )
            db.session.add(question)
        
        # Create questions for Infosys
        infosys_questions = [
            {
                'type': 'technical',
                'difficulty': 'easy',
                'question': 'What is a database index?',
                'answer': 'An index is a data structure that improves the speed of data retrieval operations on a table.'
            },
            {
                'type': 'aptitude',
                'difficulty': 'easy',
                'question': 'If 5 workers can build a wall in 10 days, how many days for 10 workers?',
                'answer': '5 days (inverse proportion: more workers = less time)'
            },
            {
                'type': 'logical',
                'difficulty': 'medium',
                'question': 'Solve: If A > B, B > C, and C > D, then which is smallest?',
                'answer': 'D is the smallest (D < C < B < A)'
            },
            {
                'type': 'verbal',
                'difficulty': 'easy',
                'question': 'What is the antonym of "Verbose"?',
                'answer': 'Concise, brief, terse, succinct'
            },
            {
                'type': 'technical',
                'difficulty': 'medium',
                'question': 'Explain the difference between SQL and NoSQL.',
                'answer': 'SQL is relational (structured), NoSQL is non-relational (unstructured). Different use cases.'
            }
        ]
        
        for q_data in infosys_questions:
            question = Question(
                company_id=companies['Infosys'].company_id,
                question_type=q_data['type'],
                difficulty_level=q_data['difficulty'],
                question=q_data['question'],
                answer=q_data['answer']
            )
            db.session.add(question)
        
        # Commit all changes
        db.session.commit()
        print("[OK] Database seeded successfully!")
        print(f"  - {len(skills)} skills created")
        print(f"  - {len(companies)} companies created")
        print(f"  - {len(google_questions) + len(tcs_questions) + len(infosys_questions)} questions created")

if __name__ == '__main__':
    seed_database()
