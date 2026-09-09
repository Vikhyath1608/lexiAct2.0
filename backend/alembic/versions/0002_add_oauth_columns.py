"""Add oauth_provider and oauth_sub columns to users table

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-02
"""
from alembic import op
import sqlalchemy as sa

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add oauth_provider column — nullable since existing users have no OAuth
    op.add_column('users',
        sa.Column('oauth_provider', sa.String(32), nullable=True)
    )
    # Add oauth_sub column — nullable for same reason
    op.add_column('users',
        sa.Column('oauth_sub', sa.String(255), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('users', 'oauth_sub')
    op.drop_column('users', 'oauth_provider')