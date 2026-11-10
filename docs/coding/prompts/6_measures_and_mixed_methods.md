# Task 6: From the word layer to measures linked to codes

You are working in the DIDI Platform repository, a local React, FastAPI and PostgreSQL app for coding news articles, with a read-only SQLite corpus. DIDI is built for German and Italian only (see `docs/PRD.md`, Section 2). This prompt runs six stages in order. **Stop after each stage**, report, and wait for Luca's go before starting the next. Luca commits between stages; you never commit or push.

## Where things stand (2026-11-09)
- **The Tageszeitung import (Task 5) has run and is committed.** The corpus has 79,303 Tageszeitung articles, 447 German Salto and 280 Italian Salto (`data/processed/didi_corpus.db`, 432 MB). The word layer is in `data/processed/didi_words.db` (6.3 GB, 30.3M words, 79,293 articles; schema in `docs/word_layer.md`). Code: `scripts/import_kst_tageszeitung.py`, `src/importers/`, `src/storage/word_layer.py`, `backend/app/services/words.py`, `tests/test_tageszeitung_word_layer.py` (10 tests, passing).
- **Salto has no word layer.** Its cluster annotations don't match DIDI's text (`docs/PRD.md`, Section 4).
- **Italian is tiny:** 280 articles from one source. German is about 80,000. Any comparison between the two languages measures this imbalance, not framing, unless counts are shown and small groups are flagged.
- **Existing measures** are in `src/nlp/` (`emotions.py` NRC/Plutchik, `morality.py` MFD 2.0 on Stanza lemmas, `lexical.py`, `framing_divergence.py` with Dunning G²), and the dictionaries are in `assets/`. They score whole articles in advance (`article_nlp_metrics`).

## Read first
1. `AGENTS.md`
2. `docs/PRD.md` and `docs/coding/PRD.md`
3. `docs/word_layer.md`, `src/storage/word_layer.py` and `backend/app/services/passages.py`
4. `docs/coding/prompts/4_retrieval.md` and `5_tageszeitung_word_layer.md`, for the conventions

## Rules for every stage
- **Exact text:** positions are 0-based Unicode code points with an exclusive end, and `full_text` is never modified.
- **Evidence first:** every number the app shows opens the passages or words behind it, and shows its count and denominator. A measure with fewer than 30 passages or 1,000 words is marked as a small sample.
- **Languages are configuration:** anything language-specific (dictionaries, pronoun lists, quotation marks, which measures exist) lives in the per-language definition from Stage 1. A measure that doesn't exist for a language shows "not available for Italian", never 0.
- **Unvalidated measures say so.** Konjunktiv I and direct quotes (Stages 3 and 5) carry an "unvalidated" label until Luca's hand check is done. Dictionary measures carry it until Phase 4.
- **Tests** run on small synthetic fixtures, never on the copyrighted corpus. Browser tests make no third-party requests.
- **Speed:** search and list queries stay under 200 ms on the real corpus. Analysis views stay under 1 s for a code with 10,000 passages; if they can't, precompute and explain how.
- **Don't touch** Luca's dev servers (API 8010, frontend 5180) or the `didi` dev database. Use ports 8011 and 5181 and the `didi_e2e` and `didi_test` databases.
- **The databases stay local** (decided 2026-11-09, review by 2027-01-09). Never add them to git or copy them anywhere. Don't run `scripts/sync_remotes.sh`; Luca syncs.
- **Data from outside the repo** (`~/Data/KST/cluster/`) never enters the repo. Read it with `python -I`.

