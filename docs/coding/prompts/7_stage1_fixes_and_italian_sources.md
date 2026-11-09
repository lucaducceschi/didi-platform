# Task 7: Fix the language scope, then collect open Italian sources

You are working in the DIDI Platform repository, a local React, FastAPI and PostgreSQL app for coding news articles, with a read-only SQLite corpus. DIDI is built for German and Italian only (`docs/PRD.md`, Section 2). The German corpus has about 80,000 articles, the Italian one 280 (Salto only). No comparison between the language communities can be made until Italian grows. On 2026-11-09 Luca decided to start collecting **open** Italian sources now.

This task has two parts. **Stop at each marked stop**, report, and wait for Luca's go. You never commit or push; Luca does.

## Read first
1. `AGENTS.md`, `docs/PRD.md` (Sections 2, 4, 6 and 7) and `docs/coding/prompts/6_measures_and_mixed_methods.md` (the rules for every stage apply here too)
2. `src/languages.py`, `src/ui/data_service.py`, `src/ui/app.py` and `tests/test_language_scope.py`
3. `src/harmonizers/salto.py`, `scripts/scrape_salto.py` and `scripts/scrape_provinz_press.py`
4. The scraper bundle in `~/Downloads/didi_scrapers/`. It was written elsewhere: read it before running anything, and copy in only what this prompt keeps.

Check `git status` first. The Stage 1 changes of Task 6 are expected to be uncommitted. If anything else is, stop and ask Luca.

## Rules
- **Exact text:** `full_text` of an existing article is never changed, because coded positions point into it. Positions are 0-based Unicode code points with an exclusive end.
- **Tests** run on small synthetic fixtures with no network and no copyrighted text.
- **Don't touch** Luca's dev servers (API 8010, frontend 5180) or the `didi` database. Use ports 8011 and 5181 and the `didi_e2e` and `didi_test` databases.
- **Databases stay local:** never add `*.db` files to git, and don't run `scripts/sync_remotes.sh`.
- **Secrets:** no cookies, tokens or logins anywhere in this task.

## Part A: fix Stage 1 of Task 6

1. **Streamlit keeps Ladin.** The PRD says the Streamlit demo stays as it is, Ladin included. `DataService.search_articles`, `search_article_ids` and `get_corpus_summary` now hide unconfigured languages by default, so `src/ui/app.py` hides Ladin too. Make the default "all languages" and pass `active_only=True` explicitly everywhere in `backend/`. Add a test that the Streamlit path still sees Ladin, and one that every backend corpus call passes the flag.
2. **One per-language definition.** Search still uses `TRILINGUAL_THESAURUS` in `data_service.py`, while the synonyms in `src/languages.py` are never read. Make search use the definitions in `src/languages.py`. Keep the Streamlit demo's results unchanged, including its Ladin expansions: either move the Ladin synonyms into the Ladin definitions, or keep a demo-only list and say so. Then remove the duplicate. Test that each German and Italian synonym still expands as before.
3. **Restore the deleted position tests.** Tests for NFD text, Windows line endings (CRLF), emoji, context cut by code point, and CSV export of a memo with a comma were deleted along with the Ladin fixture articles. Add German and Italian fixture articles with the same properties (decomposed accents, `\r\n`, emoji), and bring back every deleted assertion against them. Compare with `git diff HEAD -- tests/` so none is missed.
4. **Hidden counts for leads only.** `hidden_articles` and `hidden_passages` go to project leads and admins only, as Stage 1 required. Coders get 0 or no field.
5. **Rebuild instructions.** `docs/word_layer.md` says both databases can be rebuilt from scratch with the Tageszeitung import. They can't: Salto and Ladin come from `data/raw/` through `scripts/run_harmonization.py`. Write the full order (harmonization first, then the Tageszeitung import), and test the commands on a copy in a temporary directory, never on `data/processed/`.
6. Run pytest, vitest, the type check and the full Playwright suite.

**Stop:** report the fixes and the test results.

## Part B: collect open Italian sources

### Scope
Only these, all open access:

| Source | Language | How |
|---|---|---|
| Salto.bz Italian | it | Sitemaps; match the existing 280 articles by URL |
| RAI TGR Bolzano | it | Sitemaps or RSS, after a probe |
| Provincial press office | it and de | The existing `scripts/scrape_provinz_press.py` (content API, pairs German and Italian releases). Don't replace it with sitemap crawling. |

