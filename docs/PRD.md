# Product Requirements Document (PRD)
## DIDI Platform: Mixed-Methods Media Analysis & Research Workbench

**Project:** *DIDI — Gruppi diversi, prospettive diverse? Come l'inquadramento mediatico influenza le percezioni delle comunità di maggioranza e di minoranza*  
**Affiliation:** Eurac Research (Center for Autonomy Experience, Institute for Minority Rights, Institute for Applied Linguistics) & University of Innsbruck  
**Lead AI & Architecture:** Dr. Luca Ducceschi, Ph.D.  
**Document Version:** 1.0.0  
**Target Delivery (Local Working Demo):** 7 Calendar Days  

---

## 1. Executive Summary & Vision

### 1.1 Problem Statement
In multilingual and multi-ethnic regions such as South Tyrol (Alto Adige / Südtirol), public discourse surrounding territorial autonomy, minority language rights, tourism, and public finance is fragmented across linguistic lines. Social scientists studying these dynamics face a methodology gap:
- **Qualitative discourse analysis** provides deep contextual understanding but cannot scale across multi-decade corpora encompassing tens of thousands of articles.
- **Pure quantitative NLP** produces aggregate statistics that abstract away crucial qualitative context, textual evidence, and dialectal nuances (e.g., distinguishing Val Badia from Gherdëina and Fascia).

