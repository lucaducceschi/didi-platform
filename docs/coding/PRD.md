# PRD: DIDI Annotation Workbench (Phase 3.1)

**Status:** Direction agreed, not started. Updated 2026-11-06.

**Goal:** Turn DIDI from a Streamlit demo into a web app where different researchers run their own annotation work on the shared corpus, as researchers do in the Speech Workbench, without needing a MAXQDA licence and with all data exportable.

**Development is local for now.** Where the app will be hosted is undecided; a new Azure or Foundry-based setup is possible but not certain. This document therefore sets out product behavior and data rules, and treats technical choices as working assumptions.

## 1. How researchers work

Up to 10 researchers use one app and one corpus, but they don't all do the same job. One may study autonomy framing in German and Italian with one codebook, while another codes language rights in Ladin with a different one.

| Speech Workbench pattern | What it means in DIDI |
|---|---|
| Sign in with your own account | Individual logins, so every annotation has a known author |
| Library of documents showing status and who worked on them | A project library of articles, with each coder's status and counts |
| Each user's work is stored separately, so nobody overwrites anyone | Each coded passage belongs to one researcher, and only they can change it |
| Presence banner instead of locks | "Anna is also working on this article"; nothing is ever blocked |
| Version check when saving shared data (409 on conflict) | Codebook edits and repeated edits to a segment are checked, so a stale screen can't overwrite newer work |
| Activity and audit log | A record of codebook and project changes |
| Gold-standard review as a later stage | Consensus and adjudication come in a later phase, but the data must allow them |

**Projects are the core concept.** A project has a name, a research question, members, its own codebook and its own set of articles. A researcher can be a lead in one project and a coder in another. An article can belong to several projects without any conflict.

## 2. Scope

| # | Delivered in this phase | Replaces today |
|---|---|---|
| 0 | Local React, Python API and database skeleton, with corpus search | Streamlit only |
| 1 | Accounts, projects and per-project codebooks: create, nest, rename, merge, define codes | Free-text analyst name; one flat tag per quote |
| 2 | Project library and article reader, with coded passages highlighted | Notes listed under the article |
| 3 | Select text and code it directly, with presence and per-article progress | Pasting quotes, with no positions stored |

### Not in this phase

The design must not block these, but do not build them:

- Hosting, cloud services and production deployment
- Porting the Radar, Timeline, Focus Events and Keyness views. **Streamlit stays as the analysis demo** until they are ported
- Assigning articles to specific people
- Cross-article retrieval of segments by code
- Inter-coder agreement, adjudication and gold-standard coding
- QDPX export of coded segments, and QDPX import
- PDF, audio, video or image coding
- AI assistance and GPU services

### Rules that apply throughout

- **Ownership.** Only a segment's author can change it, and the server enforces this.
- **Exact text.** `articles.full_text` is never modified, trimmed or normalized, because positions refer to it.
- **Open data.** Everything stored can be exported as CSV, and the schema is documented.
- **No third-party calls from the browser.** No CDN, web fonts or analytics.
- **Copyright.** Full text, databases and exports never reach the public `origin` remote.
- **Stay portable.** Keep hosting options open (Section 11).

## 3. Working assumptions

These reflect current decisions. They are not locked: if one causes real trouble, propose an alternative and say why.

| Part | Assumption | Why |
|---|---|---|
| Frontend | React with TypeScript and Vite | Requested, and matches the Speech Workbench |
| API | Python with FastAPI | Reuses the existing Python code, and is easy to run anywhere |
| App data | PostgreSQL | Agreed. Suits concurrent research data, and is widely available as a managed service |
| Corpus | The existing SQLite FTS5 file, read-only | A rebuildable artifact that already meets search needs. Can move into PostgreSQL later |

Reuse `src/ui/data_service.py`, which has no Streamlit dependency, along with `src/harmonizers/`, `src/storage/`, `src/nlp/` and the `qdpx` writer. Keep the Streamlit demo working.

## 4. Verified technical basis

Measured in a browser on 2026-11-06. The code is in [`spike/`](spike/). It ran in a Streamlit component, but the position logic is plain browser JavaScript. Task 2 must re-verify it in React.

| Finding | Consequence |
|---|---|
| Browser offsets count UTF-16 units, while Python and REFI-QDA count code points | Convert with `Array.from`, in one module only |
| Offsets matched Python slices for emoji, NFD combining characters, CRLF, Markdown-like text and selections crossing highlight spans | One container with `white-space: pre-wrap` and spans holding the raw text is safe |
| A mouse drag included a trailing space | The server trims whitespace from selections and recalculates positions |

The corpus contains these cases: 1,401 articles are not NFC-normalized, 4 contain characters outside the Basic Multilingual Plane, 3 contain `\r`, and 216 contain Markdown-active characters.

## 5. Data model

This is the logical model. Exact types and migrations are up to the implementer, as long as the constraints below hold.

