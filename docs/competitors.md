# DIDI Platform: Competitive Landscape & Commercial Expansion Analysis

<!-- document: competitors-analysis-v1 -->
**Prepared for:** DIDI Project — Eurac Research & University of Innsbruck  
**Author:** AI Technical & Research Architecture  
**Date:** November 2026  
**File:** `docs/competitors.md`

---

## 1. Executive Summary

If the DIDI project were to purchase commercial or academic software instead of building a tailored workbench, **no single tool currently exists that solves our research problem out of the box**. 

The DIDI project sits at the intersection of **three distinct software markets**:
1. **Qualitative Data Analysis (CAQDAS):** *MAXQDA, NVivo, ATLAS.ti*
2. **Enterprise Media Intelligence & Social Listening:** *Meltwater, Brandwatch, LexisNexis Newsdesk*
3. **Corpus Linguistics & Lexicography:** *Sketch Engine, LancsBox*

This document breaks down the major commercial tools in these spaces, details **what they offer that DIDI currently lacks**, analyzes **what DIDI possesses that commercial tools cannot replicate**, and outlines a **concrete roadmap for expanding DIDI** based on the best commercial paradigms.

---

## 2. Comprehensive Tool Directory

### Category A: Academic CAQDAS (Computer-Assisted Qualitative Data Analysis)

#### 1. MAXQDA (VERBI Software — Berlin, Germany)
*Standard in European social sciences (Germany, Austria, Italy, Switzerland).*
- **What it does:** Mixed-methods qualitative coding, document variables, focus group analysis, mixed-methods crosstabs, and visual tools (Code Relations Browser, Code Matrix).
- **Recent AI Capabilities:** *MAXQDA AI Assist* (integrated OpenAI/local models) for automatic transcription, theme extraction, code summarization, and concept suggestions.
- **Licensing Cost:** €900 – €2,500/seat (perpetual or multi-year academic license).

#### 2. NVivo (Lumivero — Denver, USA)
*Standard in Anglo-American academic research.*
- **What it does:** Text coding, hierarchy trees, matrix coding queries, sociogram networks, automated sentiment classification (positive/negative/mixed), and integration with citation managers (Zotero, EndNote).
- **Recent AI Capabilities:** Automated theme extraction, sentiment clustering, and Lumivero AI transcription.
- **Licensing Cost:** €1,200 – €3,000/seat.

#### 3. ATLAS.ti (ATLAS.ti Scientific Software — Berlin, Germany)
- **What it does:** Hermeneutic unit coding, visual knowledge networks, co-occurrence analysis, and multi-coder teamwork.
- **Recent AI Capabilities:** Full AI coding (auto-tagging paragraphs based on user research questions), intentional AI summarization.
- **Licensing Cost:** €700 – €2,000/seat.

---

### Category B: Enterprise Media Intelligence & News Analytics

#### 4. Meltwater (Meltwater Group — San Francisco / Oslo)
*The global standard for corporate & institutional media monitoring.*
- **What it does:** Live crawling of 300,000+ global news outlets, paywalled publications, broadcast media (TV/Radio transcription), and social media.
- **Analytics:** Spike detection, journalist influence scoring, sentiment trends, competitive share-of-voice, and automated PDF executive briefings.
- **Licensing Cost:** €15,000 – €50,000+/year subscription.

#### 5. LexisNexis Newsdesk / Dow Jones Factiva
*The gold standard for legal, historical, and archival news retrieval.*
- **What it does:** Deep licensed full-text archives going back 40+ years with complete copyright clearance. High-speed Boolean indexing, company/politician entity linking, and structured taxonomy tagging.
- **Licensing Cost:** €10,000 – €40,000+/year institutional subscription.

#### 6. Brandwatch Consumer Intelligence / Talkwalker
- **What it does:** Deep sentiment analysis, image/logo recognition in press, consumer emotion classification, narrative clustering, and conversational graphs.
- **Licensing Cost:** €20,000 – €60,000+/year.

