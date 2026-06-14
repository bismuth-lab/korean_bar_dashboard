from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import plotly.graph_objects as go


def github_heatmap(day_scores: pd.DataFrame, start: date | None = None, end: date | None = None) -> go.Figure:
    end = end or date.today()
    start = start or (end - timedelta(days=365))
    start = start - timedelta(days=start.weekday())
    end = end + timedelta(days=6 - end.weekday())

    score_by_date = {}
    if not day_scores.empty:
        score_by_date = {r["date"]: float(r["day_score"]) for _, r in day_scores.iterrows()}

    days = []
    d = start
    while d <= end:
        days.append(d)
        d += timedelta(days=1)
    week_index = [(d - start).days // 7 for d in days]
    weekday = [d.weekday() for d in days]
    values = [score_by_date.get(d, None) for d in days]
    hover = [f"{d.isoformat()}<br>합격기여점수: {score_by_date.get(d, 0):.0f}" for d in days]

    df = pd.DataFrame({"week": week_index, "weekday": weekday, "score": values, "hover": hover})
    pivot = df.pivot(index="weekday", columns="week", values="score")
    text = df.pivot(index="weekday", columns="week", values="hover")

    fig = go.Figure(
        data=go.Heatmap(
            z=pivot.values,
            x=pivot.columns,
            y=["월", "화", "수", "목", "금", "토", "일"],
            text=text.values,
            hoverinfo="text",
            colorscale=[
                [0.0, "#ebedf0"],
                [0.25, "#c6e48b"],
                [0.5, "#7bc96f"],
                [0.75, "#239a3b"],
                [1.0, "#196127"],
            ],
            zmin=0,
            zmax=100,
            xgap=3,
            ygap=3,
            showscale=False,
        )
    )
    fig.update_layout(
        height=230,
        margin=dict(l=10, r=10, t=10, b=10),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
        yaxis=dict(showgrid=False, autorange="reversed", zeroline=False),
    )
    return fig
