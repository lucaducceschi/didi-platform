# Task 1: Accounts, projects and codebook

You are working in the DIDI Platform repository, now a local React and Python app (Task 0) alongside the original Streamlit demo. In this phase, up to 10 researchers run their own annotation projects on a shared corpus, instead of using MAXQDA. This task adds accounts, projects and per-project codebooks.

## Read first
1. `AGENTS.md`
2. `docs/coding/PRD.md`, especially Sections 1, 5, 6, 7 and 9
3. The backend and frontend code from Task 0
4. `scripts/rebuild_salto.py`, `scripts/relabel_ladin.py` and `scripts/run_harmonization.py`

Check `git status` first. If Task 0 isn't merged, or the tree isn't clean, stop and ask Luca.

## Build
1. **Schema:** migrations for the data model in PRD Section 5, keeping every listed constraint. Choose exact types yourself, and document the schema in `docs/coding/SCHEMA.md`.
2. **Accounts:** login, logout and sessions, a CLI command to create the first admin, and an admin screen for users. Protect all existing routes, and get the current user from one dependency only, as in PRD Section 6.
3. **Projects:** create, edit and archive projects, and manage members and roles. Add a Projects screen.
4. **Codebook:** API and screen following PRD Section 7, including the three ways to start a codebook. Merge shows affected segment and coder counts before confirming. Codebook edits use the revision check and return a conflict on a stale revision, which the UI explains.
5. **Annotation API:** create, update, delete and list, with server-side trimming and quote extraction as in PRD Section 8. Only the author can change a segment. There's no frontend for this yet.
6. **Activity log:** record codebook and project changes, and add a Project activity screen.
7. **Reconcile:** add the command in PRD Section 9, and the reminder in the rebuild scripts.
8. **Exports and backup:** per-project CSV downloads for annotations (with coder, full code path, positions, quote, memo and status) and codes. Document database backup and restore.

## Tests
Against a real PostgreSQL instance:
- Every permission in the PRD Section 6 table, by calling the API directly as each role, as a non-member, and logged out
- Project isolation: no access to another project's codes, segments or members
- The same user being a lead in one project and a coder in another
- Passwords are never returned or logged, and sessions expire
- Name uniqueness ignores case among siblings, and cycles are refused
- Merge handles duplicates and memos correctly, and rolls back fully on failure
- A segment saved with a merged code goes to the current code, and the response says so
- A stale revision gets a conflict and changes nothing
- The server trims selections, and rejects positions out of range or an empty selection
- The 10-client concurrency test in PRD Section 10
- Reconcile re-anchors unique quotes, and marks the others stale, including articles no longer in the corpus

## Do not
- Change `articles.full_text`, or normalize any text.
- Build the library, reader or text selection. Those are Tasks 2 and 3.
- Add assignments, retrieval views, agreement statistics or QDPX changes.
- Touch the Streamlit annotation form. Task 3 removes it.
- Add cloud SDKs, or commit real passwords.
- Commit or push until Luca asks.

## Done when
All tests pass, and migrations run on an empty database. In a browser:
- As admin, create two users and two projects with different codebooks.
- As a lead, nest, rename and merge codes, and download both CSVs.
- As a coder, confirm lead actions are unavailable and the other project isn't visible.

Report what you built, what you verified and how, any departures from the PRD and why, and anything still open.
