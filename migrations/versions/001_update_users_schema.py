"""Update Users table schema for two-step registration

Revision ID: 001_update_users_schema
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '001_update_users_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns to users table
    op.add_column('users', sa.Column('phone', sa.String(15), nullable=True))
    op.add_column('users', sa.Column('user_type', sa.Enum('student', 'fresher', 'professional'), nullable=False, server_default='student'))
    op.add_column('users', sa.Column('college_name', sa.String(150), nullable=True))
    op.add_column('users', sa.Column('degree', sa.String(100), nullable=True))
    op.add_column('users', sa.Column('graduation_year', sa.Integer, nullable=True))
    op.add_column('users', sa.Column('current_company', sa.String(150), nullable=True))
    op.add_column('users', sa.Column('career_goal', sa.Enum('placement_prep', 'job_switch', 'upskilling'), nullable=True))


def downgrade() -> None:
    # Remove columns from users table
    op.drop_column('users', 'career_goal')
    op.drop_column('users', 'current_company')
    op.drop_column('users', 'graduation_year')
    op.drop_column('users', 'degree')
    op.drop_column('users', 'college_name')
    op.drop_column('users', 'user_type')
    op.drop_column('users', 'phone')