| Table | Key fields | Constraints |
|---|---|---|
| `users` | username, display name, password hash, is_admin, active | Username unique, ignoring case |
| `projects` | name, description, archived, created by | Name unique, ignoring case |
| `project_members` | project, user, role (`lead` or `coder`) | One role per user per project |
| `project_articles` | project, article_id, added by, added at | One row per article per project |
| `article_progress` | project, article_id, user, status (`in_progress` or `done`), updated at | One row per user per article per project; no row means not started |
| `codes` | project, name, parent, definition, color, sort order, merged_into, revision | Active names unique among siblings, ignoring case |
| `annotations` | project, article_id, user, code, start_pos, end_pos, quote, text_sha256, memo, status (`active` or `stale`), revision, timestamps | `start_pos < end_pos`; unique on project, article, span, code and user |
| `presence` | project, article_id, user, last_seen | One row per user per article per project |
| `activity_log` | time, user, project, action, target, details | Append only |

**Conventions**

- Positions are 0-based Unicode code points with an **exclusive end**, so `full_text[start_pos:end_pos] == quote` in Python. REFI-QDA export converts positions later, in its own code.
- `text_sha256` is the SHA-256 of the UTF-8 `full_text` at coding time.
- A passage with two codes is two rows.
- `article_id` refers to the corpus file, so validate it in the API.
- `revision` increases on each update. An update sending an old revision gets a conflict response and changes nothing.
- The old `article_annotations` table has 0 rows and is not migrated.

## 6. Accounts and permissions

- Individual accounts with hashed passwords (use a current algorithm such as Argon2), and sessions in `HttpOnly` cookies with a sensible expiry. Limit login attempts.
- No self-signup. A CLI command creates the first admin, and admins add, reset and deactivate users. Deactivated users keep their segments and lose access.
- **Keep identity in one place.** All routes get the current user from a single dependency, so institutional login such as Microsoft Entra ID could replace passwords later without touching the rest of the app.

| Action | Coder | Project lead | Admin |
|---|---|---|---|
| See a project's articles, codebook and segments | Members | Members | All |
| Add segments, and edit or delete own segments | Yes | Yes | If a member |
| Edit or delete another user's segments | No | No | No |
| Create a code | Yes | Yes | If a member |
| Edit, rename, move, merge or delete a code | No | Yes | If a lead |
| Add articles and manage members | No | Yes | All |
| Export the project's data | Yes | Yes | All |
| Create projects | No | No | Yes |
| Manage users | No | No | Yes |

## 7. Codebook rules

Each project has its own codebook. A new project can start empty, copy another project's codebook, or use a starter set built from the current presets by splitting at `:` (so `Autonomy:Competences` becomes `Autonomy` > `Competences`, leaving out `Custom Tag`).

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
5. Log the moved segment IDs in `activity_log`, so a merge can be reconstructed by hand.

**Stale screens:** another coder may still have a merged code selected. When saving, follow `merged_into` to the current code, and tell the coder. Hide merged codes from pickers.

## 8. Screens and flow

- **Login.**
- **Projects:** the projects you belong to, with your progress in each. Admins can create projects and manage users.
- **Project library:** the project's articles, filterable by variety, source and status, showing who has worked on each and how many segments they made. This mirrors the Workbench's library.
- **Add articles:** corpus search with filters. Add selected results, or all matches, to the project.
- **Reader:** metadata, article text, the coding panel, and a list of visible segments grouped by code.
- **Codebook:** tree with segment counts, definitions and the Section 7 operations.
- **Project activity:** recent codebook and project changes.

**Coding**

1. Open an article from the library.
2. Select text. The panel shows the trimmed quote, a searchable code picker with definitions, a "new code" field and a memo field.
3. Save. The highlight appears without losing scroll position, and the panel clears.
4. Mark the article done when finished. It can be reopened.

Clicking a highlight opens that segment. Its owner can change the code, edit the memo or delete it, with confirmation; others see it read-only.

**Working alongside others**

- A **Mine** / **All coders** toggle defaults to **Mine**, so researchers aren't influenced by each other.
- A banner shows who else has the article open, with a heartbeat every 30 seconds and a 90-second timeout. It never blocks anyone.

**Saving a segment:** the server loads `full_text`, trims whitespace from the selection, recalculates positions, takes the quote from the text, and computes the hash. It never trusts text sent by the browser. An identical existing segment returns the existing one rather than an error.

**Reader rendering**

- Render one container with `white-space: pre-wrap`, with spans carrying `data-start` and raw text as React children. Never use `dangerouslySetInnerHTML`. The spans' concatenated text must equal `full_text` exactly.
- Do the browser-offset conversion in one function, and ignore selections that are collapsed, or start or end outside the reader.
- Colors must stay legible in light and dark themes. Mark overlaps with a stronger underline and list all codes in a tooltip. Show other coders' segments as a dashed underline without fill.

