# PRD: DIDI Full-Stack Platform and Text Coding (Phase 3.1)

**Status:** Direction agreed, not started. Created 2026-11-06.

**Goal:** Turn DIDI from a Streamlit demo into a React and Python web app with databases, and make its first feature text coding for up to 10 annotators, so the project no longer depends on a MAXQDA licence and its data stays fully exportable.

## 1. Scope

| # | Delivered in this phase | Replaces today |
|---|---|---|
| 0 | React frontend, Python API, PostgreSQL, tests, container and CI files | Streamlit only |
| 1 | Coder accounts and shared codebook: create, nest, rename, merge, define codes | Free-text analyst name; one flat tag per quote |
| 2 | Article reader with coded passages highlighted | Notes listed under the article |
| 3 | Select text and code it directly | Pasting quotes, with no positions stored |

### Not in this phase

The design must not block these, but do not build them:

- Porting the Radar, Timeline, Focus Events and Keyness views. **Streamlit stays as the analysis demo** until they are ported.
- Cross-article retrieval of segments by code
- Inter-coder agreement (Krippendorff's alpha, disagreement review)
- QDPX export of coded segments, and QDPX import
- PDF, audio, video or image coding
- Any GPU service
- The actual first deploy, which needs the Admin (Section 11)

### Rules that apply throughout

- **Multi-coder from the start.** Every segment belongs to one coder, and only that coder can change it. The server enforces this.
- **Open data.** Everything stored can be exported as CSV, and the schema is documented.
- **No external calls.** No CDN, web fonts or analytics. The app must work without internet access on its network.
- **Copyright.** Full text, databases and exports never reach the public `origin` remote.
- **Shared platform.** Follow the LT Developer Handbook (`commul/lt-developer-handbook` on `gitlab.inf.unibz.it`, read with `glab`). It is binding wherever it applies.

## 2. Target architecture

```
Browser ── React + TypeScript (Vite, Zustand), served by nginx ─┐  FE Server
                                                                │
                                                     /api/ proxy
                                                                │
           FastAPI (Python) ────────────────────────────────────┘  FE Server, CPU only
             ├── PostgreSQL: users, codes, annotations (read-write)
             ├── SQLite FTS5 corpus: articles, metrics (read-only, rebuilt by the pipeline)
             └── Inference client, added later ──> GPU service on the VPN (GPU VM)
```

| Part | Choice | Why |
|---|---|---|
| Frontend | React 19, TypeScript, Vite, Zustand, oxlint | Matches `speech-workbench/frontend`, so the team and its patterns carry over |
| API | FastAPI, Uvicorn, Pydantic | Typed, with generated API docs. Do not copy the Workbench's hand-written `http.server` backend |
| App data | PostgreSQL with SQLAlchemy 2 and Alembic (decided 2026-11-06) | Up to 10 concurrent writers and live research data, so start here rather than migrate later |
| Corpus | Existing SQLite FTS5 file, read-only | It is a rebuildable artifact, and FTS5 already meets the search needs |
| Deploy | GitLab CI, kaniko, Komodo, Traefik | Required by the handbook |

**Reuse from the current repo:**

- `src/ui/data_service.py` has no Streamlit dependency, so the API can call it. Move it to `src/services/` in Task 0, with a thin import left for Streamlit. Its annotation methods are replaced in Task 1.
- `src/harmonizers/`, `src/storage/`, `src/nlp/` and the `qdpx` writer stay as they are.

**Repository layout**

```
backend/app/      FastAPI app: routers, schemas, models, auth
backend/alembic/  Migrations
frontend/         React app
src/              Existing pipeline and services
src/ui/           Streamlit demo, unchanged until views are ported
docker/           Dockerfile.backend, Dockerfile.frontend, nginx.conf.template
tests/            Python tests
```

## 3. Verified technical basis

Measured in a browser on 2026-11-06. The code is in [`spike/`](spike/). It ran in a Streamlit component, but the position logic is plain browser JavaScript and carries over to React. Task 2 must re-verify it in React.

| Finding | Consequence |
|---|---|
| Browser offsets count UTF-16 units, while Python and REFI-QDA count code points | Convert with `Array.from`, in one module only |
| Offsets matched Python slices for emoji, NFD combining characters, CRLF, Markdown-like text and selections crossing highlight spans | One container with `white-space: pre-wrap` and spans holding the raw text is safe |
| A mouse drag included a trailing space (`'Plain text with target '`) | The server trims whitespace from selections and recalculates positions |

The corpus contains these cases: 1,401 articles are not NFC-normalized, 4 contain characters outside the Basic Multilingual Plane, 3 contain `\r`, and 216 contain Markdown-active characters.

## 4. Database

Managed through Alembic migrations.

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY,
    username TEXT NOT NULL,
    display_name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('lead', 'coder')),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL
);
CREATE UNIQUE INDEX idx_users_username ON users (lower(username));

