"""
DIDI Platform — Research Workbench Web Application.
Mixed-Methods Media Analysis for Eurac Research and University of Innsbruck.
"""

import html
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
    build_moral_radar, build_emotion_bars, build_timeline_chart
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


@st.cache_resource
def get_service() -> DataService:
    return DataService()


def render_sidebar(service: DataService):
    st.sidebar.title("🔍 Corpus Filters")

    # 1. Topic Query
    query = st.sidebar.text_input(
        "FTS5 Topic Search",
        value="",
        placeholder="e.g. Autonomie, scuola, turism...",
        help="Search query executed via SQLite FTS5 index across German, Italian, and Ladin."
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
        "min_moral": min_moral
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

    # 4 Core Views
    tab1, tab2, tab3, tab4 = st.tabs([
        "📄 1. Corpus Explorer & Snippets",
        "🕸️ 2. Comparative Framing Radar",
        "📈 3. Temporal Discourse Dynamics",
        "🔎 4. Article Deep Dive"
    ])

    # -------------------------------------------------------------
    # TAB 1: Corpus Explorer
    # -------------------------------------------------------------
    with tab1:
        st.subheader("Cross-Lingual Search & Qualitative Text Snippets")
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
            limit=page_size,
            offset=0
        )

        st.write(f"Found **{total_matches:,}** matching articles.")

        if not articles:
            st.info("No articles match the current combination of filters. Try broadening your search or resetting sliders.")
        else:
            for art in articles:
                lang = art["language"]
                badge_class = "badge-de" if lang == "de" else ("badge-it" if lang == "it" else "badge-lld")
                s_val = art.get("net_sentiment", 0.0)
                sent_color = "#27ae60" if s_val > 0.1 else ("#c0392b" if s_val < -0.1 else "#7f8c8d")

                st.markdown(f"""
                <div class="article-card">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                        <div>
                            <span class="metric-badge {badge_class}">{lang.upper()}</span>
                            <span class="metric-badge" style="background:#edf2f7; color:#2d3748;">{SOURCE_LABELS.get(art['source'], art['source'])}</span>
                            <span style="font-size:0.8rem; color:#718096;">{art['publish_date'][:10]}</span>
                        </div>
                        <div>
                            <span style="font-size:0.8rem; font-weight:600; color:{sent_color}; margin-right:12px;">Valence: {s_val:+.2f}</span>
                            <span style="font-size:0.8rem; color:#4a5568;">Tokens: {art['word_count']}</span>
                        </div>
                    </div>
                    <h4 style="margin:0 0 8px 0; color:#1a202c;">{art['title']}</h4>
                    <p style="font-size:0.92rem; color:#4a5568; line-height:1.5; margin-bottom:10px;">
                        {art['snippet']}
                    </p>
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <span style="font-size:0.78rem; color:#a0aec0;">ID: {art['id']} | Category: {art.get('category') or 'N/A'}</span>
                        <a href="{art['url']}" target="_blank" style="font-size:0.8rem; color:#3182ce; text-decoration:none;">Original Article ↗</a>
                    </div>
                </div>
                """, unsafe_allow_html=True)

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
    # TAB 4: Article Deep Dive
    # -------------------------------------------------------------
    with tab4:
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

