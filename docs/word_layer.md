# Word Layer Architecture & Specification

## 1. Overview
The **Word Layer** provides token-level linguistic annotations for articles in the DIDI Platform. It links every token directly to its character offsets in `full_text` (`[start_char:end_char]`), preserving the exact surface form, canonical lemma, universal and language-specific parts of speech, morphological features, and named entity recognition (NER) tags.

All subsequent quantitative framing metrics (Moral Foundations densities, NRC discrete emotions, keyness, and sentiment) are calculated directly as sums and aggregations over this word layer for any text passage, coded segment, or arbitrary article subset.

---

## 2. Storage Separation & Architecture Decision
The word layer is stored in a dedicated SQLite database:
- **Corpus & Search Database:** [`data/processed/didi_corpus.db`](data/processed/didi_corpus.db) (~412 MB)
  - Contains `articles` metadata and full-text search index (`articles_fts` via FTS5).
  - Keeps query latency low (<60 ms for corpus-wide full text queries).
- **Word Layer Database:** [`data/processed/didi_words.db`](data/processed/didi_words.db) (~5.9 GB)
  - Contains `article_words` (30,275,813 token rows for 79,293 articles) and `word_layer_metadata`.
  - Keeping this separate prevents bloat of the core corpus database, ensures rapid maintenance/backup cycles, and allows memory-mapped read I/O (`PRAGMA mmap_size = 268435456`) yielding sub-2ms word lookups per article.

---

## 3. Database Schema

### Table: `article_words`
```sql
CREATE TABLE article_words (
    article_id TEXT NOT NULL,
    token_idx INTEGER NOT NULL,
    start_char INTEGER NOT NULL,
    end_char INTEGER NOT NULL,
    form TEXT NOT NULL,
    lemma TEXT NOT NULL,
    upos TEXT NOT NULL,
    xpos TEXT,
    feats TEXT,
    ner TEXT,
    PRIMARY KEY (article_id, token_idx)
);

CREATE INDEX idx_article_words_start ON article_words (article_id, start_char);
```

| Column | Type | Description |
| :--- | :--- | :--- |
| `article_id` | TEXT | Canonical article identifier (`taz_YYYYMMDD_<slug>`) |
| `token_idx` | INTEGER | 0-indexed sequential position within the article content |
| `start_char` | INTEGER | Start character offset in `full_text` (Unicode code point, inclusive) |
| `end_char` | INTEGER | End character offset in `full_text` (Unicode code point, exclusive) |
| `form` | TEXT | Surface token form (e.g. `Autonomie`, `Zusammenarbeit`) |
| `lemma` | TEXT | Lemmatized base form |
| `upos` | TEXT | Universal Dependency Part-of-Speech tag (NOUN, VERB, ADJ, PROPN, etc.) |
| `xpos` | TEXT | Language-specific morphological tag (STTS: NN, VVFIN, ART, NE, etc.) |
| `feats` | TEXT | Morphological features (Case, Gender, Number, Mood, Person, Tense) |
| `ner` | TEXT | Named Entity tag (B-PER, I-ORG, B-LOC, O, etc.) |

### Table: `word_layer_metadata`
```sql
CREATE TABLE word_layer_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

---

## 4. Multi-Word Tokens & Offset Alignment
- **Title Shift:** In the raw CoNLL-U files, text was passed to Stanza as `title + "\n" + content`. The word layer importer shifts content token offsets by `-(len(title) + 1)` so that `start_char` and `end_char` correspond strictly to indices within `full_text`.
- **Multi-Word Tokens (MWTs):** In German contractions (e.g., `Beim` $\rightarrow$ `Bei` + `dem`), the decomposed sub-tokens share the character span of the compound surface form. Both words are retained with identical `[start_char:end_char]`.
- **Integrity Validation:** Every single token is verified during ingestion against `full_text[start_char:end_char] == form`. Any article failing this check is gracefully omitted from the word layer to guarantee zero misaligned annotations.

---

## 5. Python Data Access API

### UI Data Service (`src/ui/data_service.py`)
```python
from src.ui.data_service import DataService

ds = DataService()

# Retrieve all words for an article (<2 ms)
words = ds.get_article_words("taz_20250502_in-der-falle-4")

