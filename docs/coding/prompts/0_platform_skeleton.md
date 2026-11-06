# Task 0: Platform skeleton

You are working in the DIDI Platform repository, a research tool for comparing German, Italian and Ladin media discourse. It is currently a Streamlit demo over a SQLite corpus. You are starting its move to a React and Python web app, based on the infrastructure of the Speech Workbench.

## Read first
1. `AGENTS.md`
2. `docs/coding/PRD.md`, especially Sections 1, 2, 10 and 11
3. The LT Developer Handbook, with `glab` on `gitlab.inf.unibz.it`, project `commul/lt-developer-handbook`: `README.md`, `docs/02-new-project.md`, `docs/03-repo-requirements.md`, `docs/04-ci-cd.md`, `docs/07-secrets-and-security.md`, and the `templates/` folder. If you can't reach it, stop and ask Luca.
4. `/Users/luca/Gits/speech-workbench`, as a reference: `AGENTS.md`, `frontend/package.json`, `frontend/src/api/client.ts`, `docker/nginx.conf.template`, `docker/Dockerfile.frontend`. Do not change anything in that repo.
5. `src/ui/data_service.py`

Check `git status` first. If the tree isn't clean, stop and ask Luca.

## Build
1. **Service move:** move `src/ui/data_service.py` to `src/services/data_service.py`, leaving a thin import so Streamlit keeps working. Do not change behavior. Open the corpus read-only for API use.
2. **Backend:** create `backend/app/` with FastAPI and these routes, without login for now:
   - `GET /api/health`: build version, plus a real check of both databases
   - `GET /api/articles/search`: query, source and variety filters, pagination
   - `GET /api/articles/{id}`: metadata, metrics and exact `full_text`

   Add settings from environment variables with safe defaults, with no secrets in code. Use SQLAlchemy 2 and Alembic with an initial empty migration.
3. **Frontend:** create `frontend/` with React 19, TypeScript, Vite, Zustand and oxlint, matching the Workbench's versions where practical. Include:
   - A typed API client
   - A search page with filters and paginated results
   - A plain article page showing metadata and text, with `white-space: pre-wrap`
   - Light and dark themes, using a neutral, academic look
   - No external fonts or scripts
4. **Local development:** add `docker-compose.dev.yml` with PostgreSQL (pinned version), backend and frontend. One documented command must start everything using the existing local corpus file.
5. **Tests:** a small synthetic fixture corpus committed to the repo with no copyrighted text, API tests against it, and a Vitest setup with one real test.
6. **Containers and CI:** create Dockerfiles, `nginx.conf.template`, registry-image compose files, `.env.example`, `.dockerignore` and `.gitlab-ci.yml` from the handbook templates. Set up the `web` template only, with no GPU part. Test and build jobs must work; leave deploy jobs inactive until a Komodo stack exists. Use a placeholder for the final `commul/...` image path and say so in your report.
7. **Docs:** update `README.md` and `AGENTS.md` with how to run both the new app and the Streamlit demo. Add the required `.gitlab/merge_request_templates/default.md`.

## Do not
- Build login, annotations or the codebook. Those are Tasks 1–3.
- Port the analysis views, or remove Streamlit. It must keep working.
- Add `torch` or `transformers` to the API image. Search is keyword-only for now.
- Move the project to `commul/`, push images or contact the Admin. Luca handles that.
- Commit or push until Luca asks.
- Put the corpus, `.env` or any copyrighted text in git or in an image.

## Done when
- `pytest` and the frontend build, lint and tests pass.
- The dev stack starts with one command, and you can search and open a Ladin, a German and an Italian article in a browser. Include screenshots.
- `docker compose -f <file> config` passes for every compose file, and both images build locally and report healthy.
- A search takes under 200 ms against the real corpus, measured.
- The Streamlit app still runs.
- A browser test finds no external requests.

Report what you built, how you verified it, every departure from the PRD or handbook, and what the Admin will need for the first deploy.
