# DIDI Platform: Mixed-Methods Media Analysis & Research Workbench

**Project:** *DIDI — Gruppi diversi, prospettive diverse? Come l'inquadramento mediatico influenza le percezioni delle comunità di maggioranza e di minoranza*  
**Affiliation:** Eurac Research (Center for Autonomy Experience, Institute for Minority Rights, Institute for Applied Linguistics) & University of Innsbruck  
**Lead AI & Architecture:** Dr. Luca Ducceschi, Ph.D.  
**Repository:** Open Source GitHub [`lucaducceschi/didi-platform`](https://github.com/lucaducceschi/didi-platform)

---

## 1. Project Overview
The **DIDI Platform** is a full-stack computational research workbench designed to bridge **qualitative media discourse analysis** (the standard social science method) with **quantitative NLP metrics** (lexical diversity, discrete emotion mining, sentiment valence) and **Agentic RAG**.

It investigates how political discourse, minority rights, language policy, and regional autonomy in South Tyrol are framed across three linguistic communities:
1. **German:** *Die Neue Südtiroler Tageszeitung* (`tageszeitung.it`)
2. **Bilingual (German / Italian):** *Salto.bz* (`salto.bz`)
3. **Ladin (Gardenese / Badioto):** *La Usc di Ladins* (`lausc.it`)

---

## 2. Harmonized Trilingual Corpus

The local repository is pre-loaded with an initial harmonized slice of **1,251 articles** spanning **291,371 words**:

| Outlet / Source | Language | Variety / Dialect | Articles | Word Count |
| :--- | :--- | :--- | :--- | :--- |
| **La Usc di Ladins** | Ladin | `lld_badia` | 412 | 87,419 |
| **La Usc di Ladins** | Ladin | `lld_gherd` | 588 | 92,544 |
| **Salto.bz** | German | `de` | 60 | 32,845 |
| **Salto.bz** | Italian | `it` | 60 | 26,637 |
| **Die Neue Südtiroler Tageszeitung** | German | `de` | 131 | 51,926 |
| **Total** | *Trilingual* | *All varieties* | **1,251** | **291,371** |

---

## 3. Architecture & Pluggable Storage

The platform features strict abstraction barriers to allow testing locally for **$0**, deploying to **AWS**, and seamless migration to **Microsoft Azure AI Foundry**:

```
Raw Sources (Tageszeitung, Salto, La Usc)
                  ↓
       Harmonization Pipeline (`src/harmonizers/`)
                  ↓
    Standardized Canonical Schema (`DIDIArticle`)
                  ↓
  SQLite Database + FTS5 (`data/processed/didi_corpus.db`)
                  ↓
 Quantitative NLP Engine (`src/nlp/`: Lexical Diversity + NRC Emotions)
                  ↓
 Cloud Storage Adapter (`LocalStorage` → `S3Storage` → `AzureBlobStorage`)
                  ↓
 Mixed-Methods Workbench (CLI Search + Sentiment Radar + Agentic RAG)
```

### Storage Adapters (`src/storage/adapters/`)
- `LocalStorageAdapter`: Zero-dependency, offline local disk storage.
- `S3StorageAdapter`: AWS S3 & LocalStack ($0 emulation) support.
- `AzureBlobStorageAdapter`: Microsoft Azure AI Foundry container compatibility.

---

## 4. Quantitative NLP Engine (`src/nlp/`)

Every ingested article is automatically profiled along two core linguistic dimensions:
1. **Lexical & Syntactic Diversity (`src/nlp/lexical.py`)**:
   - Type-Token Ratio (TTR), Guiraud's Root TTR ($V / \sqrt{N}$), Herdan's $C$ ($\log V / \log N$).
   - Hapax legomena count and ratio.
   - Sentence segmentation and Mean Sentence Length (MSL).
2. **Discrete Emotion & Sentiment Mining (`src/nlp/emotions.py`)**:
   - Integrates the multilingual **NRC Emotion Lexicon** (German & Italian).
   - Plutchik's 8 basic emotions: *Anger, Anticipation, Disgust, Fear, Joy, Sadness, Surprise, Trust*.
   - Net Sentiment Polarity ($[-1.0, +1.0]$) and emotional token density per 1,000 words.

---

## 5. Usage & Reproducibility

### Setup
```bash
git clone git@github.com:lucaducceschi/didi-platform.git
cd didi-platform
pip install -r requirements.txt
```

### Run Harmonization & NLP Enrichment
Populates the SQLite FTS5 database and outputs `data/processed/didi_corpus.jsonl`:
```bash
python scripts/run_harmonization.py
```

### Interactive Research CLI Query
Search across qualitative text snippets with simultaneous quantitative emotion/sentiment scores:
```bash
# General search
python scripts/query_corpus.py "Autonomie"

# Italian articles on education
python scripts/query_corpus.py "scuola" --lang it

# Filter by emotional valence (negative framing only)
python scripts/query_corpus.py "Krise" --max-sentiment -0.2
```

### Run LocalStack AWS Pipeline ($0 Emulation)
To test event-driven AWS Lambda ingestion locally with Docker:
```bash
# Start LocalStack
docker-compose up -d localstack

# Deploy S3-event Lambda trigger
./cloud/aws/deploy_localstack.sh
```

---

## 6. License & Data Governance
Internal research code and metadata harmonized under Eurac Research data governance protocols for scientific and academic analysis.
