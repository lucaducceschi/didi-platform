"""Saved corpus selections and materialized selection members.

Revision ID: 0003
Revises: 0002
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE saved_corpus_selections (
        id UUID PRIMARY KEY,
        project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        name TEXT NOT NULL CHECK (length(trim(name)) > 0),
        description TEXT NOT NULL DEFAULT '',
        query_definition JSONB NOT NULL DEFAULT '{}'::jsonb,
        article_count INTEGER NOT NULL DEFAULT 0,
        created_by UUID NOT NULL REFERENCES users(id),
        created_at TIMESTAMPTZ NOT NULL,
        updated_at TIMESTAMPTZ NOT NULL
    );
    CREATE INDEX idx_saved_selections_project ON saved_corpus_selections(project_id);

    CREATE TABLE saved_selection_members (
        selection_id UUID NOT NULL REFERENCES saved_corpus_selections(id) ON DELETE CASCADE,
        article_id TEXT NOT NULL,
        added_at TIMESTAMPTZ NOT NULL,
        PRIMARY KEY (selection_id, article_id)
    );
    CREATE INDEX idx_selection_members_article ON saved_selection_members(article_id);
    """)


def downgrade() -> None:
    op.execute("""
    DROP TABLE IF EXISTS saved_selection_members;
    DROP TABLE IF EXISTS saved_corpus_selections;
    """)

