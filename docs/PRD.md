# PRD: DIDI Platform

**Project:** *DIDI — Gruppi diversi, prospettive diverse? Come l'inquadramento mediatico influenza le percezioni delle comunità di maggioranza e di minoranza*
**Affiliation:** Eurac Research (Center for Autonomy Experience, Institute for Minority Rights, Institute for Applied Linguistics) and University of Innsbruck
**Lead:** Dr. Luca Ducceschi
**Version:** 2.0, 2026-11-07. It replaces the 1-week demo PRD (version 1.0), which is in git history.

## 1. Purpose

DIDI studies how South Tyrolean media frame autonomy, minority rights and political events for different language communities, and how that framing shapes perceptions. The platform supports this with mixed methods: researchers read and code texts closely, measure framing across many texts, and move between the two.

The platform's value is the **link** between the two halves:
- Every number on screen leads back to the texts behind it.
- Coded passages can be measured and compared like any other subset of the corpus.
- Measures help choose what to read and code.

It replaces MAXQDA for the project's coding (see [`coding/PRD.md`](coding/PRD.md)), but it is meant to be more than a coding tool.

## 2. Scope decisions

**2026-11-07: German and Italian only, for now.** The platform is built for German (`de`) and Italian (`it`). Ladin is deferred until Luca's new Ladin NLP pipeline is ready (see *Ladin: returning later* in Section 7).
- Ladin articles stay in the corpus database and in `data/raw/`. Nothing is deleted.
- The new app shows only the languages it is configured for (Phase 1).
- New features are designed and tested on German and Italian. No Ladin-specific work until the Ladin phase starts.
- **Languages must stay pluggable.** Everything language-specific sits behind one per-language definition, so adding Ladin later means adding a language, not changing the app. This covers labels, the search synonym list, dictionaries, tokenization and any models.
- The Streamlit demo is left as it is, Ladin included, until its views are ported.

**Earlier decisions that still stand:**
- React and Python app with PostgreSQL, developed locally. Hosting undecided (possibly Azure or Foundry), so no cloud-specific code.
- Up to 10 researchers, each in their own projects with their own codebooks.
- Exact text: `full_text` is never modified, because coded positions refer to it.
- Copyright: full text, databases, raw data, dictionary assets and exports never reach the public `origin` remote.

## 3. Users

| User | Needs |
|---|---|
| Qualitative researcher | Find relevant articles, code passages, compare coded material across communities, export quotes with citations |
| Computational or linguistic researcher | Transparent measures, the words behind each score, validation against human coding, exportable data |
| Principal investigator | Clear comparisons and trends for reports and presentations, traceable to texts |

## 4. Where things stand

### Corpus (German and Italian)

| Source | Language | Articles | Period | Words |
|---|---|---:|---|---:|
| Salto.bz | German | 447 | 2017-10 to 2025-05, mostly 2024–2025 | 192,106 |
| Die Neue Südtiroler Tageszeitung | German | 79,303 | 2015-01 to 2025-08 | 25,113,908 |
| Salto.bz | Italian | 280 | 2021-03 to 2025-05 | 161,532 |
| **Total** | | **80,030** | | **25,467,546** |

The full corpus database holds 91,392 articles and 27,629,163 words (including the 11,362 deferred Ladin articles). Stanza token-level Word Layer annotations for 79,293 Tageszeitung articles (30,275,813 tokens) are stored in `data/processed/didi_words.db`.

### Stanza-annotated articles from the KST project (checked 2026-11-07)

Luca's KST project annotated two German sources with Stanza (`tokenize,lemma,pos,ner,depparse`) on the Eurac HPC cluster. Copies are on Luca's Mac in `~/Data/KST/cluster/`, and they never go into a git repository.

| Source | Articles | Period | Matches DIDI's text? |
|---|---:|---|---|
| Die Neue Südtiroler Tageszeitung (DE) | 79,504 | 2015–2025 | Yes: 129 of DIDI's 131 identical, 1 differs in spacing only |
| Salto.bz (DE) | 33,273 | 2013–2026 | No: none of 393 overlapping articles match; the cluster text lacks the lead paragraph and has line breaks in mid-sentence |

