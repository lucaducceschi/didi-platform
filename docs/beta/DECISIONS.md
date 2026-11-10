# DIDI Beta Architecture Decision Records (ADRs)

## ADR-001: Retention of SQLite FTS5 Search (No CQP/CWB for Beta)
- **Status:** Accepted (2026-11-10)
- **Context:** Target users are primarily political scientists and minority-rights researchers, not corpus linguists. Introducing Corpus Workbench (CWB) or CQP introduces compilation, synchronization, and dual-index maintenance complexity.
- **Decision:** Retain SQLite FTS5 over `articles_fts` as the primary search engine. Optimize tokenization, apostrophe handling, prefix indexing, and expose three explicit modes (`exact`, `word_family`, `concept`). Keep an extension path for structured lemma/UPOS queries via `didi_words.db`.
- **Consequences:** Search remains $<100\text{ ms}$ with zero added binary dependencies. Complex syntactic dependency queries are deferred.

## ADR-002: Three Explicit Search Modes
- **Status:** Accepted (2026-11-10)
- **Context:** Automated thesaurus expansion can confound exact research hypotheses by invisibly conflating German terms with Italian translations or loose synonyms.
- **Decision:** Expose three explicit modes in backend schemas and frontend UI:
  1. `exact`: Verbatim term or quoted phrase matching only. No prefix wildcarding, no thesaurus expansion.
  2. `word_family`: Transparent morphological stem/prefix expansion (`term*`) within the target language only. No cross-language translations.
  3. `concept`: Multilingual thesaurus expansion across German, Italian, and Ladin. The UI must render an expandable drawer showing every term included.
- **Consequences:** Researchers have full transparency into which lexical items contributed to their findings.

## ADR-003: Saved Corpus Selections as First-Class Objects
- **Status:** Accepted (2026-11-10)
- **Context:** Researchers need to build subsets (e.g. "German journalistic articles on autonomy 2018–2023") and reuse them in comparison grids, keyness, and qualitative projects.
- **Decision:** Saved corpus selections will be stored in PostgreSQL with both:
  1. A dynamic query definition (filters, query, mode) that can be refreshed.
  2. A materialized snapshot (explicit normalized table of article IDs) guaranteeing strict replicability.
- **Consequences:** Analytical results can be tied to a frozen snapshot for publication reproducibility.

## ADR-004: Strict Separation of Qualitative Codes, Topics, and Lexicons
- **Status:** Accepted (2026-11-10)
- **Context:** In CAQDAS and computational linguistics, researchers must not confuse interpretative qualitative codes with unsupervised statistical topic clusters or dictionary matches.
- **Decision:** 
  - Qualitative Code = Researcher hermeneutic interpretation (`annotations` table).
  - Lexical Measure = Dictionary operationalization (`mfd_density`, `sentiment`).
  - Search Concept = Retrieval construct (`articles_fts MATCH`).
  - Topic = Machine-derived latent cluster (unsupervised BERTopic).
  These layers may be cross-tabulated in comparison grids, but one will never silently overwrite or stand in for another.

## ADR-005: Data Sovereignty and Local Processing
- **Status:** Accepted (2026-11-10)
- **Context:** Copyrighted regional newspapers (*Die Neue Südtiroler Tageszeitung*, *Salto*, *Dolomiten*, *Alto Adige*) and restricted research interviews cannot be sent to commercial third-party AI APIs (OpenAI, Anthropic).
- **Decision:** All beta analytics, search, NLP metrics, and future AI assistance run 100% locally or on institutionally approved Eurac/UIBK infrastructure with zero data retention.
- **Consequences:** Prevents vendor lock-in, licensing violations, and copyright breach.

## ADR-006: Evidence Traceability Coordinate System
- **Status:** Accepted (2026-11-10)
- **Context:** Aggregated charts (radar plots, timeseries, heatmaps) can mask methodological artifacts if disconnected from source passages.
- **Decision:** Every cell in a comparison table or point on a chart must support click-to-evidence drill-down to the exact articles and character offsets.

