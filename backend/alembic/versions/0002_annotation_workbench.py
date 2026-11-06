"""Accounts, projects, codebooks, annotations and activity.

Revision ID: 0002
Revises: 0001
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

TABLES = (
    "login_attempts", "activity_log", "presence", "annotations", "codes", "article_progress",
    "project_articles", "project_members", "projects", "sessions", "users",
)


def upgrade() -> None:
    op.execute("""
    CREATE TABLE users (
        id UUID PRIMARY KEY,
        username TEXT NOT NULL CHECK (length(trim(username)) > 0),
        display_name TEXT NOT NULL CHECK (length(trim(display_name)) > 0),
        password_hash TEXT NOT NULL,
        is_admin BOOLEAN NOT NULL DEFAULT FALSE,
        active BOOLEAN NOT NULL DEFAULT TRUE,
        created_at TIMESTAMPTZ NOT NULL
    );
    CREATE UNIQUE INDEX idx_users_username ON users (lower(username));

    CREATE TABLE sessions (
        token_hash TEXT PRIMARY KEY,
        user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        created_at TIMESTAMPTZ NOT NULL,
        expires_at TIMESTAMPTZ NOT NULL
    );
    CREATE INDEX idx_sessions_user ON sessions (user_id);

    CREATE TABLE login_attempts (
        key TEXT PRIMARY KEY,
        failures INTEGER NOT NULL,
        first_failure_at TIMESTAMPTZ NOT NULL
    );

    CREATE TABLE projects (
        id UUID PRIMARY KEY,
        name TEXT NOT NULL CHECK (length(trim(name)) > 0),
        description TEXT NOT NULL DEFAULT '',
        archived BOOLEAN NOT NULL DEFAULT FALSE,
        created_by UUID NOT NULL REFERENCES users(id),
        created_at TIMESTAMPTZ NOT NULL,
        revision INTEGER NOT NULL DEFAULT 1
    );
    CREATE UNIQUE INDEX idx_projects_name ON projects (lower(name));

    CREATE TABLE project_members (
        project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        user_id UUID NOT NULL REFERENCES users(id),
        role TEXT NOT NULL CHECK (role IN ('lead', 'coder')),
        added_at TIMESTAMPTZ NOT NULL,
        PRIMARY KEY (project_id, user_id)
    );
    CREATE INDEX idx_project_members_user ON project_members (user_id);

    CREATE TABLE project_articles (
        project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        article_id TEXT NOT NULL,
        added_by UUID NOT NULL REFERENCES users(id),
        added_at TIMESTAMPTZ NOT NULL,
        PRIMARY KEY (project_id, article_id)
    );

    CREATE TABLE article_progress (
        project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        article_id TEXT NOT NULL,
        user_id UUID NOT NULL REFERENCES users(id),
        status TEXT NOT NULL CHECK (status IN ('in_progress', 'done')),
        updated_at TIMESTAMPTZ NOT NULL,
        PRIMARY KEY (project_id, article_id, user_id)
    );

    CREATE TABLE codes (
        id UUID PRIMARY KEY,
        project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        name TEXT NOT NULL CHECK (length(trim(name)) > 0),
        parent_id UUID REFERENCES codes(id),
        definition TEXT NOT NULL DEFAULT '',
        color TEXT NOT NULL CHECK (color ~ '^#[0-9A-Fa-f]{6}$'),
        sort_order INTEGER NOT NULL DEFAULT 0,
        merged_into UUID REFERENCES codes(id),
        revision INTEGER NOT NULL DEFAULT 1,
        created_by UUID NOT NULL REFERENCES users(id),
        created_at TIMESTAMPTZ NOT NULL,
        updated_at TIMESTAMPTZ NOT NULL,
        CHECK (parent_id IS NULL OR parent_id <> id),
        CHECK (merged_into IS NULL OR merged_into <> id)
    );
    CREATE UNIQUE INDEX idx_codes_active_name
        ON codes (project_id, COALESCE(parent_id, '00000000-0000-0000-0000-000000000000'), lower(name))
        WHERE merged_into IS NULL;
    CREATE INDEX idx_codes_project ON codes (project_id);

    CREATE TABLE annotations (
        id UUID PRIMARY KEY,
        project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        article_id TEXT NOT NULL,
        user_id UUID NOT NULL REFERENCES users(id),
        code_id UUID NOT NULL REFERENCES codes(id),
        start_pos INTEGER NOT NULL,
        end_pos INTEGER NOT NULL,
        quote TEXT NOT NULL,
        text_sha256 TEXT NOT NULL,
        memo TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'stale')),
        revision INTEGER NOT NULL DEFAULT 1,
        created_at TIMESTAMPTZ NOT NULL,
        updated_at TIMESTAMPTZ NOT NULL,
        CHECK (start_pos >= 0 AND start_pos < end_pos),
        UNIQUE (project_id, article_id, start_pos, end_pos, code_id, user_id)
    );
    CREATE INDEX idx_annotations_article ON annotations (project_id, article_id, user_id);
    CREATE INDEX idx_annotations_code ON annotations (code_id);
    CREATE INDEX idx_annotations_text ON annotations (article_id);

    CREATE TABLE presence (
        project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        article_id TEXT NOT NULL,
        user_id UUID NOT NULL REFERENCES users(id),
        last_seen TIMESTAMPTZ NOT NULL,
        PRIMARY KEY (project_id, article_id, user_id)
    );

    CREATE TABLE activity_log (
        id BIGSERIAL PRIMARY KEY,
        occurred_at TIMESTAMPTZ NOT NULL,
        user_id UUID REFERENCES users(id),
        project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
        action TEXT NOT NULL,
        target TEXT NOT NULL DEFAULT '',
        details JSONB NOT NULL DEFAULT '{}'
    );
    CREATE INDEX idx_activity_project ON activity_log (project_id, occurred_at DESC);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS " + ", ".join(TABLES) + " CASCADE")
