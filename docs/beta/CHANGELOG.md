# DIDI Beta Changelog

All notable changes to the DIDI Platform during the Beta Implementation Mission will be documented here per milestone.

## [Milestone 7] - 2026-11-10
### Added
- Provenance & Reproducibility export engine in `backend/app/services/exports.py`:
  - `reproducibility_manifest`: Generates full machine-readable JSON manifest capturing software version (`0.2.0-beta`), canonical coordinate system (`Document ID + [start_char, end_char]`), UD token layers, linguistic scope (`de`, `it`), codebook snapshots, saved selections, inter-coder reliability metrics, and generated APA 7th edition bibliography.
  - `reproducibility_report_markdown`: Academic markdown report formatting provenance tables, codebook definitions, and bibliographic citations.
- REST endpoints in `backend/app/routers/projects.py`:
  - `GET /api/projects/{project_id}/exports/manifest.json`
  - `GET /api/projects/{project_id}/exports/manifest.md`
- Comprehensive end-to-end integration test suite `tests/test_beta_workflow.py` validating the entire 7-stage research journey: Search -> KWIC Concordance -> Exact Coordinate Alignment -> Qualitative Coding -> Inter-Coder Reliability -> Saved Selections -> Subcorpus Comparison -> Reproducibility Manifest.

## [Milestone 6] - 2026-11-10
### Added
- Linked Exploratory Workspace connecting the Word Bubble and Lexical Dossier modal directly to the concordance engine and reader.
- Direct quick actions in `LexicalDossierModal.tsx`:
  - `🔍 KWIC Concordance`: Opens KWIC view in Search with keyword pre-filtered.
  - `📄 Search Articles`: Opens article results list.
  - `📊 Media Radar`: Navigates to longitudinal framing radar.
- Clickable regional representative excerpt: clicking on the excerpt directly opens the keyword in context within the concordance table.

## [Milestone 5] - 2026-11-10
### Added
- Generalized Cross-Subcorpus Comparison Engine in `backend/app/services/comparisons.py` and endpoint `POST /api/projects/{project_id}/selections/compare`.
- Three comparative analysis modes:
  1. Selection A vs Selection B (two distinct saved subcorpora).
  2. Selection A vs Regional Corpus Baseline.
  3. Partitions within Selection A (e.g. German vs Italian, Journalism vs Press, News Sources, or Publication Periods).
- Quantitative comparative metrics:
  - 5-Axis Moral Foundations Radar Overlay with Jensen-Shannon Divergence MFDI gauge.
  - Discrete Plutchik 8 discrete emotions comparison and Emotion JSD.
  - Distinctive differential vocabulary via Dunning's $G^2$ Log-Likelihood keyness with clickable lemmas linking to KWIC concordance.
  - Longitudinal trajectory comparisons over time.
  - Readability indices (Gulpease/WSTF), nominal style ratio, concreteness, and ingroup pronoun density.
- Interactive Subcorpus Comparison view in `AnalysisTab.tsx` (`🔀 Subcorpus Comparison`) with selection dropdowns, side-by-side KPI cards, radar overlay, and keyness charts.

## [Milestone 4] - 2026-11-10
### Added
- Inter-Coder Agreement service `backend/app/services/agreement.py` calculating coding consistency on overlapping text passages (IoU $\ge$ 0.3):
  - Observed agreement ($P_o$) and chance agreement ($P_e$).
  - Pairwise Cohen's Kappa ($\kappa$) with Landis & Koch (1977) benchmark interpretations.
  - Global Cohen's Kappa weighted across all coder pairs.
  - Code Confusion Matrix identifying most frequently confused qualitative code pairs.
  - Disagreements extraction with exact passage quotes and character coordinates.
- REST endpoint `GET /api/projects/{project_id}/codes/inter-coder-agreement`.
- Inter-Coder Reliability view in `AnalysisTab.tsx` (`🤝 Inter-Coder Reliability`):
  - KPI cards for Global $\kappa$, Observed Agreement %, Overlapping Passages, and Disagreements.
  - Pairwise coder reliability matrix table.
  - Code Confusion Frequency tags.
  - Passage Disagreements adjudication list with `"Resolve in Reader ↗"` deep links to `ReaderPage.tsx?pos={start}&q={quote}`.