CREATE TABLE sessions (
    token_hash TEXT PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE codes (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    parent_id UUID REFERENCES codes(id),
    definition TEXT NOT NULL DEFAULT '',
    color TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    merged_into UUID REFERENCES codes(id),
    created_by UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);
CREATE UNIQUE INDEX idx_codes_active_name
    ON codes (COALESCE(parent_id, '00000000-0000-0000-0000-000000000000'), lower(name))
    WHERE merged_into IS NULL;

CREATE TABLE annotations (
    id UUID PRIMARY KEY,
    article_id TEXT NOT NULL,
    text_sha256 TEXT NOT NULL,
    start_pos INTEGER NOT NULL,
    end_pos INTEGER NOT NULL,
    quote TEXT NOT NULL,
    code_id UUID NOT NULL REFERENCES codes(id),
    user_id UUID NOT NULL REFERENCES users(id),
    memo TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'stale')),
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    CHECK (start_pos >= 0 AND start_pos < end_pos),
    UNIQUE (article_id, start_pos, end_pos, code_id, user_id)
);
CREATE INDEX idx_annotations_article ON annotations (article_id, user_id);
CREATE INDEX idx_annotations_code ON annotations (code_id);

CREATE TABLE codebook_events (
    id BIGSERIAL PRIMARY KEY,
    occurred_at TIMESTAMPTZ NOT NULL,
    user_id UUID NOT NULL REFERENCES users(id),
    action TEXT NOT NULL,
    code_id UUID NOT NULL,
    details JSONB NOT NULL DEFAULT '{}'
);
```

**Conventions**

- Positions are 0-based Unicode code points with an **exclusive end**, so `full_text[start_pos:end_pos] == quote` in Python. REFI-QDA export converts positions later, in its own code.
- `articles.full_text` is the only source of positions. Never normalize it.
- `text_sha256` is the SHA-256 of the UTF-8 `full_text` at coding time.
- A passage with two codes is two rows.
- `article_id` is not a database foreign key, because articles live in the corpus file. Validate it in the API.
- The old `article_annotations` table in the corpus DB has 0 rows and is not migrated.

**Seed data:** when `codes` is empty, create the current presets as a tree by splitting at `:`. For example, `Autonomy:Competences` becomes `Autonomy` > `Competences`. Leave out `Custom Tag`.

## 5. Accounts and permissions

- **Individual accounts.** The Workbench's shared team password can't work here, because segments need a provable owner.
- Passwords are hashed with Argon2. Sessions are random tokens stored hashed, sent as an `HttpOnly`, `Secure`, `SameSite=Lax` cookie, and expire after 12 hours. Limit login attempts per username and IP address.
- There is no self-signup. A CLI command creates the first lead, and leads then add, reset and deactivate users in the UI. Deactivated users keep their segments and lose access.
- Every API route except `/api/health` and `/api/auth/login` requires a session.

| Action | Coder | Lead |
|---|---|---|
| Read articles and the codebook | Yes | Yes |
| Add segments, and edit or delete own segments | Yes | Yes |
| Edit or delete another user's segments | No | No |
| See other coders' segments | Yes | Yes |
| Create a code | Yes | Yes |
| Edit, rename, move, merge or delete a code | No | Yes |
| Manage users | No | Yes |
| Export all data as CSV | Yes | Yes |

## 6. Codebook rules

| Operation | Rule |
|---|---|
| Create | Name required and unique among siblings, ignoring case |
| Rename | The ID stays the same, so segments follow automatically |
| Move | Refuse moves that would create a cycle |
| Merge A into B | Confirmation shows affected segment and coder counts. See below |
| Delete | Only with no segments and no children; otherwise refuse and suggest merging |

**Merge runs in one transaction:**

1. Move A's segments to B.
2. If that would duplicate a segment for the same span and coder, keep B's row. If the memos differ, append A's memo to it.
3. Re-parent A's children to B.
4. Set `A.merged_into = B`.
5. Write a `codebook_events` row listing the moved segment IDs, so a merge can be reconstructed by hand.

**Stale screens:** another coder may still have a merged code selected. When saving, follow `merged_into` to the current code, and say so in the response so the UI can tell the coder. Hide merged codes from pickers. Log every codebook change in `codebook_events`.

## 7. API

```
GET    /api/health                        status and build version; 200 only if both databases respond
POST   /api/auth/login | /api/auth/logout
GET    /api/me
GET    /api/users  POST /api/users  PATCH /api/users/{id}        lead only
GET    /api/articles/search               query, filters, pagination
GET    /api/articles/{id}                 metadata, metrics and exact full_text
GET    /api/codes  POST /api/codes
PATCH  /api/codes/{id}  DELETE /api/codes/{id}
GET    /api/codes/{id}/merge-preview?into={id}
POST   /api/codes/{id}/merge
GET    /api/articles/{id}/annotations     ?scope=mine|all
POST   /api/articles/{id}/annotations     body: start, end, code_id, memo
PATCH  /api/annotations/{id}  DELETE /api/annotations/{id}
GET    /api/exports/annotations.csv  GET /api/exports/codes.csv
```

**Saving a segment:** the server loads `full_text`, trims whitespace from the selection, recalculates positions, takes the quote from the text, and computes the hash. It never trusts text sent by the browser. An identical existing segment returns the existing one rather than an error.

Keep routers thin, with logic in services. The corpus connection is read-only (`mode=ro`). Search must stay under 200 ms, as `AGENTS.md` requires.

## 8. Frontend

**Reader**

- `segmentText(text, highlights)`: a pure function that splits text at code-point boundaries, handling overlap, nesting, identical spans and touching segments.
- `selectionToCodePoints(range, root)`: the only place that converts browser offsets.
- Render one container with `white-space: pre-wrap`, with spans carrying `data-start` and raw text as React children. Never use `dangerouslySetInnerHTML`. The spans' concatenated text must equal `full_text` exactly.
- Ignore selections that are collapsed, or start or end outside the reader.
- Colors must stay legible in light and dark themes. Mark overlaps with a stronger underline, list all codes in a tooltip, and show other coders' segments as a dashed underline without fill.

**Screens**

- **Login.**
- **Search:** query, source and variety filters, paginated results with snippets. Clicking a result opens it in the reader.
- **Reader:** metadata, article text, a coding panel and a list of visible segments grouped by code. A **Mine** / **All coders** toggle defaults to **Mine**, so coders aren't influenced by each other when double-coding. Stale segments are listed, not highlighted.
- **Codebook:** tree with segment counts, definitions and the Section 6 operations. Definitions also appear in the code picker.
- **Users:** lead only.

**Coding flow**

1. Select text in the reader.
2. The panel shows the trimmed quote, a searchable code picker, a "new code" field and a memo field.
3. Save. The highlight appears without losing scroll position, and the panel clears.

Clicking a highlight opens that segment. Its owner can change the code, edit the memo or delete it, with confirmation; others see it read-only. All interface text is in English for now, and strings should be easy to translate later, because users work in German, Italian and Ladin contexts.

## 9. Text changes and rebuilds

Add `reconcile_annotations`, run by a CLI command after any corpus rebuild. For each annotation whose `text_sha256` no longer matches:

- If `quote` occurs exactly once in the new text, update the positions and hash.
- Otherwise set `status = 'stale'` and keep the row. An article missing from the corpus also makes its segments stale.

Stale segments are never silently deleted. `scripts/rebuild_salto.py` and `scripts/run_harmonization.py` must print a reminder to run this. Because annotations live in PostgreSQL, rebuilding the corpus can't delete them.

## 10. Testing

- **Python:** `pytest` against a real PostgreSQL instance, not SQLite. Cover every Section 5 and 6 rule at the API level, including a coder being refused on another coder's segment and on lead-only routes.
- **Concurrency:** 10 clients each write 50 segments plus codebook changes, with no lost writes.
- **Frontend:** Vitest for `segmentText` and `selectionToCodePoints`.
- **Browser:** Playwright with real corpus cases: non-NFC, emoji, CRLF, Markdown characters and a 4,000-word article. After a selection, `full_text[start:end]` must equal the selected text.
- **CI:** tests run without GPUs, secrets or the copyrighted corpus, so use a small synthetic fixture corpus committed to the repo. Tests using the real corpus are marked and skipped when it is absent.

## 11. Deployment

**Prepare in this phase, following the handbook:** `docker/Dockerfile.backend`, `docker/Dockerfile.frontend` and `docker/nginx.conf.template`; registry-image compose files; `.gitlab-ci.yml`; `.env.example`; `/api/health` with build version; memory limits; pinned dependencies and a pinned PostgreSQL image; `docker-compose.dev.yml` for local work.

**Needs the Admin, so don't do it without Luca:**

- Moving or mirroring the project to a `commul/...` GitLab project. CI may be disabled on the current personal project.
- The app name and URL path, Komodo stacks, data folders, secrets and the first deploy (the "New app" issue).

**Compose rules from the handbook:** no `./data` paths. The corpus file comes from an absolute folder set by the Admin, and PostgreSQL uses a named volume or Admin-set folder. Nobody pushes app images by hand.

**Open questions before hosting**

- May copyrighted full text be served to 10 logged-in users on this infrastructure? Check with Eurac or unibz.
- `scripts/sync_remotes.sh` pushes data to a personal GitLab branch. Decide where the corpus lives once the project is under `commul/`.

## 12. Build order

| Task | Prompt | Depends on | Estimate |
|---|---|---|---|
| 0. Platform skeleton | [`prompts/0_platform_skeleton.md`](prompts/0_platform_skeleton.md) | Nothing | 3–4 days |
| 1. Accounts and codebook | [`prompts/1_accounts_and_codebook.md`](prompts/1_accounts_and_codebook.md) | Task 0 | 1.5 weeks |
| 2. Reader and highlights | [`prompts/2_reader_and_highlights.md`](prompts/2_reader_and_highlights.md) | Task 1 | 3–4 days |
| 3. Select and code | [`prompts/3_select_and_code.md`](prompts/3_select_and_code.md) | Task 2 | 1 week |

Estimates are judgments for one developer, not measurements. Annotators should try the result after Task 3, before any later phase is planned.

## 13. Acceptance criteria for the phase

1. A coder logs in, selects text in German, Italian and Ladin articles, assigns a code, reloads the page, and sees the same exact passage highlighted.
2. Two coders work on the same article at once, and neither loses work. Each sees **Mine** by default and both under **All coders**.
3. A coder can't change another coder's segments or use lead-only routes, even by calling the API directly.
4. A lead nests, renames and merges codes, and segments follow correctly, including while another session has the merged code selected.
5. A corpus rebuild leaves all annotations intact, and changed text produces re-anchored or stale segments, never silent loss.
6. All annotations and codes can be exported as CSV.
7. All tests pass in CI conditions, the containers build and report healthy locally, and the browser makes no external requests.

## 14. Later phases

1. **First deploy** on the FE Server, once the Section 11 questions are settled.
2. **Port the analysis views** from Streamlit, then retire it, about 2–3 weeks (estimate).
3. **Retrieval:** all segments by code, variety, source or coder, across articles.
4. **Agreement:** double-coding assignments, Krippendorff's alpha and disagreement review.
5. **Exchange:** port the QDPX export, add coded segments and import, and confirm the end-position convention by test against a REFI-QDA tool.
6. **GPU service:** embeddings, Stanza and the Ladin pipeline, and possibly an LLM, as a separate image on the GPU VM, built from the handbook's `web-and-gpu` template.
   - The API calls it over HTTP with timeouts, and must keep working without it. No `torch` in the API image.
   - The T4 has 16 GB shared with other services, so agree a memory budget and port with the Admin. The 17–20 GB models considered earlier for synthesis would not fit.
   - Hybrid search currently needs a local encoder socket, so it stays off until this exists.

## 15. Decisions with defaults

These don't block Task 0.

| Question | Default |
|---|---|
| Will coders double-code the same articles? | The design supports it, and **Mine** is the default view |
| Should only leads rename, merge and delete codes? | Yes |
