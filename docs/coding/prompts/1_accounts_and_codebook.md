# Task 1: Accounts and codebook

You are working in the DIDI Platform repository, now a React and FastAPI app (Task 0) alongside the original Streamlit demo. This phase lets up to 10 annotators code article text in DIDI instead of using MAXQDA. This task adds coder accounts, the coding database and the shared codebook.

## Read first
1. `AGENTS.md`
2. `docs/coding/PRD.md`, especially Sections 4, 5, 6, 7 and 9
3. Handbook page `docs/07-secrets-and-security.md` in `commul/lt-developer-handbook`, read with `glab`
4. `backend/app/` and `frontend/src/`, for the patterns set in Task 0
5. `scripts/rebuild_salto.py` and `scripts/run_harmonization.py`

Check `git status` first. If Task 0 isn't merged, or the tree isn't clean, stop and ask Luca.

## Build
1. **Schema:** add Alembic migrations with the exact schema in PRD Section 4, including seed codes.
2. **Accounts:** login, logout and sessions as in PRD Section 5, and a CLI command to create the first lead. Protect all existing routes. Add a login page and a Users page for leads.
3. **Codebook API and screen:** the routes in PRD Section 7 and the rules in Section 6, with permissions enforced on the server. Merge shows affected segment and coder counts before confirming. Log every change in `codebook_events`.
4. **Annotation API:** create, update, delete and list, as in PRD Section 7, including the server-side trimming and quote extraction. Only the owner can change a segment. There's no frontend for this yet, because Tasks 2 and 3 add it.
5. **Reconcile:** add the command in PRD Section 9, and the reminder in the rebuild scripts.
6. **Exports:** the two CSV routes, with one row per segment including coder, full code path, positions, quote, memo and status. Add download buttons in the UI.

## Tests
Against a real PostgreSQL instance:
- Every permission in the PRD Section 5 table, by calling the API directly as each role, and logged out
- Passwords are never returned or logged, and sessions expire
- Name uniqueness ignores case among siblings, and cycles are refused
- Merge handles duplicates and memos correctly, and rolls back fully on failure
- A segment saved with a merged code goes to the current code, and the response says so
- The server trims selections, and rejects positions out of range or an empty selection
- The 10-client concurrency test in PRD Section 10
- Reconcile re-anchors unique quotes, and marks the others stale, including articles no longer in the corpus

## Do not
- Change `articles.full_text`, or normalize any text.
- Build the reader or text selection. Those are Tasks 2 and 3.
- Add retrieval views, agreement statistics or QDPX changes.
- Touch the Streamlit annotation form. Task 3 removes it.
- Commit real passwords, or commit or push until Luca asks.

## Done when
- All tests pass, and the migrations run on an empty database.
- In a browser, you can log in as a lead, add a coder, build a nested codebook, rename and merge codes, and download both CSVs. Then log in as the coder and confirm that lead actions are unavailable.

Report what you built, what you verified and how, any departures from the PRD and why, and anything still open.