All interface text is in English for now, in a form that's easy to translate later.

## 9. Text changes and rebuilds

Add a `reconcile_annotations` command to run after any corpus rebuild. For each annotation whose `text_sha256` no longer matches:

- If `quote` occurs exactly once in the new text, update the positions and hash.
- Otherwise set `status = 'stale'` and keep the row. An article missing from the corpus also makes its segments stale.

The reader lists stale segments instead of highlighting them. They are never silently deleted. Corpus rebuild scripts print a reminder to run this command.

## 10. Testing

- **API:** `pytest` against a real PostgreSQL instance. Cover every permission in Section 6 by calling the API directly, including a coder refused on another's segment, and a non-member refused on a project.
- **Isolation:** projects can't see each other's codes, segments or members.
- **Concurrency:** 10 clients each write 50 segments plus codebook changes, with no lost writes. A stale revision gets a conflict.
- **Frontend:** unit tests for splitting text at highlights and for offset conversion.
- **Browser:** Playwright with real corpus cases: non-NFC, emoji, CRLF, Markdown characters and a 4,000-word article. After a selection, `full_text[start:end]` must equal the selected text.
- **Fixtures:** tests run without the copyrighted corpus, using a small synthetic fixture committed to the repo. Tests using the real corpus are marked and skipped when it is absent.

## 11. Local development and portability

**Now:** one documented command starts the app locally, using PostgreSQL in Docker and the existing corpus file. All tests run with one command. Document how to back up and restore the database, because annotations are research data from day one.

**To keep hosting open:**

- All settings come from environment variables, with `.env.example` documenting them. No hostnames, paths or secrets in code.
- Plain PostgreSQL features only, and standard containers when the time comes.
- No cloud-specific SDKs in application code.
- Any future AI or GPU feature sits behind a small HTTP client and is optional, so the app keeps working without it. It could be a local service or a hosted model. Sending corpus text to a hosted model raises the copyright question in Section 14.

Don't write production Dockerfiles, CI or infrastructure code in this phase.

## 12. Build order

| Task | Prompt | Depends on | Estimate |
|---|---|---|---|
| 0. Local skeleton | [`prompts/0_local_skeleton.md`](prompts/0_local_skeleton.md) | Nothing | 2–3 days |
| 1. Accounts, projects and codebook | [`prompts/1_accounts_projects_codebook.md`](prompts/1_accounts_projects_codebook.md) | Task 0 | 2 weeks |
| 2. Library, reader and highlights | [`prompts/2_library_and_reader.md`](prompts/2_library_and_reader.md) | Task 1 | 1 week |
| 3. Select and code | [`prompts/3_select_and_code.md`](prompts/3_select_and_code.md) | Task 2 | 1 week |

Estimates are judgments for one developer, not measurements. Researchers should try the result after Task 3, before any later phase is planned.

## 13. Acceptance criteria for the phase

1. Two researchers with separate projects and codebooks work on the same article, and neither sees the other's project.
2. A researcher selects text in German, Italian and Ladin articles, assigns a code, reloads the page, and sees the same exact passage highlighted.
3. Two coders in one project work on the same article at once, see the presence banner, and neither loses work. Each sees **Mine** by default and both under **All coders**.
4. A coder can't change another coder's segments or use lead-only actions, even by calling the API directly.
5. A lead nests, renames and merges codes, and segments follow correctly, including while another session has the merged code selected.
6. The library shows the correct status and counts per coder.
7. A corpus rebuild leaves all annotations intact, and changed text produces re-anchored or stale segments, never silent loss.
8. All of a project's annotations and codes can be exported as CSV.
9. All tests pass, the browser makes no third-party requests, and the Streamlit demo still runs.

## 14. Later phases

Order to be decided after researchers try Task 3.

- **Hosting:** where it runs, login method and backups. Before hosting, check whether full text may be served to up to 10 users, or sent to a hosted model.
- **Port the analysis views**, then retire Streamlit (about 2–3 weeks, estimated).
- **Assignments:** leads assign articles to coders.
- **Retrieval:** all segments by code, variety, source or coder, across articles.
- **Agreement and gold standard:** double-coding, Krippendorff's alpha, adjudication and an approved consensus version, as in the Workbench's gold stage.
- **Exchange:** port the QDPX export, add coded segments and import, and confirm the end-position convention by test against a REFI-QDA tool.
- **AI assistance:** optional and behind the HTTP client in Section 11.

## 15. Open questions

These have working defaults, so they don't block Task 0.

| Question | Default |
|---|---|
| Does each researcher need their own codebook, or do teams share one? | One codebook per project, so both work: put people in the same project or in different ones |
| How will researchers try it before hosting is decided? | Luca runs it on one machine for a supervised session, which needs no hosting |
| Should coders in a project see each other's work at all? | Yes, with **Mine** as the default. A lead-controlled blind mode can come with the agreement phase |
