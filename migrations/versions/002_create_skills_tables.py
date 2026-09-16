"""Create Skills and UserSkills tables

Revision ID: 002_create_skills_tables
Revises: 001_update_users_schema
Create Date: 2024-01-01 00:00:01.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '002_create_skills_tables'
down_revision = '001_update_users_schema'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create skills table
    op.create_table(
        'skills',
        sa.Column('skill_id', sa.Integer(), nullable=False),
        sa.Column('skill_name', sa.String(100), nullable=False),
        sa.PrimaryKeyConstraint('skill_id'),
        sa.UniqueConstraint('skill_name')
    )
    op.create_index('ix_skills_skill_name', 'skills', ['skill_name'])
    
    # Create user_skills association table
    op.create_table(
        'user_skills',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('skill_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['skill_id'], ['skills.skill_id'], ),
        sa.PrimaryKeyConstraint('user_id', 'skill_id')
    )
    op.create_index('ix_user_skills_user_id', 'user_skills', ['user_id'])
    op.create_index('ix_user_skills_skill_id', 'user_skills', ['skill_id'])


def downgrade() -> None:
    # Drop user_skills table
    op.drop_index('ix_user_skills_skill_id', table_name='user_skills')
    op.drop_index('ix_user_skills_user_id', table_name='user_skills')
    op.drop_table('user_skills')
    
    # Drop skills table
    op.drop_index('ix_skills_skill_name', table_name='skills')
    op.drop_table('skills')
