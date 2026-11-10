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
  - **NEVER** push full-text databases (`*.db`), raw scraped files (`data/raw/`), third-party dictionary assets (`assets/`), or the manuscript (`paper/`) to `origin`.
- **Private Institutional GitLab (`gitlab` -> `git@gitlab.inf.unibz.it:Luca.Ducceschi/didi-platform.git`):**
  - Project ID `8364`.
  - Private mirror with `assets/`, raw articles (`data/raw/`) and the manuscript (`paper/`, private since 2026-11-10) on the `full-data` branch.
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
- [x] **Task 6 / Stage 1: Pluggable Language Scope:** Centralized registry in `src/languages.py` (`de`, `it` active; Ladin varieties deferred). User-facing lists, facets, search, library, passages, and exports restrict to active languages. Unconfigured articles/passages preserved in DB and reported via `hidden_articles` / `hidden_passages` to project leads.
- [x] **Task 7: Language Scope Fixes & Open Italian Sources:** Fixed Stage 1 (Ladin visible by default in Streamlit demo, single thesaurus in `src/languages.py`, restored position/CRLF/NFD fixtures). Built graceful crawler package `src/collectors/` (honest user-agent, 3s throttle, strict robots.txt, trafilatura extractor, SimHash dedup). Harvested and imported **22,371 new articles** into `data/processed/didi_corpus.db` (11,355 official press releases vs 349 journalism articles: 328 Salto, 21 RAI; 10,928 bilingual pairs linked).
- [x] **Task 8: Italian Journalism, Provenance Corrections & Source Types:** Corrected Task 7 docs and press office collector (stable sorting, retry only 5xx/429/network errors, reset checkpoint to 0 on completion, raw gzipped API responses with SHA-256). Filtered Salto subscription-gated pages to collect only free open articles. Ingested 60 new Italian Salto articles into `didi_corpus.db` (now 113,823 total articles, Italian journalism at 409 articles: 388 Salto, 21 RAI TGR). Separated journalism from official press across search, Add articles, library, passages, CSV exports, and bilingual twin links.
- [x] **Task 9: Language-Aware Readability Quantitative Metrics:** Implemented validated readability indices in `src/nlp/readability.py` calibrated per language (Italian: Gulpease index & Flesch-Vacca; German: Wiener Sachtextformel WSTF & Flesch-Amstad; Cross-linguistic: LIX and structural sentence/word lengths). Surfaced dynamically in `DataService.get_article_by_id`, FastAPI backend `ArticleMetrics`, and React frontend reader.
- [x] **Task 6 / Stage 2: Full Corpus Word Layer (Cluster GPU):** Batch-annotated 23,160 articles across German and Italian with Stanza on Eurac HPC (Tesla V100 32GB). Added 9,536,440 tokens with verified character offsets, UPOS, XPOS, feats, lemmas, and NER. Merged into local `data/processed/didi_words.db` (now holds 39,812,253 tokens across 102,453 articles).
- [x] **Streamlit Quantitative Views Ported to React:** Added macro analytics router in FastAPI (`/api/analytics/{radar,timeline,focus-events,keyness}`) and top-level React analytics page at `/analytics` featuring 5-axis Moral Foundations Radar, Plutchik discrete emotions, JSD divergence gauge, 2017–2026 longitudinal timeseries, focus events meaning-making (Hurtado-Bodell & Menshikova 2026), and cross-lingual Dunning G² keyness.
- [x] **Task 6 / Stage 3: Measures Linked to Codes:** Word-span scoring pipeline in `backend/app/services/measures.py` connecting MFD 2.0 (mMPD/it-MFD), NRC discrete emotions, readability, concreteness, nominal ratio, ingroup pronouns (wir/uns/unser, noi/ci/nostro), and Konjunktiv I. Full passage and code CSV exports, click-to-evidence passage drilldown, and interactive reader dictionary layer (`[🔍 Dictionary Layer]`).
- [x] **Task 6 / Stage 4: Cross-Tabulation Comparison Grid:** Dynamic cross-tabulation matrix in `AnalysisTab.tsx` and `backend/app/services/measures.py` (`GET /api/projects/:id/comparison-grid`). Rows grouped by Language, Source, Discourse Type, or Year; columns as Qualitative Codes. Displays metric values, small sample flags (< 30 passages / 1,000 words), top distinctive lemmas, expandable example quotes, 1-click drilldowns to Passages tab, and full CSV matrix export.
- [x] **Task 6 / Stage 5: Direct Quotes Detection & Split:** Rule-based detection engine in `src/nlp/quotes.py` (`quote_rules_v2`) calibrated for German („…“, »…«, "…", ‚…‘) and Italian («…», “…”, „…“, "…"; v2 added the curly marks Salto uses, v1 found 2 quotes in 381 Italian Salto articles). Handles nested quotes and cross-paragraph quotes, filters scare quotes (<= 2 words without verb). The real `didi_words.db` has no `article_quotes` table yet, so quotes are detected on the fly per article. Measures partition in `backend/app/services/measures.py` (`score_tokens(..., quote_spans=...)`) guaranteeing additive metric conservation (`inside_quotes + outside_quotes == total`). Validation not done: `scripts/export_quotes_for_validation.py` writes a stratified, seeded sample (50 quotes + 15 quote-free paragraphs for each of de/it x journalism/official press; local only, it holds article text), labelled with `scripts/validate_quotes.py review` and scored with `... score` (precision, exact boundaries, miss rate, Wilson 95% CIs).
- [x] **DIDI Beta Implementation Mission (Milestones 0–7):** Successfully transitioned the platform to an integrated mixed-methods beta:
  - **M0 Baseline & Benchmarks:** Documented beta architecture, decisions, and integration fixtures in `docs/beta/`.
  - **M1 Search Correctness:** Apostrophe/hyphen escaping, 3 explicit search modes (`exact`, `word_family`, `concept`), transparency drawers, and sub-200ms real search performance across all 113,823 articles.
  - **M2 KWIC Concordance & Passage Linkage:** 3-column KWIC concordance grid with exact character coordinates (`[start_char, end_char]`), deep linking into Reader with auto-scroll and amber highlight, 1-click `"Code 🏷️"` workflow, and corpus breakdown drawers.
  - **M3 Saved Corpus Selections:** PostgreSQL schema (`saved_corpus_selections`, `saved_selection_members`), REST CRUD router, and UI dialogs/drawers for reproducible subcorpora.
  - **M4 Qualitative Workbench & Inter-Coder Reliability:** Cohen's Kappa ($\kappa$) on overlapping spans (IoU $\ge$ 0.3), Landis & Koch benchmarks, code confusion matrices, and reader adjudication deep links.
  - **M5 Generalized Subcorpus Comparison:** 3-mode comparison engine (Subcorpus vs Subcorpus, vs Baseline, or internal Partitions) computing 5-axis Moral Foundations radar overlays, discrete Plutchik emotions, JSD divergence gauges, Dunning $G^2$ keyness, and longitudinal timelines.
  - **M6 Linked Exploratory Workspace:** Interactive Word Bubble & Lexical Dossier modal linked directly to concordance and reader.
  - **M7 Reproducibility & Provenance Manifests:** Academic JSON/Markdown manifest exports (`/exports/manifest.{json,md}`) with APA 7th edition bibliography and complete coordinate auditability.
- [ ] **Next (Post-Beta):** Label the 260-row quote sample (Luca), Multilingual Topic Modeling (BERTopic) & Ladin pipeline.

