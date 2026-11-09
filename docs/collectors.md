# DIDI Open Media Collectors & Importer

<!-- doc-marker: didi-collectors-v1 -->

This document describes the architecture, operation, and maintenance of the open media collection pipeline (`src/collectors/`), harmonizer (`src/harmonizers/collected.py`), and corpus importer (`scripts/import_collected_to_corpus.py`).

---

## 1. Scope & Governance Principles

1. **Open Access Only:** No paywalled sites (e.g. *Dolomiten*, *Alto Adige*, *Corriere dell'Alto Adige*), no cookies, no authentication tokens, no login walls.
2. **Provenance & Exclusions:** Commercial wire agencies (ANSA, Adnkronos, APA, dpa, Italpress, Reuters) are detected and flagged. Only verified regional South Tyrolean production is ingested.
3. **Respectful Crawling:**
   - Honest user agent: `DIDI-research-crawler/0.1 (Eurac Research)`.
   - Politeness: strict adherence to `robots.txt`, 3.0s delay between requests + random jitter, exponential backoff on 429/503.
   - 10-error cap stops misbehaving runs.
4. **Data Preservation:** Raw HTML pages are saved gzipped with SHA-256 and fetch timestamp. Existing `full_text` in the corpus database is **never modified** or overwritten to preserve coded annotations and character offsets.

---

## 2. Configured Sources

Defined in `src/collectors/sources.yaml` and registered in `src/sources.py`:

| Source ID | Name | Language | Kind | Discovery Method |
| :--- | :--- | :---: | :--- | :--- |
| `provinz_press` / `provinz_news` | Provincia Autonoma di Bolzano / Landespresseamt | `it`, `de` | Institutional | Official Kontent.ai Delivery API |
| `salto_it` / `salto` | Salto.bz (Italian) | `it` | Independent magazine | XML sitemaps (`sitemap.xml?page=1..65`) |
| `rai_tgr_bolzano` / `rai_bolzano` | RAI TGR Bolzano | `it` | Public broadcaster | Rolling RSS feed (`/tgr/bolzano/rss/tutti`) |

---

## 3. Running Collections

The collector package provides a Typer CLI (`src/collectors/cli.py`):

```bash
# List configured open sources
.venv/bin/python -m src.collectors.cli list

# Probe source health, robots permissions, and test extraction
.venv/bin/python -m src.collectors.cli probe salto_it
.venv/bin/python -m src.collectors.cli probe rai_tgr_bolzano

# Dry run: discover candidate URLs without fetching
.venv/bin/python -m src.collectors.cli run --source salto_it --dry-run --since 2026-01-01

# Harvest a batch (capped at --max-pages or --limit)
.venv/bin/python -m src.collectors.cli run --source rai_tgr_bolzano
.venv/bin/python -m src.collectors.cli run --source salto_it --limit 500 --since 2026-01-01

# Harvest official provincial press releases (bilingual DE & IT)
.venv/bin/python -c "from src.collectors.provinz import harvest_provinz_press; harvest_provinz_press()"
```

Raw pages are saved to `data/raw/collected/<source_id>/pages/<sha256>.html.gz`.
Structured records are saved to `data/raw/collected/<source_id>/<year>-Q<quarter>/<run_id>.jsonl.gz`.

---

## 4. Importing into Corpus Database

To harmonize raw records and import them into `data/processed/didi_corpus.db`:

```bash
# Dry run: inspect candidate records, twin links, and counts
.venv/bin/python scripts/import_collected_to_corpus.py --dry-run

# Execute transactional import
.venv/bin/python scripts/import_collected_to_corpus.py
```

### Safety & Integrity Safeguards:
1. Creates a dated backup of `didi_corpus.db` in `data/backups/`.
2. Creates a temporary working copy `didi_corpus_copy.db`.
3. Skips any article whose normalized URL is already in the database (preserving exact text).
4. Links bilingual twin press releases (`twin_article_id` in metadata).
5. Populates FTS5 virtual table automatically via SQLite triggers.
6. Verifies row counts, ID uniqueness, and ensures FTS5 search executes in $< 200\text{ ms}$.
7. Atomically replaces `data/processed/didi_corpus.db` only when all checks pass.

