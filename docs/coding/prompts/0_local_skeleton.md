# Task 0: Local skeleton

You are working in the DIDI Platform repository, a research tool for comparing German, Italian and Ladin media discourse. It is currently a Streamlit demo over a SQLite corpus. You are starting its move to a React and Python web app where researchers run their own annotation projects. Development is local, and hosting is undecided.

## Read first
1. `AGENTS.md`
2. `docs/coding/PRD.md`, especially Sections 2, 3, 10 and 11
3. `src/ui/data_service.py`
4. Optionally, `/Users/luca/Gits/speech-workbench/frontend/` for frontend conventions. Do not change anything in that repo.

Check `git status` first. If the tree isn't clean, stop and ask Luca. The technical choices in PRD Section 3 are working assumptions: if one causes real trouble, say so and propose an alternative rather than working around it.

## Build
1. **Service reuse:** let the API call `DataService` without importing Streamlit. Move it only if needed, and keep the Streamlit demo working. Open the corpus read-only for API use.
2. **Backend:** a Python API in `backend/` with:
   - A health route that really checks both databases
   - Corpus search with query, source and variety filters and pagination
   - Article detail with metadata, metrics and exact `full_text`

   Settings come from environment variables, documented in `.env.example`. Set up database migrations with an empty first migration.
3. **Frontend:** a React and TypeScript app in `frontend/`, with a typed API client, a search page, and a plain article page showing metadata and text with `white-space: pre-wrap`. Support light and dark themes with a neutral, academic look, and no external fonts or scripts.
4. **Local running:** PostgreSQL in Docker, and one documented command that starts everything using the existing local corpus file. One command also runs all tests.
5. **Tests:** a small synthetic fixture corpus committed to the repo with no copyrighted text, API tests against it, and frontend test setup with one real test.
6. **Docs:** update `README.md` and `AGENTS.md` with how to run both the new app and the Streamlit demo.

## Do not
- Build login, projects, annotations or the codebook. Those come in Tasks 1–3.
- Port the analysis views, or remove Streamlit.
- Add production Dockerfiles, CI, infrastructure code or cloud SDKs.
- Add `torch` or `transformers` to the API. Search is keyword-only for now.
- Put the corpus, `.env` or any copyrighted text in git.
- Commit or push until Luca asks.

## Done when
- All tests pass with the single test command.
- The app starts with the single start command, and you can search and open a Ladin, a German and an Italian article in a browser. Include screenshots.
- Article text in the API response matches the database exactly, including an NFD and a CRLF article.
- A search takes under 200 ms against the real corpus, measured.
- The Streamlit app still runs.
- A browser test finds no third-party requests.

Report what you built, how you verified it, and any departures from the PRD and why.