- Each word has a lemma, parts of speech, morphological features, a dependency and a named-entity tag, and character positions that count from the start of `title + "\n" + text`.
- There is no Italian. DIDI's 280 Italian Salto articles have no Stanza annotations yet.
- Some Tageszeitung text has words glued together (`enttäuschtauf`), probably from the original scrape. DIDI's 131 articles have the same flaw.

Known gaps:
- **Official press:** a scraper exists (`scripts/scrape_provinz_press.py`), but only 10 releases were fetched, and none are in the database.
- **Provenance checks** (Section 6): the fields exist in `src/models/schema.py`, but nothing computes them. Every article defaults to a provenance score of 1.0, and none of the 858 stores one.
- **Source manifests:** `config/sources/` was planned but never built. Each scraper is its own script.

### Software

| Part | State |
|---|---|
| Annotation workbench (React, FastAPI, PostgreSQL) | Built: accounts, projects, codebooks, library, reader, coding, presence, passages across articles, article removal, CSV export. Used by Luca; no researcher trial yet. |
| Streamlit demo | Explorer, framing radar, timelines, focus events with Dunning G² keyness and a moral divergence index, article inspector, CSV exports |
| Measures (`src/nlp/`) | Computed in advance per article: sentiment and NRC emotions (Plutchik), Moral Foundations (MFD 2.0, lemmatized with Stanza), lexical diversity |
| Search | SQLite FTS5 keyword search with a synonym list; sentence-vector search in Streamlit only |
| MAXQDA exchange | QDPX export of articles and metadata; never tested in MAXQDA |

## 5. Principles

1. **Evidence first:** every chart, count or score can be opened to show the passages or words behind it.
2. **Codes and measures meet:** any measure can be computed for coded passages, a code or a project, not only for the whole corpus.
3. **Validate before comparing:** a dictionary measure isn't used to compare communities until it has been checked against human judgement in that language.
4. **Languages are configuration:** see Section 2.
5. **Open data:** everything stored can be exported, and the schema is documented.
6. **Runs offline:** no third-party calls from the browser. Any optional model service sits behind one small HTTP client, and the app works without it.

## 6. Corpus and provenance for German and Italian

German and Italian text must be **South Tyrolean regional production**, not national wire copy republished locally.

**Sources, in order:**
1. **Journalism, open access:** *Salto.bz* (DE, IT), *Die Neue Südtiroler Tageszeitung* (DE), *RaiNews TGR Bolzano* Italian desk, *Barfuss* (DE), *ff* (DE), *QuiMedia / QuiBolzano* (IT).
2. **Official press:** *Landespresseamt / Ufficio Stampa della Provincia* (`news.provinz.bz.it`, `news.provincia.bz.it`). Releases appear in German and Italian on the same day, which makes them a parallel anchor for comparing the two languages. They are tagged `source_type: "official_press"`, kept apart from journalism.
3. **Paywalled, needing an agreement:** *Dolomiten* (`stol.it`) and *Alto Adige* (`altoadige.it`). These are the main daily papers of each community, so without them the comparison leans on smaller outlets. Access is a question for the project, not for engineering.
4. **Later:** municipal gazettes (PDF/OCR noise), and broadcasts transcribed with Whisper.

**Provenance checks** before an article enters the corpus:
- **Wire agencies:** flag or reject ANSA, Adnkronos, APA, dpa, Italpress and Reuters bylines.
- **Sections:** collect only regional sections, not national, world or sport.
- **Local score:** density of South Tyrolean place names and political terms, stored as `local_provenance_score`.

Raw responses are kept unchanged with a checksum and timestamp, and re-running a collector only adds new material.

## 7. Roadmap

Each phase gets its own task prompt in `docs/coding/prompts/` before work starts, as for Tasks 0–4. Order and estimates are proposals.