Leave out the paywalled dailies (Dolomiten, Alto Adige, Corriere dell'Alto Adige), the agencies (ANSA, Agenzia Opinione), il Dolomiti (a Trentino outlet), Südtirol News, Alto Adige TV, the Landtag, and the GitLab CI harvest. Don't copy the cookie and login code.

### B1: bring in the collector
1. Put the parts of the bundle that are kept in `src/collectors/`: the registry for the sources above, the polite HTTP client, discovery, extraction, dedup, the state store and the CLI. Add its dependencies to `requirements.txt` with pinned versions, and make trafilatura required, not optional, so the extracted text doesn't depend on what's installed.
2. Fix these bugs from the bundle:
   - **Keep raw pages.** Save each downloaded HTML page unchanged (gzipped), with its SHA-256 and fetch time, as `docs/PRD.md` Section 6 requires, so the text can be extracted again later.
   - **Record the extractor:** each record carries the extraction method and the versions of trafilatura and the collector.
   - **robots.txt:** a 401 or 403 means "fetch nothing" for that site, not "fetch everything". If robots.txt can't be reached, don't fetch.
   - **Retries:** retry only network and server errors. Short or undated articles don't change by retrying.
   - **URLs:** normalize them before deduplicating: strip tracking parameters (`utm_*`, `fbclid` and similar) and the fragment, and record the final URL after redirects and the canonical URL.
   - **Backfill:** support collecting a past period (`--since 2013-01-01`) as well as top-ups, and show progress.
   - **Wire bylines:** flag articles whose byline or dateline names ANSA, Adnkronos, APA, dpa, Italpress or Reuters (`wire_byline`). Flag them; don't drop them.
3. **Graceful crawling.** This is a demo, so be gentler than needed:
   - The user agent names the crawler honestly (`DIDI-research-crawler/0.1 (Eurac Research)`). It has no contact address; don't add one.
   - One request at a time per site, at least 3 seconds apart, with random extra delay of up to 2 seconds.
   - On 429 or 503, respect `Retry-After`, or wait at least 60 seconds, and double the delay for that site for the rest of the run.
   - Stop a source for the run after 10 errors in a row, and report it.
   - Cap each run per source (`--max-pages`, default 2,000), so a collection is spread over several runs instead of one long burst.
   - Fetch sitemaps and feeds once per run, and never fetch a page already saved.
   - Download only HTML pages: no images, PDFs or media.
4. **Output** goes to `data/raw/collected/<source>/`, which is gitignored. `sync_remotes.sh` mirrors `data/raw/` to GitLab's private `full-data` branch, so report the total size. If it's over 1 GB, say so before Luca syncs.
5. **Tests**, all offline with fixtures: each robots.txt case, URL normalization, raw page and checksum written, the extractor version recorded, wire bylines, backfill windows, and the bundle's existing tests.

### B2: probe and dry run (no full collection yet)
1. Probe each source. Report what robots.txt allows, which sitemaps or feeds exist, and one sample extraction per source (title, date, author, word count, the first 300 characters).
2. Dry run over the full period: for each source, the number of candidate URLs per year and the earliest date.
3. For the 280 existing Italian Salto articles, extract 20 again and compare their text with DIDI's `full_text`. Report how many are identical, and how the others differ.

**Stop:** report the probes, the counts per year, the comparison, and an estimate of time and disk space. Luca decides the period and whether to go ahead.

### B3: collect and import (after Luca's go)
1. Collect the agreed period with the graceful crawling rules from B1, over as many capped runs as needed. If interrupted, it continues where it stopped.
2. **Harmonizer** (`src/harmonizers/collected.py`): map records to DIDI articles.
   - IDs follow the existing pattern: `salto_it_<YYYYMMDD>_<slug>` for Salto, as in `src/harmonizers/salto.py`; for new sources, `<prefix>_<YYYYMMDD>_<slug>`, with the prefix in one place.
   - An article already in DIDI (matched by normalized URL) is left unchanged.
   - Press releases get `source_type: "official_press"` and keep the link between a German release and its Italian twin.
   - Add the new sources to the source labels, and keep source definitions in one place.
3. Import into a **copy** of `didi_corpus.db` first, check it, and replace the real file only when the checks pass. Keep the previous file as a dated backup in `data/backups/`.
4. **Report:** articles per source, language and year; how many were already present, flagged as wire, skipped and why; and the SimHash near-duplicates between press releases and outlets.
5. Update `docs/PRD.md` (the corpus table in Section 4; in Section 7, Phase 2 now includes open Italian sources), the tracker in `AGENTS.md`, and a short `docs/collectors.md` on how to run the collector and the importer.

The Salto word layer (Task 6, Stage 2) then runs on all Salto articles and the new Italian and press office articles together, so Stanza runs once.

## Do not
- Collect paywalled sites, use cookies or logins, or collect the agencies.
- Change the text of an existing article, or delete anything.
- Run more than one request at a time to the same site, or ignore robots.txt.
- Add a CI or scheduled harvest.
- Commit, push or run `sync_remotes.sh`.

## Done when
Part A: all suites pass and the fixes are reported. Part B: the agreed period is collected and imported, and the counts are reported. The app works with the new articles on Luca's real data, and search stays under 200 ms. Report what you built, how you checked it, and any departures from this prompt.
