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


def build_keyness_bar_chart(
    keyness_df: pd.DataFrame,
    target_label: str = "Target Corpus",
    ref_label: str = "Reference Corpus"
) -> go.Figure:
    """
    Build horizontal divergent bar chart of Dunning's G² keyness statistics.
    """
    if keyness_df.empty:
        fig = go.Figure()
        fig.add_annotation(text="Insufficient word frequencies to compute keyness", showarrow=False)
        return fig

    # Sort so top terms appear cleanly on y-axis
    df = keyness_df.sort_values(by="g2", ascending=True)

    colors = ["#2b6cb0" if val > 0 else "#c53030" for val in df["g2"]]

    fig = go.Figure(go.Bar(
        x=df["g2"],
        y=df["term"],
        orientation='h',
        marker_color=colors,
        text=[f"{abs(val):.1f} (G²)" for val in df["g2"]],
        textposition="outside",
        hovertemplate="<b>%{y}</b><br>G²: %{x:.2f}<br>Target rate: %{customdata[0]}/1k<br>Ref rate: %{customdata[1]}/1k<extra></extra>",
        customdata=df[["target_per_1k", "ref_per_1k"]].values
    ))

    fig.update_layout(
        title=dict(
            text=f"<b>Differential Keyness (Dunning G²)</b><br><sub>Blue: Overused in {target_label} | Red: Overused in {ref_label}</sub>",
            font=dict(size=14)
        ),
        xaxis=dict(title="Dunning G² (Signed by Direction)", zeroline=True, zerolinecolor="#4a5568"),
        yaxis=dict(title="", tickfont=dict(size=11)),
        margin=dict(l=70, r=40, t=60, b=40),
        height=max(400, len(df) * 22)
    )
    return fig


def build_moral_divergence_gauge(jsd_value: float, title: str = "Moral Framing Divergence (JSD)") -> go.Figure:
    """
    Indicator gauge for Jensen-Shannon Moral Divergence (0.0 = Consensual, 1.0 = Polarized).
    """
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=jsd_value,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': f"<b>{title}</b>", 'font': {'size': 14}},
        gauge={
            'axis': {'range': [0, 1.0], 'tickwidth': 1, 'tickcolor': "darkblue"},
            'bar': {'color': "#1a365d", 'thickness': 0.25},
            'bgcolor': "white",
            'borderwidth': 2,
            'bordercolor': "gray",
            'steps': [
                {'range': [0.0, 0.10], 'color': '#c6f6d5'},  # High alignment
                {'range': [0.10, 0.25], 'color': '#feebc8'},  # Moderate gap
                {'range': [0.25, 1.0], 'color': '#fed7d7'}   # Polarized framing
            ],
            'threshold': {
                'line': {'color': "red", 'width': 3},
                'thickness': 0.75,
                'value': 0.25
            }
        }
    ))
    fig.update_layout(height=240, margin=dict(l=30, r=30, t=50, b=20))
    return fig


def build_pre_post_moral_comparison(
    pre_moral: Dict[str, float],
    post_moral: Dict[str, float],
    event_title: str = "Focus Event"
) -> go.Figure:
    """
    Grouped bar chart comparing Moral Foundation densities Pre vs Post Focus Event.
    """
    foundations = ["Care", "Fairness", "Loyalty", "Authority", "Sanctity"]
    keys = ["care", "fairness", "loyalty", "authority", "sanctity"]

    pre_vals = [pre_moral.get(k, 0.0) for k in keys]
    post_vals = [post_moral.get(k, 0.0) for k in keys]

    fig = go.Figure(data=[
        go.Bar(name='Pre-Event Window', x=foundations, y=pre_vals, marker_color='#4a5568'),
        go.Bar(name='Post-Event Window', x=foundations, y=post_vals, marker_color='#dd6b20')
    ])

    fig.update_layout(
        barmode='group',
        title=dict(text=f"<b>Moral Framing Reconfiguration: {event_title}</b>", font=dict(size=14)),
        yaxis=dict(title="Density (Tokens / 1k Words)"),
        margin=dict(l=40, r=40, t=50, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5)
    )
    return fig

