# Task 5: Import the Tageszeitung and add a word layer

You are working in the DIDI Platform repository. DIDI is built for German and Italian only (see `docs/PRD.md`, Section 2). Its German and Italian corpus has 858 articles, too few for quantitative work. Luca's KST project already annotated 79,504 *Neue Südtiroler Tageszeitung* articles with Stanza. This task imports them, and stores a **word layer**: one row per word, with its position in `full_text`. Later measures (Phase 3) are sums over these words, for any passage, code or set of articles.

## Read first
1. `AGENTS.md`
2. `docs/PRD.md`, Sections 2, 4 and 7
3. `src/harmonizers/tageszeitung.py`, `src/models/schema.py`, `src/ui/data_service.py`, and `backend/app/services/passages.py` (how the new app reads the corpus)

Check `git status` first. If the tree isn't clean, stop and ask Luca.

## The input
In `~/Data/KST/cluster/`, outside the repo. It is copyrighted. Never copy it into the repo, a test fixture or anything pushed to `origin`.
- `tageszeitung.tar.gz` holds `json/STYR_tageszeitung_articles_23_01_2026.json` (a list of `{url, tag, date, title, content, comments}`) and `conll/STYR_tageszeitung_articles_de_23_01_2026.conll` (3.2 GB).
- Each article in the CoNLL-U file starts with `<url = "...">`. Words carry `start_char` and `end_char` in the MISC column, plus `ner=`. Multi-word tokens (`5-6 zur`, then `5 zu`, `6 der`) appear as a range line followed by the words.
- **Positions count from the start of `title + "\n" + content`**. Checked on 25 sample articles: every token matched.
- DIDI's 131 Tageszeitung articles (May 2025, IDs like `taz_20250502_in-der-falle-4`) have `full_text == content` in 129 cases. One differs only in spacing, and one is unexplained.
- Extract into a new empty directory, stream the CoNLL-U file without loading it whole, and run any Python that reads it with `python -I`.

## Build
1. **Import script** (`scripts/import_kst_tageszeitung.py`): add the articles not yet in DIDI, using the existing harmonizer's ID, date and category rules (`tag` becomes the category). Keep the 131 existing articles and their IDs, and never change their `full_text`, because coded segments point into it. Running it again adds nothing new. Report the counts: added, already present, skipped and why.
2. **Word layer:** for every article whose `full_text` equals the annotated text minus `title + "\n"`, store each word's start and end in `full_text` (code points, exclusive end), form, lemma, part of speech, features and entity tag. Multi-word tokens: the words share the token's span; keep both words. Check `full_text[start:end] == form` for every token, except multi-word parts, and leave out any article that fails, with the reason in the report. Record the Stanza version, models and processors as the layer's source.
3. **Storage:** decide between a table in `didi_corpus.db` and a separate SQLite file, and say why. Measure the size first (estimate from a sample of 1,000 articles). The words of one article must load in under 200 ms, and so must the article list and search over the larger corpus. If a file is over 100 MB, ask Luca before syncing it to GitLab's `full-data` branch.
4. **Data service:** a function returning the words of one article, or of a span in it, with no SQL outside `src/ui/data_service.py` or the backend services.
5. **Report on the corpus:** articles per year and per category, and how many have no word layer and why. Don't drop any category. Provenance checks come later.
6. **Docs:** the corpus table in `docs/PRD.md`, the tracker in `AGENTS.md`, and a short note in `docs/` on the word layer's schema and where it comes from.

## Tests
On a small synthetic CoNLL-U and JSON fixture written for the tests, never on the real corpus:
- positions shifted by the title, multi-word tokens, emoji and NFD text, an article whose text doesn't match (skipped, with the reason), an article already in DIDI (left unchanged), and running the import twice.
- Existing tests still pass, and the app works with the larger corpus on Luca's real data.

## Do not
- Change the text of an existing article, or delete anything.
- Re-run Stanza, or import Salto. Salto's cluster text doesn't match DIDI's (see `docs/PRD.md`, Section 4).
- Build measures or reader layers. That's Phase 3.
- Touch Luca's dev database or servers (API 8010, frontend 5180).
- Commit or push until Luca asks.

## Done when
The import has run on the real files, the counts and checks are reported, the words of any Tageszeitung article load in under 200 ms, and search stays under 200 ms. Report what you built, the storage choice with its sizes, and any departures from this prompt.