### 1.2 Product Vision
The **DIDI Workbench** is a unified computational research platform designed specifically for mixed-methods social scientists. It provides an interactive web interface where researchers can simultaneously execute:
1. **Qualitative Inquiry:** Full-text semantic search (FTS5) to discover relevant passages, quote snippets, and contextualized arguments.
2. **Quantitative Framing:** Real-time cross-linguistic profiling along discrete emotional axes (Plutchik's 8 basic emotions via NRC EmoLex) and moral foundations (Moral Foundations Theory: Care, Fairness, Loyalty, Authority, Sanctity) across German, Italian, and Ladin.
3. **Comparative Visualization:** Direct side-by-side triangulation revealing how identical societal topics (e.g., *Autonomie / Autonomia*, *Schule / Scola*, *Tourismus / Turism*) are framed differently across majority and minority linguistic communities.

---

## 2. Target User Personas

| Persona | Role | Primary Needs | Critical Success Metric |
| :--- | :--- | :--- | :--- |
| **Dr. Elena (Social Scientist / Qualitative Analyst)** | Postdoc in Minority Rights & Regional Politics | Needs to search topics across German, Italian, and Ladin, view in-context text snippets, filter by emotional tone, and export quotes for journal articles. | Ability to find and inspect relevant multilingual text excerpts in < 3 seconds. |
| **Matteo (Computational Linguist / DH Specialist)** | Applied Linguistics Researcher | Needs to compare aggregate metrics (Type-Token Ratio, Mean Sentence Length, Moral Foundation densities) across dialects and validate cross-lingual dictionary parity. | Transparent access to underlying metrics, lemma counts, and CSV/JSONL export. |
| **Prof. Karl (Institute Director / Grant Evaluator)** | Principal Investigator & Stakeholder | Needs an intuitive, high-level visual dashboard that demonstrates research impact, interactive radar comparisons, and temporal trends for presentations and reports. | Self-explanatory, interactive visual story runnable locally with zero setup friction. |

---

## 3. Existing Technical Assets & Foundation

The platform builds directly upon pre-existing, tested computational assets:
- **Corpus Database ([`data/processed/didi_corpus.db`](file:///Users/luca/Gits/didi-platform/data/processed/didi_corpus.db)):** 12,624 articles, 2,765,436 tokens (2017–2026) across 5 linguistic varieties (`lld_gherd`, `lld_badia`, `lld_fascia`, `de`, `it`) with active SQLite FTS5 search.
- **Quantitative Metrics Pipeline:** Pre-computed `article_nlp_metrics` table with lexical diversity (TTR, Root TTR, Herdan's $C$, Hapax ratio), NRC discrete emotions, and 10-pole Moral Foundations Theory densities ($[0, \infty)$ per 1,000 words, plus net moral valence $[-1.0, +1.0]$).
- **Stanza MFD 2.0 Lexicon Engine:** Curated and Stanza-disambiguated dictionaries for German, Italian, and triangulated Ladin (DLS + Eurac BISTRO + 17k Forni inflections).
- **Dual-Remote Architecture:** Open-source public code & copyright-safe metadata on GitHub (`origin`), full-text data and dictionary assets on institutional GitLab (`gitlab`).

---

## 4. Proposed Demo Architecture: Streamlit + Plotly

For a **1-week working demo**, **Streamlit** combined with **Plotly** is the optimal choice:
- **Zero Frontend Build Chain:** Pure Python codebase — no Node.js, Webpack, or React compilation hurdles.
- **Direct Database Connectivity:** Direct native read-only access to SQLite (`didi_corpus.db`) via `sqlite3` and Python `@st.cache_data`.
- **Publication-Ready Visualizations:** Interactive Plotly radar charts, time-series timelines, and box plots with hover tooltips and zoom capabilities.
- **Portability:** Runs locally with `streamlit run app.py` on macOS/Linux and packages cleanly into a Docker container or Azure/HPC deployment.

---

## 5. Functional Specifications: The 4 Core Views

```
┌────────────────────────────────────────────────────────────────────────┐
│                        DIDI RESEARCH WORKBENCH                         │
│  [Sidebar: Topic Search | Sources | Languages | Sentiment & Moral Filters] │
├────────────────────────────────────────────────────────────────────────┤
│ [Tab 1: Corpus Explorer]  [Tab 2: Framing Radar]  [Tab 3: Temporal]   │
│                                                                        │
│  • Side-by-side linguistic comparison (DE vs IT vs LLD)                │
│  • Quantitative framing radar (Care, Fairness, Loyalty, Auth, Sanct)   │
│  • In-context keyword snippets with emotion & moral score badges       │
│  • Article full-text deep-dive with annotated token inspection         │
└────────────────────────────────────────────────────────────────────────┘
```

### View 1: Cross-Lingual Corpus Explorer & Qualitative Search
- **Faceted Filters (Sidebar):**
  - Keyword / Topic Search (FTS5 full-text query with boolean operators: e.g. `Autonomie OR Autonomia`, `Scola`).
  - Source Multi-Select (*Die Neue Südtiroler Tageszeitung*, *Salto.bz*, *La Usc di Ladins*, *RaiNews TGR TRAIL*).
  - Language Variety Multi-Select (`de`, `it`, `lld_gherd`, `lld_badia`, `lld_fascia`).
  - Date Range Picker (2017 to 2026).
  - Net Sentiment Valence Slider ($-1.0$ to $+1.0$).
  - Moral Foundation Threshold Slider (minimum moral density per 1,000 words).
- **Results Table / Card Stream:**
  - Displays article cards with Title, Outlet, Date, Language Variety badge, Word Count, and FTS5 Context Snippet with search terms highlighted.
  - Interactive badges showing Net Sentiment, Top Emotion, and Dominant Moral Foundation.
  - "Inspect Full Text" button opening the Article Deep-Dive modal/drawer.

### View 2: Comparative Framing Radar (Triangulation View)
- **Moral Foundations Radar Chart:**
  - Comparative 5-axis polygon overlay comparing German (`de`), Italian (`it`), and Ladin (`lld`) framing on the queried topic.
  - Axes: *Care*, *Fairness*, *Loyalty*, *Authority*, *Sanctity*.
- **Discrete Emotion Distribution Bar / Polar Plot:**
  - Plutchik 8-emotion density comparison per language group (*Anger, Anticipation, Disgust, Fear, Joy, Sadness, Surprise, Trust*).
- **Virtue vs. Vice Polarity Matrix:**
  - Stacked bar breakdown showing whether morality is framed affirmatively (virtue) or polemically (vice).

### View 3: Temporal Discourse Dynamics (Timeline View)
- **Time-Series Trend Chart:**
  - Monthly or quarterly aggregation of topic coverage volume, mean sentiment valence, and moral density over time.
  - Visual flags for regional milestone events (e.g., South Tyrolean provincial elections, regional budget debates, COVID-19 lockdowns).
- **Outlet Divergence Heatmap:**
  - Heatmap showing which outlets express the highest emotional intensity or moral framing on the queried topic.

### View 4: Qualitative Article Inspector (Deep Dive)
- **Full Text Reader:**
  - Clean typographic layout displaying article title, byline/author, publication date, URL source link, and complete paragraphs.
- **Interactive Linguistic Annotations:**
  - Highlight tokens triggering NRC emotion scores (color-coded by positive/negative valence).
  - Highlight tokens triggering Moral Foundations (color-coded by foundation).
- **Metadata Sidebar:** Complete JSON metadata drawer (breadcrumbs, raw tags, categories, exact lexical diversity metrics: TTR, Hapax ratio, MSL).

---

## 6. One-Week Implementation Plan (Day-by-Day)

| Day | Focus Area | Deliverables | Verification Milestone |
| :---: | :--- | :--- | :--- |
| **Day 1** | **Data Service & Project Scaffolding** | Create `src/ui/data_service.py` to handle cached queries from `didi_corpus.db`. Set up Streamlit layout and global styling (`src/ui/app.py`). | `streamlit run src/ui/app.py` loads corpus summary cards in < 0.5s. |
| **Day 2** | **View 1: Corpus Explorer & Qualitative Search** | Implement FTS5 keyword query engine, faceted sidebar filters, and paginated article cards with highlighted snippets. | Search query "Autonomie" renders filtered cards across DE, IT, and LLD. |
| **Day 3** | **View 2: Comparative Framing Radar** | Build interactive Plotly Radar chart and Emotion distribution plots grouped by language variety. | Radar chart dynamically renders 3 language polygons for any search query. |
| **Day 4** | **View 3: Temporal Discourse Dynamics** | Build time-series aggregation of sentiment and moral foundation density over 2017–2026. | Monthly timeline renders coverage spikes and valence shifts cleanly. |
| **Day 5** | **View 4: Article Inspector & Token Highlighting** | Implement single-article inspection view with in-text highlighting of moral and emotional lexical triggers. | Clicking an article card opens full text with colored moral/emotional tokens. |
| **Day 6** | **Polish, Caching Optimization & Export** | Add CSV/Excel export for filtered queries, optimize SQL query indices, ensure responsive typography on desktop and laptop displays. | Export button generates research-ready CSV with all NLP metrics and snippet context. |
| **Day 7** | **Dry-Run, Docker Packaging & Demo Script** | Package into a self-contained `docker-compose` run, write user walkthrough guide in `README.md`, test with real Eurac research questions. | Flawless end-to-end 5-minute walkthrough ready for stakeholders. |

---

## 7. Non-Functional Requirements & Governance

1. **Local Performance:**
   - Database queries must execute in $< 200\text{ ms}$ using existing SQLite FTS5 and indexed columns (`publish_date`, `source`, `language`, `net_sentiment`).
   - Streamlit page transitions must feel instantaneous using `@st.cache_data`.
2. **Offline Reproducibility:**
   - The entire dashboard must run completely offline without relying on external API calls or internet access (using the pre-compiled `didi_corpus.db`).
3. **Data Governance & Copyright:**
   - The local dashboard reads full text from the local SQLite database.
   - Public code pushes continue to strictly respect the dual-remote policy (only code and metadata on GitHub, full-text and assets exclusively on the private GitLab).
4. **Code Quality:**
   - Modular architecture separating database logic (`src/storage/`), data transformation (`src/ui/data_service.py`), and visualization components (`src/ui/components/`).

---

## 8. Success Criteria for the 1-Week Demo

1. **Usability:** A social science researcher with zero command-line experience can open the browser, type a keyword (e.g., *"Scuola"* or *"Autonomie"*), and visually identify framing divergences between German, Italian, and Ladin news outlets.
2. **Academic Credibility:** Every visual metric on screen links directly back to transparent textual evidence (clickable quotes and articles).
3. **Institutional Readiness:** The demo serves as an immediate proof-of-concept for Eurac Research and University of Innsbruck presentations and project grant reviews.

