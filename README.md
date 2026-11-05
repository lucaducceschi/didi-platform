# DIDI Platform: Mixed-Methods Media Analysis & Research Workbench

**Project:** *DIDI — Gruppi diversi, prospettive diverse? Come l'inquadramento mediatico influenza le percezioni delle comunità di maggioranza e di minoranza*  
**Affiliation:** Eurac Research (Center for Autonomy Experience, Institute for Minority Rights, Institute for Applied Linguistics) & University of Innsbruck  
**Lead AI & Architecture:** Dr. Luca Ducceschi, Ph.D.  
**Repository:** Open Source GitHub [`lucaducceschi/didi-platform`](https://github.com/lucaducceschi/didi-platform)

---

## 1. Project Overview
The **DIDI Platform** is a full-stack computational research workbench designed to bridge **qualitative media discourse analysis** (the standard social science method) with **quantitative NLP metrics** (lexical diversity, discrete emotion mining, sentiment valence) and **Agentic RAG**.

It investigates how political discourse, minority rights, language policy, and regional autonomy in South Tyrol and the Dolomitic Ladin valleys are framed across three linguistic communities and five varieties:
1. **German (`de`):** *Die Neue Südtiroler Tageszeitung* (`tageszeitung.it`) & *Salto.bz* (`salto.bz/de`)
2. **Italian (`it`):** *Salto.bz* (`salto.bz/it`)
3. **Ladin (`lld_gherd`, `lld_badia`, `lld_fascia`):** *La Usc di Ladins* (`lausc.it`) & *RaiNews TGR TRAIL* (`rainews.it/tgr/trail`)

**Product Specification & UI Roadmap:** See [`docs/PRD.md`](docs/PRD.md) for full functional specifications, user personas, and the 1-week interactive Streamlit research demo roadmap.

---

## 2. Harmonized Trilingual Corpus

The platform harmonizes **12,624 articles** spanning **2,765,436 words** (2017–2026):

| Outlet / Source | Language | Variety / Dialect | Articles | Word Count |
| :--- | :--- | :--- | ---: | ---: |
| **RaiNews TGR TRAIL** | Ladin | `lld_gherd` / `lld_badia` / `lld_fascia` | 6,278 | 1,246,407 |
| **La Usc di Ladins** | Ladin | `lld_gherd` / `lld_badia` | 5,084 | 915,210 |
| **Salto.bz** | German | `de` | 741 | 382,114 |
| **Salto.bz** | Italian | `it` | 390 | 169,779 |
| **Die Neue Südtiroler Tageszeitung** | German | `de` | 131 | 51,926 |
| **Total** | *Trilingual* | *5 varieties (`de`, `it`, `lld_gherd`, `lld_badia`, `lld_fascia`)* | **12,624** | **2,765,436** |

> **Language/Dialect Breakdown:** `lld_gherd` (5,965 articles), `lld_badia` (3,880 articles), `lld_fascia` (1,517 articles), `de` (872 articles), `it` (390 articles).

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

Every ingested article is automatically profiled along three core linguistic and psycholinguistic dimensions:
1. **Lexical & Syntactic Diversity (`src/nlp/lexical.py`)**:
   - Type-Token Ratio (TTR), Guiraud's Root TTR ($V / \sqrt{N}$), Herdan's $C$ ($\log V / \log N$).
   - Hapax legomena count and ratio.
   - Sentence segmentation and Mean Sentence Length (MSL).
2. **Discrete Emotion & Sentiment Mining (`src/nlp/emotions.py`)**:
   - Integrates the multilingual **NRC Emotion Lexicon** (German & Italian).
   - Plutchik's 8 basic emotions: *Anger, Anticipation, Disgust, Fear, Joy, Sadness, Surprise, Trust*.
   - Net Sentiment Polarity ($[-1.0, +1.0]$) and emotional token density per 1,000 words.
3. **Multilingual Moral Foundations Analysis (`src/nlp/morality.py`)**:
   - Scores the 5 Moral Foundations (**Care/Harm**, **Fairness/Cheating**, **Loyalty/Betrayal**, **Authority/Subversion**, **Sanctity/Degradation**) across all 10 virtue/vice poles, overall `moral_density` (per 1,000 words), and `moral_valence` ($[-1.0, +1.0]$).
   - **Stanza `(lemma, upos)` Disambiguation (`scripts/build_mfd_lexicons.py`):** Merges Husson & Palma (2025, *Political Psychology*) with Simonsen & Widmann (2023) `mMPD_de` for German (2,876 cleaned content lemmas + nominal compound-head decomposition) and Rizzoli et al. (2026) `it-MFD` for Italian (2,619 cleaned content lemmas), eliminating function-word and auxiliary homograph collisions (e.g., IT `dei`/`stato`, DE `würde`/`bleiben`).
   - **Ladin Projection (`lld_gherd`, `lld_badia`, `lld_fascia`):** Triangulates `IT ∩ DE` across the *Dicziunari dl Ladin Standard* (`dls_dictionary.db`) and validated legal/civic terminology from **Eurac BISTRO** (`bistro.jsonl`), paired with a 17,346-form inflectional lookup table built from Forni's Gherdëina dictionary (`ladin_dictionary.db`) and `apertium-lld` until the native Ladin Stanza lemmatizer is released.
   - **Parallel Corpus Validation (`scripts/validate_mfd_parallel.py`):** Cross-lingually validated on BISTRO's aligned legal context sentences and the University of Innsbruck (`sfrontull/*`) Ladin-Italian parallel corpora following Husson & Palma's (2025) correlation ($r$) and mean-difference ($\Delta\mu$) protocol.

---

## 5. Usage & Reproducibility

### Setup
```bash
git clone git@github.com:lucaducceschi/didi-platform.git
cd didi-platform
pip install -r requirements.txt
```

### Build Unified MFD Lexicons & Run Harmonization
```bash
# 1. Compile Stanza-lemmatized DE/IT/LLD Moral Foundations lexicons (requires local assets/)
python scripts/build_mfd_lexicons.py

# 2. Harmonize full trilingual corpus into SQLite FTS5 + export metadata JSONL
python scripts/run_harmonization.py

# 3. Validate MFD across BISTRO and Hugging Face Ladin-Italian parallel corpora
python scripts/validate_mfd_parallel.py
```

### Interactive Research CLI Query
Search across qualitative text snippets with simultaneous quantitative emotion and Moral Foundations scores:
```bash
# General search
python scripts/query_corpus.py "Autonomie"

# Ladin RaiNews TRAIL articles on education
python scripts/query_corpus.py "scola" --source trail --lang lld_badia

# Filter by emotional valence or moral density
python scripts/query_corpus.py "Krise" --max-sentiment -0.2 --min-moral 10.0
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

## 6. Data Availability, Copyright & Dual-Remote Governance

To comply with publisher copyright and third-party lexicon licenses while ensuring scientific reproducibility, this project separates **public code & derived metrics** from **restricted full-text & lexical assets**:

- **Public GitHub Repository (`origin` — [`github.com/lucaducceschi/didi-platform`](https://github.com/lucaducceschi/didi-platform)):**
  - Contains the complete software architecture, harmonization/NLP pipelines, Stanza lexicon compiler, parallel validation suite, and [`data/processed/didi_corpus.jsonl`](data/processed/didi_corpus.jsonl) (**12,624 harmonized records** with article URLs, dates, categories, lexical diversity, NRC emotion densities, and Moral Foundations scores, with `full_text` omitted).
  - Excludes copyrighted full-text newspaper bodies (`data/raw/`, `*.db`) and third-party dictionary files (`assets/`) via [`.gitignore`](.gitignore).
- **Private Institutional Mirror (`gitlab` — `gitlab.inf.unibz.it/Luca.Ducceschi/didi-platform`):**
  - Restricted private repository containing the full research environment, including `assets/` (`MFD_Fr_Ge_Sp_It.Rmd`, `mMPD_de.yml`, `it-MFD.dicx`, `mfd_compiled_lemmas.json`, and `parallel_validation/`) alongside full corpus snapshots under Eurac Research / unibz academic data governance.
