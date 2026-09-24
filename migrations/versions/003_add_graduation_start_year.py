"""Add graduation_start_year to users table

Revision ID: 003_add_graduation_start_year
Revises: 002_create_skills_tables
Create Date: 2024-01-01 00:00:02.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '003_add_graduation_start_year'
down_revision = '002_create_skills_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add graduation_start_year column to users table
    op.add_column('users', sa.Column('graduation_start_year', sa.Integer(), nullable=True))


def downgrade() -> None:
    # Remove graduation_start_year column from users table
    op.drop_column('users', 'graduation_start_year')
