"""
Interactive Plotly Visualizations for DIDI Research Workbench.
Includes Moral Foundations Radar, Emotion Polar/Bar distribution,
and Temporal Framing Trends.
"""

from typing import Dict, List, Optional
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

LANG_COLORS = {
    "de": "#1f77b4",          # Academic Steel Blue
    "it": "#2ca02c",          # Forest Green
    "lld_gherd": "#ff7f0e",   # Dolomite Terracotta
    "lld_badia": "#d62728",   # Crimson
    "lld_fascia": "#9467bd"   # Purple
}

FOUNDATION_LABELS = {
    "care_density": "Care",
    "fairness_density": "Fairness",
    "loyalty_density": "Loyalty",
    "authority_density": "Authority",
    "sanctity_density": "Sanctity"
}

EMOTION_LABELS = {
    "anger_density": "Anger",
    "anticipation_density": "Anticipation",
    "disgust_density": "Disgust",
    "fear_density": "Fear",
    "joy_density": "Joy",
    "sadness_density": "Sadness",
    "surprise_density": "Surprise",
    "trust_density": "Trust"
}


def build_moral_radar(grouped_df: pd.DataFrame) -> go.Figure:
    """
    Build a 5-axis Moral Foundations radar chart with polygon overlays per language.
    """
    fig = go.Figure()

    categories = ["Care", "Fairness", "Loyalty", "Authority", "Sanctity"]
    cols = ["care_density", "fairness_density", "loyalty_density", "authority_density", "sanctity_density"]

    if grouped_df.empty:
        fig.add_annotation(text="No data matching current filters", showarrow=False, font=dict(size=14))
        return fig

    for _, row in grouped_df.iterrows():
        lang = row["language"]
        color = LANG_COLORS.get(lang, "#636efa")
        values = [row[c] for c in cols]
        # Close the loop
        values += [values[0]]
        cat_closed = categories + [categories[0]]

        fig.add_trace(go.Scatterpolar(
            r=values,
            theta=cat_closed,
            fill='toself',
            name=lang.upper(),
            line=dict(color=color, width=2),
            opacity=0.65
        ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, max(5.0, grouped_df[cols].max().max() * 1.15)]
            )
        ),
        showlegend=True,
        title=dict(text="<b>Moral Foundations Framing Radar (Density per 1k Words)</b>", font=dict(size=16)),
        margin=dict(l=40, r=40, t=50, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5)
    )
    return fig


def build_emotion_bars(grouped_df: pd.DataFrame) -> go.Figure:
    """
    Build grouped horizontal or vertical bar chart comparing Plutchik's 8 emotions.
    """
    if grouped_df.empty:
        fig = go.Figure()
        fig.add_annotation(text="No data matching current filters", showarrow=False)
        return fig

    records = []
    for _, row in grouped_df.iterrows():
        lang = row["language"]
        for col, emo in EMOTION_LABELS.items():
            records.append({
                "Language": lang,
                "Emotion": emo,
                "Density": row[col]
            })

    df_emo = pd.DataFrame(records)
    fig = px.bar(
        df_emo,
        x="Emotion",
        y="Density",
        color="Language",
        barmode="group",
        color_discrete_map=LANG_COLORS,
        title="<b>Plutchik Discrete Emotion Distributions (Per 1k Words)</b>",
        labels={"Density": "Tokens / 1,000 words"}
    )
    fig.update_layout(
        margin=dict(l=40, r=40, t=50, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5)
    )
    return fig


def build_timeline_chart(timeline_df: pd.DataFrame, metric: str = "avg_sentiment") -> go.Figure:
    """
    Build interactive line chart tracking longitudinal evolution of sentiment or moral density.
    """
    if timeline_df.empty:
        fig = go.Figure()
        fig.add_annotation(text="No temporal data matching current filters", showarrow=False)
        return fig

    y_label = "Net Sentiment Polarity (-1 to +1)" if metric == "avg_sentiment" else "Moral Density (Tokens / 1k Words)"
    title_text = "<b>Longitudinal Net Sentiment Evolution (2017–2026)</b>" if metric == "avg_sentiment" else "<b>Longitudinal Moral Framing Density (2017–2026)</b>"

    fig = px.line(
        timeline_df,
        x="period",
        y=metric,
        color="language",
        color_discrete_map=LANG_COLORS,
        markers=True,
        title=title_text,
        labels={"period": "Date", metric: y_label}
    )

    if metric == "avg_sentiment":
        # Add neutral baseline reference line
        fig.add_hline(y=0.0, line_dash="dash", line_color="gray", annotation_text="Neutral", opacity=0.7)

    fig.update_layout(
        xaxis=dict(showgrid=True),
        yaxis=dict(showgrid=True),
        margin=dict(l=40, r=40, t=50, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5)
    )
    return fig

