# DIDI Platform: Stakeholder Demo & Expansion Brief

<!-- document: didi-executive-demo-brief-v1 -->
**Target Audience:** Eurac Research (Minority Rights, Autonomy Experience, Applied Linguistics) & University of Innsbruck Faculty  
**Presenter:** Dr. Luca Ducceschi, Ph.D.  
**Date:** November 2026  
**File Reference:** `docs/EXECUTIVE_DEMO_BRIEF.md`

---

## Part 1: Executive Summary for the Research Group

### 1. What We Have Built
The **DIDI Research Workbench** is an interactive, mixed-methods computational platform designed to answer the core question of the project:  
> **"Gruppi diversi, prospettive diverse? Come l'inquadramento mediatico influenza le percezioni delle comunità di maggioranza e di minoranza."**

In 7 days, we have harmonized and analyzed the entire regional media landscape of South Tyrol and the Dolomitic valleys into a single, offline-capable research dashboard:
- **12,624 articles (2.77 million tokens)** spanning 2017–2026.
- **5 language varieties:** German (`de`), Italian (`it`), and three Dolomitic Ladin varieties (`lld_gherd`, `lld_badia`, `lld_fascia`).
- **4 journalistic outlets:** *Die Neue Südtiroler Tageszeitung*, *Salto.bz*, *La Usc di Ladins*, and *RaiNews TGR TRAIL*.

### 2. Why Commercial Software (€15k–€50k/year) Fails for Our Project
Before investing in off-the-shelf tools (Meltwater, Brandwatch, MAXQDA, NVivo, Sketch Engine), we evaluated their capabilities:
- **The Ladin Void:** No commercial SaaS supports Dolomitic Ladin. They treat Ladin texts as OCR errors, broken Italian, or Romansh. DIDI provides native morphological dictionaries (*DLS*, *Forni*) and Eurac BISTRO terminology alignment.
- **Beyond Crude Sentiment:** Commercial tools classify text into simple "positive / negative / neutral". DIDI scores **Moral Foundations Theory (MFT 2.0)** across 5 foundational axes (*Care, Fairness, Loyalty, Authority, Sanctity*) and 8 Plutchik emotions (*Trust, Fear, Joy, Anger, etc.*).
- **Academic Focus Event Framework:** Rather than simple volume spike alerts, DIDI implements **Hurtado-Bodell & Menshikova (2026, *Poetics*)**: pre/post event windows, Dunning $G^2$ differential keyness, and the Jensen-Shannon Moral Foundations Divergence Index (MFDI).
- **Data Sovereignty & €0 Licensing:** The platform runs 100% locally on institutional hardware with zero cloud egress or subscription fees.

### 3. Proposed Next-Phase Expansions (To Vote On)
Based on commercial gaps and researcher workflows, we propose four high-leverage expansions:
1. **MAXQDA / NVivo Integration (`.qdpx` format):** Export filtered cohorts directly into qualitative CAQDAS software for manual coding and inter-rater reliability (IRR).
2. **Grammatical Word Sketches (Sketch Engine paradigm):** Reveal which adjectives and verbs modify key political terms (e.g., *"Autonomie"* vs. *"Autonomia"*) per language variety.
3. **Regional Political Actor Tracker:** Entity extraction linking regional politicians (Kompatscher, Achammer, Knoll, Meloni) to the moral frames they trigger.
4. **Agentic Qualitative Framing Synthesis:** Local, privacy-preserving LLM drafting peer-review-style comparative discourse summaries with direct citations.

---

## Part 2: Speaker's Walkthrough & Presentation Checklist

When presenting to researchers who are **not statisticians and not AI power users**, focus on **transparency, qualitative grounding, and methodological reassurance**.

### Phase 1: Setting the Stage (2 Minutes)
- [ ] **Frame the problem:** Remind them that qualitative researchers usually spend months reading hundreds of articles without knowing if their sample is representative.
- [ ] **Acknowledge the linguistic challenge:** Emphasize that South Tyrol has three distinct linguistic communities that rarely read each other's press.
- [ ] **Reassure about "Black Boxes":** State upfront: *"This tool is not an autonomous black-box AI making claims for you. It is a research magnifying glass. Every single metric links directly back to the original full text and paragraph."*