| Phase | What | Why now | Depends on |
|---|---|---|---|
| **1. Language scope** | One per-language definition; the app, search, passages and exports offer only configured languages (German and Italian). Ladin articles already in projects are hidden, not deleted. | Small, and it settles how Ladin returns later | Nothing |
| **2. Tageszeitung and the word layer** | Import the 79,504 annotated Tageszeitung articles (Task 5), and store each word's position in `full_text`, lemma, part of speech, features and entity tag. Run Stanza on DIDI's 727 Salto articles, German and Italian, so they get the same layer. The other ~32,800 German Salto articles on the cluster wait for a decision on their text quality. No scraping. | Measures for any passage, code or article set are sums over words, and the reader can show which words produced a score | Nothing |
| **3. Measures in the app, linked to codes** | Bring sentiment, emotion and moral measures into the new app, computed from the word layer: profiles for a code's passages against the rest of the project, code frequency by language, source and period, keyness for a code, and measure words as an optional layer in the reader. | The core of mixed methods; reuses existing measures | Phases 1 and 2 |
| **4. Dictionary validation** | Check emotion and moral measures against human coding in German and Italian, using coded passages, and report agreement per language. If the official press is added later, its parallel German and Italian releases help check that the two languages are scored alike. | Comparisons between communities are only credible after this | Phases 2 and 3, and coded data |
| **5. Sampling and focus events** | Draw random or balanced samples into a project; flag periods of unusual coverage and open them for coding. | Lets coded findings generalize | Phase 2 |
| **6. Coder agreement** | Double-coding, blind mode, Krippendorff's alpha or another measure, adjudication. | Only once it's clear how coders will work | Researchers' working practice |
| **7. Assisted coding** | Suggest passages similar to a code's examples, and estimate code frequencies across the corpus with a stated error. Needs a GPU or hosted model. | Scales coding to the whole corpus | Phases 3 and 4, enough coded data, hosting |
| **8. Hosting** | Where it runs, logins, backups, and whether full text may be served to 10 users or sent to a model | Needed before researchers use it from their own computers | A decision by Luca and Eurac |

**Later, not yet planned:** more corpora (the remaining Salto articles, the official press, another Italian source, paywalled dailies), provenance checks for them, named entities (people, parties, places), topic models across languages, QDPX export of coded segments and import, audio, porting the remaining Streamlit views and retiring Streamlit.

### Ladin: returning later

Ladin comes back as a new language once these hold:
- Luca's Ladin pipeline (tokenizer, lemmatizer, tagger) works for the varieties in scope.
- A Ladin speaker has reviewed the variety labels (Gherdëina, Badiot, Fascian).
- Ladin dictionaries for emotion and moral measures are rebuilt with the new pipeline and validated as in Phase 4.

Adding it should then mean adding a language definition (Phase 1), re-running measures, and checking provenance for Ladin sources. Existing Ladin articles, scrapers and the relabelling script (`scripts/relabel_ladin.py`) are kept for that moment.

## 8. Open questions for the DIDI team (later)

Not needed for the proof of concept. They matter once the platform goes beyond it.

| Question | Why it matters |
|---|---|
| Which comparisons matter most: German against Italian, outlets against each other, journalism against official press, change over time? | Decides what Phase 3 shows first |
| Which period should the corpus cover? | Decides how far back later collection goes |
| Can the project get access to *Dolomiten* and *Alto Adige*? | Without them, each community's main daily paper is missing |
| Will coders code the same articles independently? | Decides when Phase 6 is needed |
| Which agreement measure do reviewers expect? | Krippendorff's alpha is the default |

## 9. Requirements throughout

- **Speed:** searches and list queries take under 200 ms against the real corpus.
- **Tests:** API tests against PostgreSQL, unit tests, and browser tests with no third-party requests. Tests run on a small synthetic fixture, without the copyrighted corpus.
- **Remotes:** code and copyright-safe metadata go to GitHub (`origin`); raw data and dictionary assets go only to the private GitLab (`gitlab`), using `scripts/sync_remotes.sh`. The SQLite databases stay on Luca's Mac (decided 2026-11-09, review by 2027-01-09; see `AGENTS.md`).
- **Separation:** database access in services, UI in components; the Streamlit demo keeps working until it is retired.
