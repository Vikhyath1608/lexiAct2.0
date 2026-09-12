"""Fix conversations table structure

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-12
"""
from alembic import op
import sqlalchemy as sa

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop the wrongly structured conversations table completely
    op.execute("DROP TABLE IF EXISTS conversations CASCADE")

    # Recreate it with the correct structure
    op.execute("""
        CREATE TABLE conversations (
            id         SERIAL PRIMARY KEY,
            user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            session_id TEXT    NOT NULL DEFAULT 'default',
            role       TEXT    NOT NULL,
            content    TEXT    NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    # Recreate indexes
    op.execute("CREATE INDEX ix_conversations_id         ON conversations (id)")
    op.execute("CREATE INDEX ix_conversations_user_id    ON conversations (user_id)")
    op.execute("CREATE INDEX ix_conversations_session_id ON conversations (session_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS conversations CASCADE")