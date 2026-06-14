from __future__ import annotations

import math
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd

OUTPUT_WEIGHTS = {
    "사례답안": 18,
    "CBT답안": 18,
    "사례목차": 10,
    "기록형": 24,
    "기록형목차": 12,
    "선택형": 0,  # 선택형은 attempted/correct로 별도 계산
    "오답복기": 8,
    "암기재현": 6,
    "판례문장": 4,
    "재풀이": 6,
    "기타": 4,
}

HEAVY_OUTPUTS = {"사례답안", "CBT답안", "기록형"}
REVIEW_OUTPUTS = {"오답복기", "암기재현", "판례문장", "재풀이"}


def parse_time_minutes(start: str | None, end: str | None) -> int:
    if not start or not end:
        return 0
    try:
        s = datetime.strptime(start, "%H:%M")
        e = datetime.strptime(end, "%H:%M")
        if e < s:
            e += timedelta(days=1)
        return int((e - s).total_seconds() // 60)
    except Exception:
        return 0


def _study_points(minutes: int) -> int:
    if minutes >= 480:
        return 36
    if minutes >= 360:
        return 30
    if minutes >= 240:
        return 26
    if minutes >= 200:
        return 22
    if minutes >= 180:
        return 18
    if minutes >= 120:
        return 12
    if minutes > 0:
        return 5
    return 0


def _attendance_points(minutes: int) -> int:
    if minutes >= 480:
        return 12
    if minutes >= 360:
        return 9
    if minutes >= 180:
        return 6
    if minutes > 0:
        return 3
    return 0


def compute_day_scores(daily: pd.DataFrame, outputs: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "date",
        "day_score",
        "attendance_min",
        "self_study_min",
        "effective_study_min",
        "output_points",
        "review_points",
        "mcq_attempted",
        "mcq_correct",
        "mcq_accuracy",
        "heavy_outputs",
        "lecture_min",
        "cbt_practice_min",
        "avoidance_count",
        "completed_first",
    ]
    if daily.empty:
        return pd.DataFrame(columns=columns)

    rows: list[dict[str, object]] = []
    out_by_date = outputs.groupby("date") if not outputs.empty else {}
    for _, row in daily.iterrows():
        d = row["date"]
        odf = out_by_date.get_group(d) if not outputs.empty and d in out_by_date.groups else pd.DataFrame()
        attendance_min = parse_time_minutes(row.get("checkin"), row.get("checkout"))
        lecture_min = int(row.get("lecture_min") or 0)
        self_study_min = int(row.get("self_study_min") or 0)
        cbt_practice_min = int(row.get("cbt_practice_min") or 0)
        study_blocks = int(row.get("study_blocks") or 0)
        block_estimated_min = study_blocks * 25

        # 집중블록은 자습시간과 같은 행동이므로, 자습시간이 비어 있을 때만 시간 대체값으로 쓴다.
        if self_study_min > 0:
            effective_study_min = self_study_min
        elif block_estimated_min > 0:
            effective_study_min = block_estimated_min
        else:
            effective_study_min = attendance_min

        output_points = 0
        heavy_count = 0
        attempted = 0
        correct = 0
        review_points = 0
        if not odf.empty:
            for _, out in odf.iterrows():
                typ = out.get("output_type", "기타")
                qty = int(out.get("quantity") or 1)
                attempted += int(out.get("attempted") or 0)
                correct += int(out.get("correct") or 0)
                if typ in HEAVY_OUTPUTS:
                    heavy_count += qty
                if typ in REVIEW_OUTPUTS:
                    review_points += min(20, OUTPUT_WEIGHTS.get(typ, 4) * qty)
                else:
                    output_points += OUTPUT_WEIGHTS.get(typ, 4) * qty
            output_points += min(20, attempted // 10)

        first_task_points = 8 if int(row.get("completed_first") or 0) else 0
        block_points = 0
        exercise_points = 4 if int(row.get("exercise_min") or 0) >= 15 else 0
        cbt_points = 4 if cbt_practice_min >= 30 else 0
        avoidance = row.get("avoidance") or []
        penalty = min(25, len(avoidance) * 5)
        if lecture_min >= 240 and heavy_count == 0 and attempted < 30:
            penalty += 10
        if attendance_min >= 360 and output_points < 10 and attempted < 30:
            penalty += 6

        raw = (
            _attendance_points(attendance_min)
            + _study_points(effective_study_min)
            + min(output_points, 36)
            + min(review_points, 18)
            + first_task_points
            + block_points
            + exercise_points
            + cbt_points
            - penalty
        )
        day_score = max(0, min(100, raw))
        mcq_accuracy = correct / attempted if attempted else np.nan
        rows.append(
            {
                "date": d,
                "day_score": day_score,
                "attendance_min": attendance_min,
                "self_study_min": self_study_min,
                "effective_study_min": effective_study_min,
                "output_points": min(output_points, 36),
                "review_points": min(review_points, 18),
                "mcq_attempted": attempted,
                "mcq_correct": correct,
                "mcq_accuracy": mcq_accuracy,
                "heavy_outputs": heavy_count,
                "lecture_min": lecture_min,
                "cbt_practice_min": cbt_practice_min,
                "avoidance_count": len(avoidance),
                "completed_first": int(row.get("completed_first") or 0),
            }
        )
    return pd.DataFrame(rows, columns=columns)


def current_streak(day_scores: pd.DataFrame, threshold: int = 35) -> int:
    if day_scores.empty:
        return 0
    df = day_scores.sort_values("date")
    streak = 0
    today = date.today()
    by_date = {r["date"]: r["day_score"] for _, r in df.iterrows()}
    d = today
    if d not in by_date:
        d -= timedelta(days=1)
    while by_date.get(d, 0) >= threshold:
        streak += 1
        d -= timedelta(days=1)
    return streak


def weekly_summary(day_scores: pd.DataFrame, outputs: pd.DataFrame) -> dict[str, float]:
    today = date.today()
    start = today - timedelta(days=today.weekday())
    ds = day_scores[(day_scores["date"] >= start) & (day_scores["date"] <= today)] if not day_scores.empty else pd.DataFrame()
    outs = outputs[(outputs["date"] >= start) & (outputs["date"] <= today)] if not outputs.empty else pd.DataFrame()
    first_rate = float(ds["completed_first"].mean()) if not ds.empty else 0.0
    return {
        "avg_score": float(ds["day_score"].mean()) if not ds.empty else 0.0,
        "output_qty": int(outs["quantity"].sum()) if not outs.empty else 0,
        "mcq_attempted": int(ds["mcq_attempted"].sum()) if not ds.empty else 0,
        "mcq_correct": int(ds["mcq_correct"].sum()) if not ds.empty else 0,
        "heavy_outputs": int(ds["heavy_outputs"].sum()) if not ds.empty else 0,
        "attendance_hours": round(float(ds["attendance_min"].sum()) / 60, 1) if not ds.empty else 0.0,
        "self_study_hours": round(float(ds["effective_study_min"].sum()) / 60, 1) if not ds.empty else 0.0,
        "lecture_hours": round(float(ds["lecture_min"].sum()) / 60, 1) if not ds.empty else 0.0,
        "cbt_hours": round(float(ds["cbt_practice_min"].sum()) / 60, 1) if not ds.empty else 0.0,
        "first_task_rate": first_rate,
    }


def safe_probability(p: float) -> float:
    return float(min(0.97, max(0.03, p)))


def logit(p: float) -> float:
    p = min(0.99, max(0.01, p))
    return math.log(p / (1 - p))


def inv_logit(x: float) -> float:
    return 1 / (1 + math.exp(-x))


def probability_after_lr(prior: float, lr: float) -> float:
    return safe_probability(inv_logit(logit(prior) + math.log(lr)))


def day_likelihood_ratio(score: float, heavy_outputs: int, mcq_attempted: int) -> float:
    # 게임감각: 하루 행동은 작게, 모의고사는 크게. 매일 0.05~0.35%p 정도만 움직이게 설계한다.
    if score >= 80 and (heavy_outputs >= 1 or mcq_attempted >= 60):
        return 1.015
    if score >= 65:
        return 1.010
    if score >= 35:
        return 1.003
    if score > 0:
        return 0.993
    return 0.985


def mock_likelihood_ratio(row: pd.Series) -> float:
    lr = 1.0
    top = row.get("top_percent")
    if pd.notna(top):
        top = float(top)
        if top <= 20:
            lr *= 4.5
        elif top <= 35:
            lr *= 3.0
        elif top <= 50:
            lr *= 1.8
        elif top <= 65:
            lr *= 1.1
        elif top <= 80:
            lr *= 0.65
        else:
            lr *= 0.35

    total = row.get("total_score")
    cut = row.get("pass_cut")
    if pd.notna(total) and pd.notna(cut) and cut:
        margin = float(total) - float(cut)
        lr *= math.exp(max(-1.4, min(1.4, margin / 120)))

    round_no = int(row.get("round_no") or 0)
    name = str(row.get("mock_name") or "")
    if "7월" in name or "7" in name or "진단" in name:
        weight = 0.6
    elif round_no == 3 or "10" in name or "3차" in name:
        weight = 1.6
    elif round_no == 2 or "8" in name or "2차" in name:
        weight = 1.2
    elif round_no == 1 or "6" in name or "1차" in name:
        weight = 0.8
    else:
        weight = 1.0
    return max(0.15, min(8.0, lr**weight))


def estimate_probability(prior: float, day_scores: pd.DataFrame, mocks: pd.DataFrame) -> tuple[float, list[dict[str, float | str]]]:
    x = logit(prior)
    updates: list[dict[str, float | str]] = []

    if not day_scores.empty:
        recent = day_scores.sort_values("date").tail(180)
        base = x
        for _, r in recent.iterrows():
            lr = day_likelihood_ratio(float(r["day_score"]), int(r.get("heavy_outputs") or 0), int(r.get("mcq_attempted") or 0))
            x += math.log(lr)
        updates.append({"source": "최근 180개 기록일의 루틴/출력", "lr": round(math.exp(x - base), 3), "kind": "daily"})

    if not mocks.empty:
        for _, row in mocks.iterrows():
            lr = mock_likelihood_ratio(row)
            x += math.log(lr)
            updates.append({"source": str(row.get("mock_name")), "lr": round(lr, 3), "kind": "mock"})

    return safe_probability(inv_logit(x)), updates


def build_risk_flags(day_scores: pd.DataFrame, outputs: pd.DataFrame, daily: pd.DataFrame) -> list[str]:
    flags: list[str] = []
    if day_scores.empty:
        return ["아직 기록이 없습니다. 오늘 최소 루틴부터 입력하세요."]
    last14 = day_scores.sort_values("date").tail(14)
    if last14["heavy_outputs"].sum() < 4:
        flags.append("최근 2주간 사례답안/기록형 출력이 부족합니다. 인풋보다 출력 블록을 먼저 배치하세요.")
    if last14["mcq_attempted"].sum() < 200:
        flags.append("최근 2주 선택형 풀이량이 낮습니다. 매일 20~40문제라도 하방을 막으세요.")
    if last14["lecture_min"].sum() >= 900 and last14["heavy_outputs"].sum() < 6:
        flags.append("강의 시간이 많은데 답안 출력이 부족합니다. 강의 1개당 문제/목차 1개 원칙을 적용하세요.")
    if last14["attendance_min"].sum() >= 3600 and last14["output_points"].sum() < 60:
        flags.append("자습실 체류는 충분한데 출력점수가 낮습니다. 오래 앉아 있는 것보다 답안/오답 사진을 남기세요.")
    if len(last14) >= 5 and last14["completed_first"].mean() < 0.45:
        flags.append("첫 과제 완료율이 낮습니다. 전날 밤에 다음 날 1교시 과제를 하나로 잠그세요.")
    if not daily.empty:
        recent_avoid = sum(len(x or []) for x in daily.sort_values("date").tail(14)["avoidance"])
        if recent_avoid >= 6:
            flags.append("회피행동 태그가 반복됩니다. 자료쇼핑/계획리셋 대신 최소 루틴으로 복귀하세요.")
    if not outputs.empty:
        recent_start = date.today() - timedelta(days=13)
        recent_outs = outputs[outputs["date"] >= recent_start]
        if not recent_outs.empty:
            subject_counts = recent_outs.groupby("subject")["quantity"].sum()
            for required in ["민사법", "형사법", "공법"]:
                if subject_counts.get(required, 0) == 0:
                    flags.append(f"최근 2주 {required} 출력이 0입니다. 싫은 과목을 첫 블록에 넣으세요.")
    if not flags:
        flags.append("큰 위험 신호는 없습니다. 다음 목표는 루틴 유지가 아니라 출력 난도를 조금 올리는 것입니다.")
    return flags