## Stage 0: close Task 5 and update the PRD
1. Run the full test suites (pytest, vitest, Playwright) and report the results.
2. Check 200 random articles from the word layer: for every word, `full_text[start:end] == form`, except parts of multi-word tokens. Explain the 10 articles that have no word layer.
3. Record the Stanza version and models if anything on the Mac shows them (the files in `~/Data/KST/cluster/`, the logs in the archives). If nothing does, write "unknown" in `word_layer_metadata` and the docs, and ask Luca to check `stanza_process.ipynb` on the cluster.
4. **Rebuilding:** the databases stay local, with no backup in any remote, until Luca reviews this by 2027-01-09. Write the exact steps and commands to rebuild both from `~/Data/KST/cluster/` into `docs/word_layer.md`, with how long the Tageszeitung import takes. Don't run a full rebuild.
5. **Update `docs/PRD.md` Section 7** to this plan:
   - Phase 2 done for Tageszeitung; the Salto word layer is Stage 2.
   - Phase 3 includes words behind every score, ingroup pronouns and Konjunktiv I.
   - New phases after Phase 3: the comparison grid, then direct quotes, with a validation step.
   - Phase 4 adds a dictionary coverage check per language.
   - Phase 6 names Krippendorff's unitized alpha, checked against published worked examples.
   - Phase 7 starts with TF-IDF suggestions, and records whether an accepted suggestion counts as human coding.
   - Under "later": networks of people and issues (called co-occurrence, after merging name variants), and which language community leads an issue (only once there's a comparable Italian corpus).
   - Update the corpus table and the tracker in `AGENTS.md`.

## Stage 1: language scope (PRD Phase 1)
1. **One per-language definition** for `de` and `it`: label, search synonyms, dictionaries, pronoun lists, quotation marks, which measures exist, and the word layer's source. Adding Ladin later must mean adding a definition, not changing code.
2. The new app (search, add articles, library, passages, exports) offers only configured languages. Ladin articles already in projects are hidden, not deleted, and a lead can see how many are hidden.
3. Remove the Ladin caution from the Passages tab, or keep it behind the Ladin definition.
4. **Tests:** an unconfigured language is hidden everywhere, and its articles and segments still exist in the database.

## Stage 2: word layer for DIDI's Salto articles
1. Run Stanza locally on the 727 Salto articles (447 German, 280 Italian), on DIDI's `full_text` exactly as stored. Pass `full_text` alone; don't prepend the title, so positions need no shift.
2. Use the processors from the Tageszeitung run. Record the Stanza version and models per language. If the German model differs from the cluster's, say so in the docs, because measures may then differ slightly between sources.
3. Run the same check (`full_text[start:end] == form`) and the same storage, through the same importer code where possible.
4. Downloading the models is allowed in this script. The app itself stays offline.

## Stage 3: measures linked to codes (PRD Phase 3)
1. **Measures over words:** a function that scores any set of word spans: an article, a coded passage, all passages of a code, or a project. Re-use the dictionaries in `assets/` through the language definition, and match on lemmas as `morality.py` does. Measures: Moral Foundations (MFD 2.0, virtue and vice per foundation), NRC emotions (Plutchik), and sentiment, each as hits per 1,000 words with the raw counts.
2. **Ingroup pronouns:** first person plural (German *wir, uns, unser*; Italian *noi, ci, nostro*), from `upos` and `feats` (`Person=1|Number=Plur`). Show them as a rate, and note that inside quotes they are the speaker's, not the newspaper's (Stage 5 separates them).
3. **Konjunktiv I (German only):** finite verbs with `Mood=Sub`, separated from Konjunktiv II by tense and form. Hand-check 100 hits yourself and report the error rate. Keep it labelled "unvalidated" until Luca has reviewed your check. Not available for Italian.
4. **Analysis tab** in a project: pick a code, and compare its passages with the rest of the project and with the project's articles. Show each measure with counts, plus distinctive lemmas (Dunning G², minimum counts stated) for the code against the rest. Breakdowns by language, source and year show their counts, and flag small groups. Every measure and breakdown can be split by source type (`journalism` vs. `official_press`), and German against Italian comparisons say what share of each side is official press.
5. **Words behind every score:** clicking a measure or a lemma lists the passages that contributed, with the words highlighted, and opens the reader there. The reader gets an optional layer showing dictionary words in the selected measure's colour. It is off by default, so it doesn't hide coding highlights.
6. **Export:** CSV of the measures per passage and per code, with the dictionary and the word layer's source in the header.
7. **Tests:** sums over spans (passage boundaries cutting through a word, multi-word tokens, overlapping passages counted once per passage), language rules, permissions, the CSV, and a browser test from a score to the highlighted words.

## Stage 4: comparison grid
1. A project view with rows by source, language or year (the user chooses), and the project's codes as columns.
2. Each cell shows the number of passages, articles and coders, one chosen measure with its counts, the top distinctive lemmas, and up to three example quotes.
3. Clicking a cell opens the Passages tab with the matching filters.
4. CSV export of the grid. No written summaries, and no model service.
5. **Tests:** counts match the Passages tab for the same filters, empty cells are shown as empty, and small cells are flagged.

## Stage 5: direct quotes
1. Detect direct quotes from quotation marks in the language definition: German „…“, »…«, "…" and ‚…‘; Italian «…» and "…". Handle nesting, and quotes that run across paragraphs. Don't count one- or two-word quotes with no verb (scare quotes, titles) as speech.
2. Store quote spans per article alongside the word layer, with the detection rule's version.
3. Every Stage 3 measure can be split into **inside quotes** and **outside quotes**. Indirect speech and naming the speaker are out of scope.
4. **Validation:** export 200 random candidate quotes and 50 random paragraphs without detected quotes as a CSV for Luca to label. When the labels come back, report precision and recall per source. Until then the split is labelled "unvalidated".
5. **Tests:** each quotation mark style, nesting, unbalanced marks, quotes in headlines, and a measure split that sums back to the total.

## Do not
- Compare German with Italian without showing counts, or describe a difference as a framing difference before Phase 4.
- Add suggestions from a model, agreement statistics, people networks or agenda timing. They are later phases.
- Change the text of any article, delete Ladin data, or re-run Stanza on the Tageszeitung.
- Commit, push or run `sync_remotes.sh`.

## Done when (for each stage)
All tests pass, the feature works on Luca's real data in both themes and at phone width, and you have measured the speed on the real corpus. Report what you built, how you checked it, the numbers, and any departures from this prompt. Then stop and wait for Luca.
