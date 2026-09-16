"""Profile-related utility functions"""

def calculate_profile_completeness(user):
    """
    Calculate user profile completeness percentage.
    
    Breakdown:
    - 20% for account creation (name, email, password, user_type)
    - 20% for education info (college_name, degree, graduation_year)
    - 20% for domain selection
    - 20% for career goal selection
    - 20% for resume upload
    
    Args:
        user: User model instance
        
    Returns:
        int: Completeness percentage (0-100)
    """
    score = 0
    
    # Base: Account created (20%)
    if user.id and user.name and user.email and user.user_type:
        score += 20
    
    # Education info (20%)
    if user.college_name and user.degree and user.graduation_year:
        score += 20
    
    # Domain selection (20%)
    if user.domain:
        score += 20
    
    # Career goal (20%)
    if user.career_goal:
        score += 20
    
    # Resume upload (20%)
    if user.resumes and len(user.resumes) > 0:
        score += 20
    
    return min(score, 100)