## [Milestone 3] - 2026-11-10
### Added
- Saved Corpus Selections data model: PostgreSQL migration `0003_saved_corpus_selections.py` defining `saved_corpus_selections` and `saved_selection_members` tables.
- SQLAlchemy models `SavedCorpusSelection` and `SavedSelectionMember` in `backend/app/models.py`.
- Full REST CRUD router in `backend/app/routers/selections.py` supporting creation from dynamic search definitions or frozen article sets, snapshot member materialization, detail retrieval, deletion, and on-demand refresh.
- Activity logging for `create_selection`, `delete_selection`, and `refresh_selection`.
- Unit test suite `tests/test_selections.py` (3/3 passing) verifying explicit article selection, dynamic query materialization, snapshot refresh, and role-based permissions.
- Frontend dialog `SaveSelectionDialog.tsx` enabling researchers to save reusable subcorpora directly from search results into any project.
- Saved Selections management drawer in project Library (`LibraryTab.tsx`) with status badges (`⚡ Dynamic Query` vs `📌 Frozen Set`), article count tags, snapshot timestamps, and one-click refresh/delete actions.

## [Milestone 2] - 2026-11-10
### Added
- KWIC (Key Word in Context) concordance engine in `src/ui/data_service.py` (`get_concordance`) and `backend/app/routers/corpus.py` (`GET /api/articles/concordance`).
- Exact character offset tracking: each concordance hit returns `start_char` and `end_char` within the article text, strictly fulfilling the coordinate system (`document ID + [start_char, end_char]`).
- Three-mode regex compilation in `compile_query_regex` reflecting exact phrases, word-family wildcards, and trilingual thesaurus expansions.
- Frontend Concordance view toggle in `SearchPage.tsx` with a 3-column monospace grid (Left Context, Keyword, Right Context, Metadata, and Quick Actions).
- Deep linking support in both `ArticlePage.tsx` and project `ReaderPage.tsx` (`?pos={start_char}&q={keyword}`), automatically centering the viewport and rendering an amber match highlight.
- Seamless search-to-code workflow: Concordance rows feature a "Code 🏷️" button linking directly into the project reader with `code=1`, pre-populating the pending selection span and opening the `QuickCodeCard`.
- Search distribution aggregation engine in `src/ui/data_service.py` (`get_search_distribution`) and `GET /api/articles/distribution`.
- Collapsible "📊 Corpus Breakdown" drawer in `SearchPage.tsx` displaying matches across Languages, Discourse Types, Top Outlets, and Yearly timelines.
- Unit test suite in `tests/test_concordance.py` (4/4 passing) validating coordinate exactness against full text, search mode expansion, and faceted aggregation.

## [Milestone 1] - 2026-11-10
### Added
- Explicit search mode support: `exact`, `word_family`, and `concept` across `src/ui/data_service.py`, FastAPI backend (`/api/articles/search?mode=...`), and React frontend segmented buttons.
- Query interpretation metadata model `QueryInterpretation` returning `original_query`, `normalized_query`, `search_mode`, `effective_fts`, `expansion_terms` with language breakdown, and `expansion_category`.
- Expandable "Terms included in this search" drawer in `SearchPage.tsx` explaining how the search was expanded.
- Non-blocking corpus coverage warnings for uneven periods (Provinz News pre-2021, Salto pre-2025, Tageszeitung post-2025).
- Date range filtering (`min_date`, `max_date`) surfaced in search API and UI.
- Unit test suite `tests/test_search_modes.py` with 6 dedicated test cases covering quotes, prefix expansion, trilingual thesaurus, apostrophes, and Italian elisions.

### Fixed
- SQLite FTS5 syntax crash on Italian elisions with apostrophes (`dell'autonomia`) and German compounds with hyphens (`SVP-Parteitag`) by automatically wrapping apostrophe/hyphen-bearing tokens in double quotes in `build_fts_query`.
- Sub-200ms real search performance across all 113,823 articles in `didi_corpus.db`:
  - Optimized empty searches via `INDEXED BY idx_articles_date` and subquery pagination before metrics joins (from ~175ms down to 0.15ms).
  - Replaced unindexed `a.language NOT IN (...)` with indexed `a.language IN ('lld_badia', 'lld_fascia', 'lld_gherd')` in `count_unconfigured_matches` (from 1700ms down to 87ms).
  - Default API search mode set to `word_family` for fast sub-50ms token searches while allowing researchers to toggle full trilingual concept search.

## [Milestone 0] - 2026-11-10
### Added
- Beta documentation suite: `docs/beta/README.md`, `docs/beta/DECISIONS.md`, `docs/beta/CHANGELOG.md`, `docs/beta/BENCHMARKS.md`.
- Representative integration fixtures in `tests/fixtures/beta_search_articles.json` containing:
  - German compounds (`Autonomiestatut`, `SVP-Parteitag`).
  - Italian articles with apostrophes and elisions (`dell'autonomia`, `l'autonomia`, `un'altra`).
  - Ladin sample articles (`lld_gherd`).
  - Multi-year date coverage (2018–2025).
  - Both journalism and official press releases.
- Integration tests in `tests/test_beta_fixtures.py` verifying fixture integrity and baseline search constraints.
- Baseline query performance benchmark suite logged in `docs/beta/BENCHMARKS.md`.