### Phase 2: Live Feature Walkthrough (5 Minutes)

#### 1. View 1: Corpus Explorer & The Triangulation Strip
- **Action:** Click the preset button **`🏫 Education`** or type `"scuola"`.
- **Show:** The **"Triangulation at a Glance"** strip.
  - *Point out:* Look at the dominant frames:
    - German press frames education around **Care (3.2/1k)**.
    - Italian press frames education around **Authority & Competences (4.6/1k)**.
    - Ladin press frames education around **Care (13.9/1k) and Loyalty (13.1/1k)** (communal survival and language transmission).
- **Show:** Expand one article (`📖 Read Full Article`) and show the clean text and APA citation.
- **Show:** The **`📥 Export CSV`** button for R / SPSS / Excel.

#### 2. View 2: Comparative Framing Radar
- **Action:** Switch to Tab 2.
- **Show:** The 5-axis Plotly radar polygon. Explain how German, Italian, and Ladin profiles map onto Care, Fairness, Loyalty, Authority, and Sanctity.
- **Check/Explain:** Emphasize that these scores are based on validated lexicons compiled with Eurac BISTRO terminology and parallel corpora (Husson & Palma 2025).

#### 3. View 4: Focus Events & Meaning-Making (The Academic Highlight)
- **Action:** Switch to Tab 4 and select the **`2018 Provincial Election`** or **`COVID-19 Lockdown & Brenner Controls`**.
- **Show:**
  - The volume surge KPI (+X%).
  - The pre/post sentiment drop.
  - The **Dunning $G^2$ Emerging Vocabulary** bar chart: show the terms that surged specifically *after* the event.
  - The **`📥 Export Keyness Table`** button.

---

## Part 3: Anticipated Questions & How to Answer Them

### Q1: *"Can we trust dictionary-based moral foundations and sentiment across three languages?"*
> **Answer:** *"Yes, because we did not use machine translation. For German and Italian, we utilized Stanza `(lemma, upos)` disambiguation that eliminates auxiliary homographs (e.g. IT 'dei' vs DE 'würde'). For Ladin, we triangulated Italian and German lexicons against the Dicziunari dl Ladin Standard (DLS) and Eurac BISTRO legal terms, validated against parallel corpus sentences."*

### Q2: *"Is our corpus biased because there are 11,000 Ladin articles and only ~1,200 German/Italian articles?"*
> **Answer:** *"All comparative metrics (densities, radar axes, valence) are normalized per 1,000 words, not by raw volume. Ladin outlets publish short daily dispatches (TRAIL broadcasts), whereas Salto publishes long-form analytical pieces. Word-level normalization ensures fair statistical comparisons."*

### Q3: *"I don't use Python or R; I code manually in MAXQDA or NVivo. Does this replace my work?"*
> **Answer:** *"Not at all. This replaces the 4 weeks of manual keyword searching and scoping. You filter your cohort here in 30 seconds, verify the framing patterns, and click 'Export' to pull the exact dataset with APA citations directly into MAXQDA or Excel."*

### Q4: *"Can we add other outlets like Dolomiten or Alto Adige?"*
> **Answer:** *"Technically, yes. The harmonization pipeline (`src/harmonizers/`) is pluggable. However, unlike Salto, Tageszeitung, and RaiNews TRAIL, commercial publishers like Athesia (Dolomiten, Alto Adige) use strict digital paywalls and legal restrictions. If Eurac negotiates institutional access or PDF archives, we can ingest them in 1 day."*

---

## Part 4: How to Pitch the Expansions

Close the presentation by putting the 4 expansion options on screen and asking the researchers for their votes:

```
[ ] 1. MAXQDA / NVivo (.qdpx) Two-Way Export
       -> For researchers who want to do qualitative sentence coding immediately.

[ ] 2. Grammatical Word Sketches (Sketch Engine style)
       -> For linguists who want to see which adjectives/verbs attach to key concepts.

[ ] 3. Regional Politician & Entity Tracker
       -> For political scientists studying coalition dynamics and actor framing.

[ ] 4. Local AI Narrative Synthesis
       -> For researchers who want draft comparative qualitative synthesis paragraphs.
```

Ask them: **"Which of these four would save you the most research hours in your next publication?"**

