"""
DIDI Platform — Research Workbench Web Application.
Mixed-Methods Media Analysis for Eurac Research and University of Innsbruck.
"""

import html
import re
import textwrap
import streamlit as st
import pandas as pd
from pathlib import Path
import sys

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ui.data_service import (
    DataService, LANGUAGE_LABELS, SOURCE_LABELS, FOUNDATION_COLS, EMOTION_COLS
)
from src.ui.components.charts import (
    build_moral_radar, build_emotion_bars, build_timeline_chart,
    build_keyness_bar_chart, build_moral_divergence_gauge, build_pre_post_moral_comparison
)

# Page configuration
st.set_page_config(
    page_title="DIDI Research Workbench",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom academic styling
st.markdown("""
<style>
    .reportview-container {
        background: #fdfdfd;
    }
    .main-header {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        font-weight: 700;
        color: #1a2a3a;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        color: #556677;
        font-size: 0.95rem;
        margin-bottom: 1.5rem;
    }
    .fts-hl {
        background-color: #ffeaa7;
        font-weight: 600;
        padding: 0 3px;
        border-radius: 2px;
    }
    .metric-badge {
        display: inline-block;
        padding: 2px 7px;
        font-size: 0.75rem;
        font-weight: 600;
        border-radius: 4px;
        margin-right: 4px;
    }
    .badge-de { background-color: #e3f2fd; color: #0d47a1; }
    .badge-it { background-color: #e8f5e9; color: #1b5e20; }
    .badge-lld { background-color: #fff3e0; color: #e65100; }
    .article-card {
        background: #ffffff;
        border: 1px solid #e1e8ed;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 14px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }
</style>
""", unsafe_allow_html=True)


def highlight_query(text: str, query: str) -> str:
    """Highlight matched query terms in full text using safe HTML tags."""
    if not query or not query.strip() or not text:
        return html.escape(text) if text else ""
    terms = [re.escape(t) for t in query.strip().split() if len(t) >= 2]
    if not terms:
        return html.escape(text)
    pattern = re.compile(r"(" + "|".join(terms) + r")", re.IGNORECASE)
    escaped_text = html.escape(text)
    return pattern.sub(r'<mark class="fts-hl">\1</mark>', escaped_text)


def get_service() -> DataService:
    return DataService()


def render_sidebar(service: DataService):
    st.sidebar.title("🔍 Corpus Filters")

    if "query_input" not in st.session_state:
        st.session_state["query_input"] = ""

    # 1. Topic Query
    query = st.sidebar.text_input(
        "FTS5 Topic Search",
        key="query_input",
        placeholder="e.g. Autonomie, scuola, turism...",
        help="Search query executed via SQLite FTS5 index across German, Italian, and Ladin."
    )

    # Search Intelligence Options
    expand_trilingual = st.sidebar.checkbox(
        "🌐 Trilingual Concept Bridge",
        value=True,
        help="Expands queries across German, Italian, and Ladin (e.g. scuola -> Schule -> scola)."
    )
    enable_prefix = st.sidebar.checkbox(
        "⚡ Stem / Prefix Matching (*)",
        value=True,
        help="Matches grammatical endings (e.g. autonom* matches Autonomie, autonomo, autonoma)."
    )
    use_hybrid = st.sidebar.checkbox(
        "🧠 Hybrid Semantic Reranking",
        value=True,
        help="Fuses BM25 keyword matching with multilingual MiniLM vector similarity."
    )

    # 2. Outlets
    all_sources = list(SOURCE_LABELS.keys())
    selected_sources = st.sidebar.multiselect(
        "News Outlets",
        options=all_sources,
        default=all_sources,
        format_func=lambda s: SOURCE_LABELS.get(s, s)
    )

    # 3. Languages
    all_langs = list(LANGUAGE_LABELS.keys())
    selected_langs = st.sidebar.multiselect(
        "Language Varieties",
        options=all_langs,
        default=all_langs,
        format_func=lambda l: LANGUAGE_LABELS.get(l, l)
    )

    # 4. Net Sentiment Range
    st.sidebar.markdown("---")
    st.sidebar.subheader("Valence & Morality")
    sent_range = st.sidebar.slider(
        "Net Sentiment Range",
        min_value=-1.0,
        max_value=1.0,
        value=(-1.0, 1.0),
        step=0.05,
        help="Filter articles by net sentiment valence (positive minus negative density)."
    )

    # 5. Minimum Moral Density
    min_moral = st.sidebar.slider(
        "Min. Moral Density (/1k)",
        min_value=0.0,
        max_value=40.0,
        value=0.0,
        step=1.0,
        help="Filter articles containing at least N moral foundations tokens per 1,000 words."
    )

    return {
        "query": query,
        "sources": selected_sources,
        "languages": selected_langs,
        "min_sentiment": sent_range[0],
        "max_sentiment": sent_range[1],
        "min_moral": min_moral,
        "expand_trilingual": expand_trilingual,
        "enable_prefix": enable_prefix,
        "use_hybrid": use_hybrid
    }


def main():
    service = get_service()

    # App Header
    st.markdown('<h1 class="main-header">⚖️ DIDI Platform: Mixed-Methods Media Research Workbench</h1>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header"><b>Eurac Research</b> (Minority Rights & Autonomy Experience) & <b>University of Innsbruck</b> | 12,624 Articles (2017–2026)</p>', unsafe_allow_html=True)

    filters = render_sidebar(service)

    # Overview KPI row
    summary = service.get_corpus_summary()
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("Total Articles", f"{summary['total_articles']:,}")
    kpi2.metric("Total Words Analyzed", f"{summary['total_words']:,}")
    kpi3.metric("NLP & MFT Profiled", f"{summary['nlp_count']:,}")
    kpi4.metric("Temporal Span", f"{summary['min_date'][:4]} – {summary['max_date'][:4]}")

    st.markdown("---")

    # 5 Core Views
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📄 1. Corpus Explorer & Snippets",
        "🕸️ 2. Comparative Framing Radar",
        "📈 3. Temporal Discourse Dynamics",
        "⚡ 4. Focus Events & Meaning-Making",
        "🔎 5. Article Deep Dive"
    ])

    # -------------------------------------------------------------
    # TAB 1: Corpus Explorer
    # -------------------------------------------------------------
    with tab1:
        st.subheader("Cross-Lingual Search & Qualitative Text Snippets")

        # Preset Research Inquiries
        st.markdown("**💡 Thematic Inquiries (One-Click Trilingual Search):**")
        p_cols = st.columns(6)
        presets = [
            ("🏫 Education", "scuola"),
            ("🏛️ Autonomy", "autonomia"),
            ("🐺 Predators", "lupo"),
            ("🚦 Brenner Transit", "brenner"),
            ("🤝 Coalition", "koalition"),
            ("🗣️ Language Rights", "bilinguismo")
        ]
        for idx, (label, val) in enumerate(presets):
            with p_cols[idx]:
                if st.button(label, key=f"btn_p_{val}", use_container_width=True):
                    st.session_state["query_input"] = val
                    st.rerun()

        col_ctrl1, col_ctrl2 = st.columns([3, 1])
        with col_ctrl1:
            st.caption(f"Showing results for query: **'{filters['query'] or 'ALL ARTICLES'}'**")
        with col_ctrl2:
            page_size = st.selectbox("Page Size", options=[10, 20, 50], index=0)

        articles, total_matches = service.search_articles(
            query=filters["query"],
            sources=filters["sources"],
            languages=filters["languages"],
            min_sentiment=filters["min_sentiment"],
            max_sentiment=filters["max_sentiment"],
            min_moral=filters["min_moral"],
            expand_trilingual=filters.get("expand_trilingual", True),
            enable_prefix=filters.get("enable_prefix", True),
            use_hybrid=filters.get("use_hybrid", True),
            limit=page_size,
            offset=0
        )

        if service.last_query_expansion:
            st.info(f"💡 **Search Intelligence:** {service.last_query_expansion}")

        st.write(f"Found **{total_matches:,}** matching articles (ranked by Hybrid BM25 + Vector Fusion).")

        if not articles:
            st.info("No articles match the current combination of filters. Try broadening your search or resetting sliders.")
        else:
            for art in articles:
                lang = art["language"]
                badge_class = "badge-de" if lang == "de" else ("badge-it" if lang == "it" else "badge-lld")
                s_val = art.get("net_sentiment", 0.0)
                sent_color = "#27ae60" if s_val > 0.1 else ("#c0392b" if s_val < -0.1 else "#7f8c8d")
                sent_label = "Positive" if s_val > 0.1 else ("Negative" if s_val < -0.1 else "Neutral")

                # Compute Moral Badges
                moral_badges = []
                if art.get("authority_density", 0.0) >= 0.5:
                    moral_badges.append(f'<span class="metric-badge" style="background:#ebf8ff; color:#2b6cb0; border:1px solid #bee3f8;">🏛️ Authority ({art["authority_density"]:.1f})</span>')
                if art.get("fairness_density", 0.0) >= 0.5:
                    moral_badges.append(f'<span class="metric-badge" style="background:#f0fff4; color:#276749; border:1px solid #c6f6d5;">⚖️ Fairness ({art["fairness_density"]:.1f})</span>')
                if art.get("care_density", 0.0) >= 0.5:
                    moral_badges.append(f'<span class="metric-badge" style="background:#faf5ff; color:#6b46c1; border:1px solid #e9d8fd;">💚 Care ({art["care_density"]:.1f})</span>')
                if art.get("loyalty_density", 0.0) >= 0.5:
                    moral_badges.append(f'<span class="metric-badge" style="background:#fffaf0; color:#c05621; border:1px solid #feebc8;">🛡️ Loyalty ({art["loyalty_density"]:.1f})</span>')
                if art.get("sanctity_density", 0.0) >= 0.5:
                    moral_badges.append(f'<span class="metric-badge" style="background:#fff5f5; color:#9b2c2c; border:1px solid #fed7d7;">✨ Sanctity ({art["sanctity_density"]:.1f})</span>')
                moral_badges_html = " ".join(moral_badges) if moral_badges else '<span style="font-size:0.75rem; color:#a0aec0;">No prominent moral markers</span>'

                # Dominant Emotion
                emos = {
                    "Trust": art.get("trust_density", 0.0),
                    "Joy": art.get("joy_density", 0.0),
                    "Anticipation": art.get("anticipation_density", 0.0),
                    "Fear": art.get("fear_density", 0.0),
                    "Sadness": art.get("sadness_density", 0.0),
                    "Anger": art.get("anger_density", 0.0),
                    "Disgust": art.get("disgust_density", 0.0)
                }
                top_emo = max(emos.items(), key=lambda x: x[1])
                emo_badge_html = f'<span class="metric-badge" style="background:#f7fafc; color:#4a5568; border:1px solid #e2e8f0;">🎭 {top_emo[0]} ({top_emo[1]:.1f}/1k)</span>' if top_emo[1] >= 1.5 else ""

                # Semantic Match Badge
                sem_sim = art.get("semantic_sim")
                sem_badge_html = f'<span class="metric-badge" style="background:#e6fffa; color:#234e52; border:1px solid #b2f5ea;">🧠 {sem_sim:.0%} Semantic Match</span>' if sem_sim else ""

                author_clean = art.get('author') or 'Redaktion'
                cat_clean = art.get('category') or 'General'

                card_html = textwrap.dedent(f"""
                <div class="article-card">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                        <div>
                            <span class="metric-badge {badge_class}">{lang.upper()}</span>
                            <span class="metric-badge" style="background:#edf2f7; color:#2d3748;">{SOURCE_LABELS.get(art['source'], art['source'])}</span>
                            <span style="font-size:0.8rem; color:#718096; margin-right:8px;">📅 {art['publish_date'][:10]}</span>
                            <span style="font-size:0.8rem; color:#718096;">✍️ {author_clean}</span>
                        </div>
                        <div>
                            <span style="font-size:0.8rem; font-weight:600; color:{sent_color}; margin-right:12px;">Valence: {s_val:+.2f} ({sent_label})</span>
                            <span style="font-size:0.8rem; color:#4a5568;">Tokens: {art['word_count']}</span>
                        </div>
                    </div>
                    <h3 style="margin:4px 0 8px 0; color:#1a202c; font-size:1.15rem;">{art['title']}</h3>
                    <p style="font-size:0.95rem; color:#2d3748; line-height:1.6; margin-bottom:12px; background:#f8fafc; padding:10px 14px; border-left:3px solid #3182ce; border-radius:4px;">
                        {art['snippet']}
                    </p>
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-top:8px;">
                        <div>
                            {moral_badges_html}
                            {emo_badge_html}
                            {sem_badge_html}
                        </div>
                        <span style="font-size:0.78rem; color:#a0aec0;">Category: {cat_clean} | ID: {art['id']}</span>
                    </div>
                </div>
                """).strip()
                st.markdown(card_html, unsafe_allow_html=True)

                # Expandable Full-Text Reader Drawer
                with st.expander(f"📖 Read Full Article: \"{art['title']}\" ({art['word_count']} words)", expanded=False):
                    pub_year = art['publish_date'][:4]
                    src_title = SOURCE_LABELS.get(art['source'], art['source'])
                    apa_cite = f"{author_clean}. ({pub_year}). {art['title']}. {src_title}. DIDI Corpus ID: {art['id']}."

                    col_c1, col_c2 = st.columns([4, 1])
                    with col_c1:
                        st.caption(f"**APA Citation:** `{apa_cite}`")
                    with col_c2:
                        st.link_button("Original Outlet ↗", art['url'])

                    st.markdown("---")
                    raw_body = art.get('full_text')
                    if not raw_body:
                        # Bulletproof safeguard: fetch directly by ID if not in memory
                        full_art = service.get_article_by_id(art['id'])
                        raw_body = full_art.get('full_text', '') if full_art else ''

                    if raw_body:
                        hl_body = highlight_query(raw_body, filters['query'])
                        for paragraph in hl_body.split('\n\n'):
                            if paragraph.strip():
                                st.markdown(f"<p style='font-size:0.96rem; line-height:1.65; color:#1a202c;'>{paragraph.strip()}</p>", unsafe_allow_html=True)
                    else:
                        st.warning("Article text could not be loaded from local database.")

    # -------------------------------------------------------------
    # TAB 2: Framing Radar
    # -------------------------------------------------------------
    with tab2:
        st.subheader("Triangulated Framing: German vs Italian vs Ladin")
        st.caption("Aggregates Moral Foundations Theory and discrete emotion densities across matching articles.")

        radar_df = service.get_aggregated_radar_data(
            query=filters["query"],
            sources=filters["sources"],
            languages=filters["languages"]
        )

        if radar_df.empty:
            st.warning("Insufficient data to compute framing radar for current selection.")
        else:
            col_radar, col_emo = st.columns([1, 1])
            with col_radar:
                fig_radar = build_moral_radar(radar_df)
                st.plotly_chart(fig_radar, use_container_width=True)

            with col_emo:
                fig_emo = build_emotion_bars(radar_df)
                st.plotly_chart(fig_emo, use_container_width=True)

            # Detailed table breakdown
            st.markdown("##### Mean Density Breakdown Table (Tokens per 1,000 Words)")
            disp_cols = ["language", "moral_density", "care_density", "fairness_density", "loyalty_density", "authority_density", "sanctity_density", "net_sentiment"]
            st.dataframe(radar_df[disp_cols].round(2), use_container_width=True)

    # -------------------------------------------------------------
    # TAB 3: Temporal Trends
    # -------------------------------------------------------------
    with tab3:
        st.subheader("Longitudinal Discourse Dynamics (2017–2026)")
        col_t1, col_t2 = st.columns([1, 3])
        with col_t1:
            metric_choice = st.radio(
                "Trend Metric",
                options=["avg_sentiment", "avg_moral_density", "article_count"],
                format_func=lambda m: {
                    "avg_sentiment": "Net Sentiment Valence",
                    "avg_moral_density": "Moral Framing Density",
                    "article_count": "Article Coverage Volume"
                }.get(m, m)
            )

        timeline_df = service.get_timeline_data(
            query=filters["query"],
            sources=filters["sources"],
            languages=filters["languages"],
            freq="M"
        )

        with col_t2:
            fig_timeline = build_timeline_chart(timeline_df, metric=metric_choice)
            st.plotly_chart(fig_timeline, use_container_width=True)

    # -------------------------------------------------------------
    # TAB 4: Focus Events & Meaning-Making
    # -------------------------------------------------------------
    with tab4:
        st.subheader("Event-Driven Meaning-Making & Discursive Shifts")
        st.caption("Operationalizes Hurtado-Bodell & Menshikova (2026): tracking how critical focal events reshape public discourse and moral framing.")

        events = service.get_focus_events()
        event_options = list(events.keys())

        col_ev1, col_ev2 = st.columns([2, 1])
        with col_ev1:
            selected_event_key = st.selectbox(
                "Select Regional Focus Event",
                options=event_options,
                format_func=lambda d: f"{d} — {events[d]['title']} ({events[d]['category'].capitalize()})"
            )
        with col_ev2:
            default_win = events[selected_event_key].get("default_window", 30)
            window_days = st.slider("Window Size (± Days)", min_value=15, max_value=90, value=default_win, step=15)

        event_info = events[selected_event_key]
        st.info(f"**Context ({selected_event_key}):** {event_info['description']}")

        # Compute Event Analysis
        analysis = service.analyze_focus_event(
            event_date_str=selected_event_key,
            window_days=window_days,
            query=filters["query"]
        )

        # KPI Row for Event Impact
        k1, k2, k3, k4 = st.columns(4)
        k1.metric(
            "Pre-Event Articles",
            f"{analysis['pre_count']}",
            help=f"Coverage within {analysis['pre_period']}"
        )
        k2.metric(
            "Post-Event Articles",
            f"{analysis['post_count']}",
            delta=f"{analysis['pct_surge']:+.1f}% volume",
            help=f"Coverage within {analysis['post_period']}"
        )
        k3.metric(
            "Sentiment Shift",
            f"{analysis['post_sentiment']:+.2f}",
            delta=f"{analysis['delta_sentiment']:+.2f} Δ",
            help="Net sentiment polarity shift following the focus event"
        )
        jsd_val = analysis["moral_divergence"]["jsd"]
        k4.metric(
            "Moral Divergence (JSD)",
            f"{jsd_val:.4f}",
            delta=f"Main: {analysis['moral_divergence']['primary_divergence_foundation'].capitalize()}",
            delta_color="inverse",
            help="Jensen-Shannon Divergence of 5-foundation moral vector pre vs post event"
        )

        st.markdown("---")

        # Two-column visual layout
        col_m_gauge, col_keyness = st.columns([1, 1])

        with col_m_gauge:
            st.markdown("##### 1. Moral Framing Reconfiguration (Pre vs Post)")
            fig_pre_post = build_pre_post_moral_comparison(
                analysis["pre_moral"],
                analysis["post_moral"],
                event_title=event_info["title"]
            )
            st.plotly_chart(fig_pre_post, use_container_width=True)

            fig_jsd = build_moral_divergence_gauge(
                jsd_val,
                title="Temporal Moral Shift (Pre/Post JSD)"
            )
            st.plotly_chart(fig_jsd, use_container_width=True)

        with col_keyness:
            st.markdown("##### 2. Differential Emerging Vocabulary (Dunning G²)")
            if not analysis["keyness_df"].empty:
                fig_key = build_keyness_bar_chart(
                    analysis["keyness_df"],
                    target_label="Post-Event Discourse",
                    ref_label="Pre-Event Discourse"
                )
                st.plotly_chart(fig_key, use_container_width=True)
            else:
                st.warning("Insufficient vocabulary frequency to calculate statistically significant keyness.")

        st.markdown("---")

        # Cross-Lingual Moral Divergence Summary for Active Topic Filter
        st.subheader("Cross-Lingual Moral Gap on Current Filter")
        st.caption("Pairwise Jensen-Shannon Divergence across German, Italian, and Ladin communities.")

        pair_div = service.compute_cross_lingual_moral_divergence(
            query=filters["query"],
            sources=filters["sources"]
        )

        if pair_div:
            p_cols = st.columns(len(pair_div))
            for idx, (pair_name, p_data) in enumerate(pair_div.items()):
                with p_cols[idx]:
                    fig_p = build_moral_divergence_gauge(
                        p_data["jsd"],
                        title=f"{pair_name.replace('_', ' ')}"
                    )
                    st.plotly_chart(fig_p, use_container_width=True)
                    st.caption(f"**Key Divergence:** `{p_data['primary_divergence_foundation'].capitalize()}`")

    # -------------------------------------------------------------
    # TAB 5: Article Deep Dive
    # -------------------------------------------------------------
    with tab5:
        st.subheader("Single-Article Qualitative Deep Dive")
        art_id_input = st.text_input("Enter Article ID to inspect:", value="lausc_1" if not articles else articles[0]["id"])

        if art_id_input:
            art_data = service.get_article_by_id(art_id_input.strip())
            if not art_data:
                st.error(f"Article ID '{art_id_input}' not found in database.")
            else:
                col_meta, col_body = st.columns([1, 2])

                with col_meta:
                    st.markdown("#### Metadata & NLP Scores")
                    st.write(f"**Source:** {SOURCE_LABELS.get(art_data['source'], art_data['source'])}")
                    st.write(f"**Variety:** `{art_data['language']}`")
                    st.write(f"**Author:** {art_data.get('author') or 'Redaktion'}")
                    st.write(f"**Date:** {art_data['publish_date'][:10]}")
                    st.write(f"**Word Count:** {art_data['word_count']}")
                    st.write(f"**TTR:** {art_data.get('ttr', 0.0):.3f}")
                    st.write(f"**Mean Sentence Length:** {art_data.get('mean_sentence_length', 0.0):.1f}")
                    st.write(f"**Net Sentiment:** {art_data.get('net_sentiment', 0.0):+.2f}")
                    st.write(f"**Moral Density:** {art_data.get('moral_density', 0.0):.1f} / 1k")

                    with st.expander("Full JSON Metadata"):
                        st.json(art_data.get("metadata", {}))

                with col_body:
                    st.markdown(f"### {art_data['title']}")
                    st.markdown(f"[Original Link ↗]({art_data['url']})")
                    st.markdown("---")
                    paragraphs = art_data.get("full_text", "").split("\n\n")
                    for p in paragraphs:
                        if p.strip():
                            st.write(p.strip())


if __name__ == "__main__":
    main()

