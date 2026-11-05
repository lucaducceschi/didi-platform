# DIDI Platform: Agent Guidelines & Project Instructions

<!-- agents-marker: didi-platform-v1 -->

This file is the shared instruction manual for all AI coding agents working on the DIDI Platform repository (Claude Code, Antigravity/Gemini, etc.).

---

## 1. Project Context & Objectives

The **DIDI Platform** is an academic mixed-methods research workbench developed for Eurac Research and the University of Innsbruck. It analyzes how regional autonomy, minority language rights, and socio-political events in South Tyrol and the Dolomitic Ladin valleys are framed across three linguistic communities and five varieties:
- **German (`de`):** *Die Neue Südtiroler Tageszeitung*, *Salto.bz*
- **Italian (`it`):** *Salto.bz*
- **Ladin (`lld_gherd`, `lld_badia`, `lld_fascia`):** *La Usc di Ladins*, *RaiNews TGR TRAIL*

**Living Product Specification:** See [`docs/PRD.md`](docs/PRD.md) for full functional requirements, user personas, and the 7-day interactive demo roadmap.

---

## 2. Core Architecture & Storage Boundaries

```
Raw Archives (Tageszeitung, Salto, La Usc, RaiNews TRAIL)
                        ↓
            Harmonization Pipeline (`src/harmonizers/`)
                        ↓
     Canonical SQLite FTS5 DB (`data/processed/didi_corpus.db` [44 MB])
                        ↓
  Quantitative NLP Engine (`src/nlp/`: Lexical + NRC Emotions + MFD 2.0)
                        ↓
  Interactive Web Workbench (`src/ui/`: Streamlit + Plotly)
```

### Critical Dual-Remote Git Governance (Mandatory Rule)
- **Public GitHub (`origin` -> `git@github.com:lucaducceschi/didi-platform.git`):**
  - Public profile repository.
  - Code, documentation, scripts, and copyright-safe derived metadata ([`data/processed/didi_corpus.jsonl`](data/processed/didi_corpus.jsonl) with `full_text` omitted).
  - **NEVER** push full-text databases (`*.db`), raw scraped files (`data/raw/`), or third-party dictionary assets (`assets/`) to `origin`.
- **Private Institutional GitLab (`gitlab` -> `git@gitlab.inf.unibz.it:Luca.Ducceschi/didi-platform.git`):**
  - Project ID `8364`.
  - Private mirror containing the entire research environment, including `assets/`, `didi_corpus.db`, and raw articles on the `full-data` branch.
- **Syncing Remotes:** Always use [`./scripts/sync_remotes.sh`](scripts/sync_remotes.sh) to push commits to both remotes in a single synchronized operation.

---

## 3. UI Implementation Guidelines (1-Week Demo)

All frontend code for the research demo lives in `src/ui/`:
1. **Separation of Concerns:**
   - Keep SQL queries and pandas transformations inside `src/ui/data_service.py`. Wrap all DB access with `@st.cache_data`.
   - Keep UI layout, sidebar filters, and Plotly charts modularized inside `src/ui/components/` and `src/ui/app.py`.
2. **Performance Constraints:**
   - Database queries against [`data/processed/didi_corpus.db`](data/processed/didi_corpus.db) must execute in $< 200\text{ ms}$ using SQLite FTS5 and indexed metadata columns (`publish_date`, `source`, `language`).
   - The app must run completely offline without external internet calls.
3. **Typography & Styling:**
   - Clean, academic, neutral palette suited for Eurac Research and University of Innsbruck presentations.
   - Text snippets must highlight search terms and display visual badges for Sentiment, NRC Emotion, and Moral Foundations.

---

## 4. Current Milestone & Status Tracker

Reference [`docs/PRD.md`](docs/PRD.md#6-one-week-implementation-plan-day-by-day) for detailed task specifications:
- [x] **Core Ingestion & NLP:** 12,624 articles (2.77M tokens) harmonized into `data/processed/didi_corpus.db`.
- [x] **Stanza MFD 2.0 Engine:** Lexicons compiled and validated for `de`, `it`, and `lld` (`assets/mfd_compiled_lemmas.json`).
- [x] **Day 1: Data Service & App Shell:** Create `src/ui/data_service.py` and initial `src/ui/app.py` skeleton.
- [x] **Day 2: View 1 (Explorer):** FTS5 search, facet filters, paginated snippet cards.
- [x] **Day 3: View 2 (Framing Radar):** Plotly 5-axis MFT radar overlay and Plutchik emotion distribution.
- [x] **Day 4: View 3 (Temporal Dynamics):** Monthly time-series of sentiment and moral framing (2017–2026).
- [x] **Day 5: View 4 (Article Deep Dive):** Full-text reader with colored token annotations.
- [ ] **Day 6: Export & Polishing:** CSV/Excel export for research subsets + responsive styling.
- [ ] **Day 7: Packaging & Docker:** Final verification and `docker-compose up didi-ui`.

