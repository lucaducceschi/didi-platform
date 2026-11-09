# Task 8: Correct Task 7, collect Italian journalism, and separate official press

You are working in the DIDI Platform repository, a local React, FastAPI and PostgreSQL app for coding news articles, with a read-only SQLite corpus. Task 7 added 22,371 articles. A review on 2026-11-09 found that:
- **Italian is almost all press releases:** 11,355 of 11,704 Italian articles come from the provincial press office. Only about 350 are journalism (Salto 328, RAI 21), and the new Salto and RAI articles are all from 2026. A comparison of "Italian" against German would mostly compare press releases with newspapers.
- Two claims in `docs/PRD.md` are false, and the press office collector cuts two corners.

This task has three parts. **Stop at each marked stop**, report, and wait for Luca's go. Do every part, including the stops, even if a later message asks you to collect everything. You never commit or push; Luca does.

## Read first
1. `AGENTS.md`, `docs/PRD.md` (Sections 4, 6 and 7) and `docs/collectors.md`
2. `docs/coding/prompts/7_stage1_fixes_and_italian_sources.md`: its rules and graceful crawling rules apply here unchanged
3. `src/collectors/` (especially `provinz.py`, `discovery.py` and `pipeline.py`), `src/sources.py`, `src/harmonizers/collected.py` and `scripts/import_collected_to_corpus.py`

Check `git status` first. If Task 7's work is uncommitted, stop and ask Luca to commit it.

## Rules
- **Existing articles:** never change the `full_text`, title, language or date of an article already in the corpus. Coded positions point into `full_text`.
- **Imports** go into a copy of `didi_corpus.db` first, with a dated backup in `data/backups/`, as in Task 7. After every import, check that every article from the backup is still present and unchanged, and report the result.
- **Tests** run on small synthetic fixtures with no network and no copyrighted text.
- **Don't touch** Luca's dev servers (API 8010, frontend 5180) or the `didi` database. Use ports 8011 and 5181 and the `didi_e2e` and `didi_test` databases.
- **Databases stay local:** never add `*.db` files to git, and don't run `scripts/sync_remotes.sh`.
- **Run every suite** before each stop: pytest, vitest, the type check and the full Playwright suite (`npm --prefix frontend run e2e`).

## Part 1: correct Task 7
1. **Docs** (`docs/PRD.md`, `AGENTS.md`, `docs/collectors.md`):
   - **Provenance:** remove the claim that every article stores `local_provenance_score`. Say instead that wire bylines are detected for collected articles, the press office collector sets 1.0 without computing it, and the local score (Section 6) is still not computed anywhere.
   - **Official press label:** say where `official_press` actually lives: in `src/sources.py`, per source, not in the corpus database.
   - **Italian:** state the split between journalism and press releases in the corpus table, and that Italian journalism is about 350 articles.
2. **Press office collector** (`src/collectors/provinz.py`):
   - Save each API response unchanged (gzipped) with its SHA-256 and fetch time, as other sources save raw pages, and record the checksum per article instead of `null`.
   - A failed request is retried with backoff (3 attempts). If it still fails, the run stops with an error and a non-zero exit, says which language and offset it reached, and is not recorded as complete. Today it quietly stops that language and reports success.
   - Use the same user agent as the other collectors.
   - Tests: raw response saved with checksum; a failed page retried, then the run reported as failed; a later run continuing from where it stopped.

**Stop:** report the changes and the test results.

## Part 2: collect Italian journalism

### 2a: find out why only 2026 came through (no collection yet)
1. Dry run `salto_it` and `rai_tgr_bolzano` over the full period (`--since 2013-01-01`). For each, report the candidate URLs per year, the earliest date, and which sitemaps or feeds they came from.
2. Explain why Task 7 got only 2026 articles. For example: sitemaps skipped by their `lastmod`, a default window, the 2,000-page cap, RSS covering only recent items, or a discovery bug. Fix any bug you find, with a test.
3. **RAI:** if only the live RSS feed is available, say so. Look for an archive the site allows (archive sitemaps, or listing pages permitted by robots.txt). If there is none, RAI stays a small, current-only source; don't work around robots.txt.
4. **Existing Salto Italian:** re-extract 20 of the 280 articles already in DIDI and compare them with DIDI's `full_text`: identical, differing only in spacing, or different (with an example). The existing text is kept in every case, but this shows whether new and old Salto articles are comparable.
5. Estimate the pages, time and disk space per source. At 3 to 5 seconds per page, 10,000 pages take about 11 hours.

**Stop:** report all of the above. Luca chooses the period.

### 2b: collect and import (after Luca's go)
1. Collect the agreed period in capped runs (2,000 pages per run per source), with the graceful crawling rules. If interrupted, it continues where it stopped.
2. Import with the existing importer, into a copy first. Articles already in DIDI are matched by normalized URL and left unchanged.
3. **Report:** new articles per source and year, how many were already present, flagged as wire, too short or undated, and the check that all existing articles are unchanged. Update the corpus table in `docs/PRD.md`.

**Stop:** report the counts.

## Part 3: separate journalism from official press
1. **One definition:** `source_type` per source stays in `src/sources.py` (`journalism`, `official_press`). The backend gets it from there, so a new source only needs a registry entry.
2. **Filter everywhere** a researcher picks articles or reads results: corpus search, **Add articles**, the library and passages. Show a filter "Type: Journalism / Official press" with counts, like the language filter, and keep it in the URL. By default both are shown, and each result card shows a small badge for official press.
3. **Exports:** the annotation and passage CSVs get a `source_type` column.
4. **Twins:** in the reader, a press release with a twin in the other language shows a link to it.
5. **Prompt 6, Stage 3:** add a line to `docs/coding/prompts/6_measures_and_mixed_methods.md` saying that every measure and breakdown can be split by source type, and that German against Italian comparisons say what share of each side is official press.
6. **Tests:** the filter and counts in each place, the URL state, the CSV column, the twin link, and a browser test filtering a project's library to journalism only.

**Stop:** report what you built and the test results. The Stanza run (Task 6, Stage 2) comes after this task, on all Salto, press office and RAI articles together.

## Do not
- Collect paywalled sites, use cookies or logins, collect agencies, or ignore robots.txt.
- Run more than one request at a time to the same site.
- Skip a stop, or change existing articles.
- Commit, push or run `sync_remotes.sh`.

## Done when
All three parts are done, each stop reported, every suite passes, and the app works on Luca's real data. Report what you built, how you checked it, and any departures from this prompt.