# Retrieve words within or intersecting a character span (<0.5 ms)
passage_words = ds.get_passage_words("taz_20250502_in-der-falle-4", 50, 250)
```

### Backend Service (`backend/app/services/words.py`)
```python
from backend.app.services.words import get_article_words, get_passage_words

words = get_article_words("taz_20250502_in-der-falle-4")
passage_tokens = get_passage_words("taz_20250502_in-der-falle-4", 50, 250)
```

---

## 6. Stanza Provenance & Version
- **Model:** German (`de`) Stanza model (`processors='tokenize,lemma,pos,ner,depparse'`)
- **Stanza Version:** `unknown` on Mac (not recorded in raw archive headers or logs; check cluster notebook `/data/users/luducceschi_eurac/gits/kst_scripts_and_notebooks/stanza_process.ipynb` to verify cluster environment version)
- **Metadata table entry:** `stanza_version: unknown`

---

## 7. Rebuilding the Databases
The databases (`data/processed/didi_corpus.db` ~432 MB and `data/processed/didi_words.db` ~6.3 GB) stay local on the Mac with no backup in any remote until Luca's review by 2027-01-09.

Rebuilding the databases from scratch requires **two steps in order**: the harmonization pipeline must run first to establish the baseline corpus (Salto, Ladin varieties, and initial sample), followed by the Tageszeitung import which streams the full archive and constructs the word layer.

### Step 1: Harmonization Pipeline (Salto, Ladin & Initial Corpus)
Builds `data/processed/didi_corpus.db` from raw scraping archives and computes initial NLP framing metrics:
```bash
cd /Users/luca/Gits/didi-platform
.venv/bin/python scripts/run_harmonization.py
```
- **Inputs:** `data/raw/salto/` (727 articles), `~/Gits/digi-rlf/text_corpus/scraping_ladino/corpus_master.db` (11,362 Ladin articles), and `~/Data/KST/tagesScraping/zip_scraped_tageszeit/` (131 Tageszeitung articles).
- **Outputs:** Creates fresh `data/processed/didi_corpus.db` (12,220 articles, ~42 MB) with FTS5 search index and `article_nlp_metrics`, plus `data/processed/didi_corpus.jsonl` (copyright-safe metadata export).
- **Duration:** ~6 seconds on Apple Silicon.

### Step 2: Tageszeitung Corpus & Word Layer Ingestion
Streams the 79,504 cluster Tageszeitung articles, adds them to `didi_corpus.db`, and builds `didi_words.db`:
```bash
# 1. Verify cluster archive checksum
cd ~/Data/KST/cluster && shasum -a 256 -c MANIFEST.sha256

# 2. Run ingestion script
cd /Users/luca/Gits/didi-platform
.venv/bin/python scripts/import_kst_tageszeitung.py \
    --archive ~/Data/KST/cluster/tageszeitung.tar.gz \
    --corpus-db data/processed/didi_corpus.db \
    --words-db data/processed/didi_words.db
```
- **Inputs:** `~/Data/KST/cluster/tageszeitung.tar.gz` (3.23 GB CoNLL-U + 281 MB JSON).
- **Outputs:**
  - Adds 79,172 articles into `didi_corpus.db` (79,303 Tageszeitung total; total corpus reaches 91,492 articles, ~432 MB). Preserves the 131 existing sample articles identically.
  - Generates `didi_words.db` (~6.3 GB) storing 30,275,813 Stanza word tokens for 79,293 articles.
- **Duration:** ~170–195 seconds (under 3.5 minutes) on Apple Silicon.

### Testing Rebuild Commands (Isolated Temporary Directory)
Never run rebuild tests against production `data/processed/`. Test using the sample archive in a temporary directory:
```bash
TMPDIR=$(mktemp -d)

# Test Step 2 using the small synthetic sample on a copy of the corpus
cp data/processed/didi_corpus.db "$TMPDIR/test_corpus.db"
.venv/bin/python scripts/import_kst_tageszeitung.py \
    --sample \
    --corpus-db "$TMPDIR/test_corpus.db" \
    --words-db "$TMPDIR/test_words.db"

# Verify token table and metadata in test database
sqlite3 "$TMPDIR/test_words.db" "SELECT count(*) FROM article_words;"
sqlite3 "$TMPDIR/test_words.db" "SELECT key, value FROM word_layer_metadata;"

# Clean up temporary directory
rm -rf "$TMPDIR"
```


