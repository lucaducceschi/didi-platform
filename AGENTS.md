# DIDI Platform: Agent Guidelines & Project Instructions

<!-- agents-marker: didi-platform-v1 -->

This file is the shared instruction manual for all AI coding agents working on the DIDI Platform repository (Claude Code, Antigravity/Gemini, etc.).

---

## 1. Project Context & Objectives

The **DIDI Platform** is an academic mixed-methods research workbench developed for Eurac Research and the University of Innsbruck. It analyzes how regional autonomy, minority rights and socio-political events in South Tyrol are framed for different language communities.

**Scope since 2026-11-07: German and Italian only.** Ladin is deferred until Luca's new Ladin NLP pipeline is ready. Don't build or test Ladin-specific features, keep everything language-specific behind one per-language definition, and never delete the Ladin data (see [`docs/PRD.md`](docs/PRD.md), Sections 2 and 7).
- **German (`de`):** *Die Neue Südtiroler Tageszeitung*, *Salto.bz*
- **Italian (`it`):** *Salto.bz*
- **Planned:** *Landespresseamt / Ufficio Stampa Provincia Autonoma di Bolzano* (`news.provinz.bz.it` / `news.provincia.bz.it`), labeled `source_type: "official_press"` to separate institutional from journalistic discourse, and more German and Italian outlets.
- **Deferred:** Ladin (`lld_gherd`, `lld_badia`, `lld_fascia`) from *La Usc di Ladins* and *RaiNews TGR TRAIL*. These articles stay in the corpus database and still appear in the Streamlit demo.

**Provenance Rule:** All German and Italian text must be verified regional South Tyrolean production. Never ingest syndicated wire agency feeds (ANSA, APA, dpa); always enforce category isolation, byline checks, and gazetteer validation (see [`docs/PRD.md`](docs/PRD.md#6-corpus-and-provenance-for-german-and-italian)). These checks are planned but not yet computed.

**Living Product Specification:** See [`docs/PRD.md`](docs/PRD.md) for scope, the corpus, principles and the roadmap, and [`docs/coding/PRD.md`](docs/coding/PRD.md) for the annotation workbench.

---

## 2. Core Architecture & Storage Boundaries

```
Raw Archives (Tageszeitung, Salto, La Usc, RaiNews TRAIL)
                        ↓
            Harmonization Pipeline (`src/harmonizers/`)
                        ↓
     Canonical SQLite FTS5 DB (`data/processed/didi_corpus.db`, local only)
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
  - Private mirror with `assets/` and raw articles (`data/raw/`) on the `full-data` branch.
- **Databases stay local (decided 2026-11-09, review by 2027-01-09):** `data/processed/didi_corpus.db` (about 430 MB) and `didi_words.db` (about 6.3 GB) are in no remote. They are gitignored, and `sync_remotes.sh` refuses any file over 100 MB. They can be rebuilt from `~/Data/KST/cluster/` with `scripts/import_kst_tageszeitung.py`. By 2027-01-09, decide on a lasting backup (an institutional drive, Git LFS, or rebuild only); `sync_remotes.sh` prints a reminder from that date.
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
- [x] **Core Ingestion & NLP:** 12,220 articles (2.57M tokens) harmonized into `data/processed/didi_corpus.db`.
- [x] **Stanza MFD 2.0 Engine:** Lexicons compiled and validated for `de`, `it`, and `lld` (`assets/mfd_compiled_lemmas.json`).
- [x] **Day 1: Data Service & App Shell:** Create `src/ui/data_service.py` and initial `src/ui/app.py` skeleton.
- [x] **Day 2: View 1 (Explorer):** FTS5 search, facet filters, paginated snippet cards.
- [x] **Day 3: View 2 (Framing Radar):** Plotly 5-axis MFT radar overlay and Plutchik emotion distribution.
- [x] **Day 4: View 3 (Temporal Dynamics):** Monthly time-series of sentiment and moral framing (2017–2026).
- [x] **Day 5: View 4 (Focus Events & Meaning-Making):** Grounded in Hurtado-Bodell & Menshikova (2026); Dunning G² keyness + Jensen-Shannon Moral Foundations Divergence Index (MFDI).
- [x] **Day 5b: View 5 (Article Deep Dive):** Full-text reader with colored token annotations and JSON metadata inspector.
- [x] **Day 6: Export & Polishing:** CSV export for research subsets with APA citations + Dunning G² keyness table export.
- [x] **Day 7: Packaging & Docker:** Final verification, Docker containerization (`docker-compose up didi-ui`), and demo walkthrough.
- [ ] **Phase 2.2: MAXQDA QDPX Export:** Article and metadata export built (`src/ui/qdpx.py`, tests in `tests/`); awaiting an import test in MAXQDA. Coded segments not started.
- [ ] **Phase 3.1: Annotation Workbench:** React and Python app where up to 10 researchers run their own annotation projects, per [`docs/coding/PRD.md`](docs/coding/PRD.md). Developed locally; hosting undecided. Tasks 0–4 built (local skeleton; accounts, projects, codebook; library, reader, highlights; select and code; retrieval and article management). No researcher trial yet. New features go there; the Streamlit app in `src/ui/` stays as the analysis demo until its views are ported.
- [x] **Phase 2.1: Qualitative Annotations & Codebook:** SQLite persistent storage (`article_annotations`), inline quote highlight form, card badges, and CSV codebook export.
- [x] **Phase 2 / Task 5: Tageszeitung Ingestion & Word Layer:** Ingested 79,172 new Tageszeitung articles (79,303 total, 2015–2025) into `data/processed/didi_corpus.db` (412 MB) and 30,275,813 Stanza word tokens for 79,293 articles into `data/processed/didi_words.db` (5.9 GB). Sub-2ms token lookups via `DataService` and `backend.app.services.words`.
- [ ] **Next (per [`docs/PRD.md`](docs/PRD.md), Section 7):** Phase 1 (pluggable language scope: German and Italian active), then Phase 3 (measures in the app, linked to codes, computed directly over the word layer).
- [ ] **Later: Ladin.** Returns as a new language once Luca's Ladin NLP pipeline works, a Ladin speaker has reviewed the variety labels, and Ladin dictionaries are rebuilt and validated.

