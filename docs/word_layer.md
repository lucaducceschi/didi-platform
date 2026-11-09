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