---

### Category C: Corpus Linguistics & Psycholinguistics

#### 7. Sketch Engine (Lexical Computing — Brno / Brighton)
*The premier tool for lexicographers, terminologists, and corpus linguists (used by Oxford, Duden, Eurac BISTRO).*
- **What it does:** 
  - **Word Sketches:** Syntactic collocations (e.g., finding which verbs and adjectives collocate specifically with *"Autonomie"* vs. *"Autonomia"*).
  - **Bilingual Concordancing & Terminology Extraction:** Aligned bilingual terminology discovery.
  - **Dunning Log-Likelihood Keyness:** Compares subcorpora against reference corpora.
- **Licensing Cost:** €250 – €1,000/year academic institutional access.

#### 8. Relative Insight / Symanto
*Commercial psycholinguistic platforms.*
- **What it does:** Applies linguistic style and personality trait extraction to compare how two demographics or outlets talk differently about the exact same topic.
- **Licensing Cost:** €15,000 – €30,000/year.

---

## 3. The Capability Gap: What They Offer That DIDI Does Not

If we purchased these tools, here is the exact feature set we would gain that our current platform lacks:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       COMMERCIAL CAPABILITY ADVANTAGES                      │
├───────────────────────────────┬─────────────────────────────────────────────┤
│ 1. Continuous Live Sourcing   │ Automated daily scrapers, paywall bypasses, │
│    & Ingestion Pipeline       │ RSS monitors, and real-time news alerts.    │
├───────────────────────────────┼─────────────────────────────────────────────┤
│ 2. Named Entity Recognition   │ Automatic identification & disambiguation   │
│    (NER) & Knowledge Graphs   │ of actors (Kompatscher, Meloni, SVP, Lega)  │
│                               │ and linking them to specific statements.    │
├───────────────────────────────┼─────────────────────────────────────────────┤
│ 3. Qualitative Manual Coding  │ The ability for human researchers to select │
│    & Inter-Coder Reliability  │ sentences, attach custom coding nodes, and  │
│    (CAQDAS workflow)          │ calculate Krippendorff's alpha (IRR).       │
├───────────────────────────────┼─────────────────────────────────────────────┤
│ 4. Grammatical Collocations   │ Syntactic grammar relations: What verbs and │
│    (Word Sketches)            │ modifiers attach to target concepts in each │
│                               │ language variety?                           │
├───────────────────────────────┼─────────────────────────────────────────────┤
│ 5. Agentic Qualitative        │ Generative AI generating qualitative essay  │
│    Framing Synthesis          │ drafts comparing discourse across languages │
│                               │ citing specific article excerpts.           │
├───────────────────────────────┼─────────────────────────────────────────────┤
│ 6. Multi-User Collaboration   │ Multi-tenant accounts, project sharing,     │
│    & Cloud Workspaces         │ annotations, and audit logs.                │
└───────────────────────────────┴─────────────────────────────────────────────┘
```

---

## 4. DIDI's Strategic Moat: What None of These Tools Can Do

Commercial platforms fail completely when applied to the specific socio-political and linguistic reality of South Tyrol and the Dolomitic valleys:

| Critical Dimension | Commercial Platforms (Meltwater, MAXQDA, NVivo) | DIDI Research Platform |
| :--- | :--- | :--- |
| **Dolomitic Ladin Varieties (`lld_gherd`, `lld_badia`, `lld_fascia`)** | **Completely unsupported.** Treated as OCR noise, broken Italian, or Romansh errors. Lexicons and lemmatizers do not exist in any commercial SaaS. | **Native Support.** Morphological lookups (*DLS*, *Forni*), Eurac BISTRO terminology alignment, and validated tri-variety corpus (11,362 articles). |
| **Moral Foundations Theory (MFT 2.0)** | **Non-existent.** Commercial tools offer generic 3-class sentiment (positive / neutral / negative) or basic polarity sliders. | **Full 5-Foundation / 10-Pole Profiling.** Stanza-lemmatized lexicons for German, Italian, and Ladin projection, scoring Care, Fairness, Loyalty, Authority, Sanctity. |
| **Focus Event Meaning-Making** | None implement academic sociolinguistic models. Event tracking is limited to raw volume spike alerts. | **Grounded in Hurtado-Bodell & Menshikova (2026).** Pre/post windowing, Dunning $G^2$ differential keyness, and Jensen-Shannon Moral Divergence Index (MFDI). |
| **Regional Provenance Isolation** | National news aggregators ingest syndicated national wires (ANSA, dpa, APA), completely drowning out local editorial discourse. | **Strict Provenance Filtering.** Excludes wire duplication; isolates true regional production (*Tageszeitung, Salto, La Usc, TRAIL*). |
| **Cost & Data Sovereignty** | €15,000 – €60,000/year recurring subscriptions. Data uploaded to US/cloud third-party servers. | **€0 ongoing cost.** 100% offline reproducibility, institutional data sovereignty compliant with Eurac / unibz privacy standards. |

---

## 5. Expansion Blueprint: Features to Adopt into DIDI

To bridge the gap and elevate DIDI into a world-class, grant-winning research workbench, we should adopt the highest-value features from these commercial tools:

### Phase 1: CAQDAS Integration (Borrow from MAXQDA)
- **Qualitative Annotation Drawer:** Allow researchers clicking into an article to highlight passages and assign qualitative codes (e.g., `[Autonomy-Fiscal]`, `[Minority-Protection]`, `[Cross-Border-Transit]`).
- **Export to MAXQDA / NVivo:** Add a 1-click export of filtered corpora into `.qdpx` (the universal Qualitative Data Exchange Format) so researchers can seamlessly transition from quantitative scanning into manual coding.

### Phase 2: Grammatical Collocations (Borrow from Sketch Engine)
- **Word Sketches for South Tyrolean Concepts:** Implement dependency-based collocation tables. When a user queries *"Autonomie"*, display the top adjectives (*"finanzielle"*, *"dynamische"*, *"differenzierte"*) and top verbs (*"verteidigen"*, *"aushöhlen"*, *"reformieren"*) grouped by outlet.

### Phase 3: Actor & Entity Linking (Borrow from Meltwater / Factiva)
- **Regional Gazetteer & Politician Tracker:** Extract mentions of regional political figures (Arno Kompatscher, Philipp Achammer, Sven Knoll, Giorgia Meloni) and show which moral foundations are invoked when each actor is discussed.

### Phase 4: Agentic Narrative Synthesis (Borrow from Next-Gen AI)
- **"Draft Framing Synthesis" Button:** Connect a local offline LLM (e.g., LLaMA-3.1-8B running via Ollama/vLLM) that reads the top 10 articles from each linguistic variety and generates a peer-review-style qualitative summary of how the narrative differs across the three communities.

---

## 6. Synthesis Matrix for Stakeholder Discussions

```
                      ACADEMIC RIGOR & LOCAL VALIDITY
                                    ▲
                                    │
                                    │      ★ DIDI PLATFORM
                                    │      (Ladin, MFD 2.0, Regional Autonomy,
                                    │       Dunning G² + JSD Event Framing)
               Sketch Engine        │
                     ○              │
                                    │
    MAXQDA / NVivo                  │
          ○                         │
                                    │
────────────────────────────────────┼─────────────────────────────────────►
AUTOMATION & COMMODITY FEATURES     │               ENTERPRISE MEDIA SAAS
(Generic sentiment, generic PDFs)   │               (Meltwater, Talkwalker)
                                    │                         ○
                                    │
                                    │
```

---

*This document is stored as `docs/competitors.md` in the repository and synced with the team.*
