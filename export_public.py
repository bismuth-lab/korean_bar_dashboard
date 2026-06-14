from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from barpassos.db import get_settings, init_db, load_daily, load_outputs
from barpassos.metrics import compute_day_scores


PUBLIC_DIR = Path("public")

JA_TEXT = {
    "기록 대기": "記録待ち",
    "기록 완료": "記録完了",
    "7월 학교/학원 모의고사": "7月 学内・予備校模試",
    "10월 법전협/실전 모의고사": "10月 実戦模試",
    "2028 변호사시험": "2028年 韓国弁護士試験",
    "정확한 장소와 답안 내용은 비공개이며, 매일의 루틴과 출력량만 기록합니다.": "正確な場所と答案の内容は非公開にし、毎日のルーティンとアウトプット量だけを記録します。",
    "공개 가능한 기록이 아직 없습니다.": "公開できる記録はまだありません。",
    "큰 위험 신호는 없습니다.": "大きなリスクサインはありません。",
}


def _setting_date(settings: dict[str, str], key: str, fallback: str) -> date:
    raw = settings.get(key, fallback)
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return datetime.strptime(fallback, "%Y-%m-%d").date()


def _d_day(target: date) -> str:
    days = (target - date.today()).days
    if days > 0:
        return f"D-{days}"
    if days == 0:
        return "D-Day"
    return f"D+{abs(days)}"


def _next_exam(settings: dict[str, str]) -> dict[str, Any]:
    milestones = [
        {"name": "7월 학교/학원 모의고사", "date": _setting_date(settings, "mock_july_date", "2027-07-15")},
        {"name": "10월 법전협/실전 모의고사", "date": _setting_date(settings, "mock_october_date", "2027-10-15")},
        {"name": "2028 변호사시험", "date": _setting_date(settings, "exam_date", "2028-01-11")},
    ]
    future = [m for m in milestones if m["date"] >= date.today()]
    return min(future, key=lambda m: m["date"]) if future else milestones[-1]


def _num(value: Any, default: float = 0.0) -> float:
    if value is None or pd.isna(value):
        return default
    return float(value)


def _int_num(value: Any, default: int = 0) -> int:
    return int(_num(value, float(default)))


def public_log_frame(
    daily: pd.DataFrame,
    outputs: pd.DataFrame,
    day_scores: pd.DataFrame,
    delay_hours: int,
    include_evidence_hash: bool,
) -> pd.DataFrame:
    columns = [
        "date",
        "checkin",
        "checkout",
        "seat_hours",
        "self_study_hours",
        "lecture_hours",
        "cbt_hours",
        "outputs_count",
        "mcq_count",
        "first_task_done",
        "score",
        "edited",
        "late_entry",
    ]
    if include_evidence_hash:
        columns.append("evidence_hash")
    if daily.empty or day_scores.empty:
        return pd.DataFrame(columns=columns)

    cutoff = (datetime.now() - timedelta(hours=delay_hours)).date()
    visible_scores = day_scores[day_scores["date"] <= cutoff].copy()
    if visible_scores.empty:
        return pd.DataFrame(columns=columns)

    meta = daily[["date", "checkin", "checkout", "edited", "late_entry"]].copy()
    public_df = visible_scores.merge(meta, on="date", how="left")

    if outputs.empty:
        out_qty = pd.DataFrame(columns=["date", "outputs_count", "evidence_hash"])
    else:
        out_qty = outputs[outputs["date"] <= cutoff].groupby("date", as_index=False)["quantity"].sum()
        out_qty = out_qty.rename(columns={"quantity": "outputs_count"})
        if include_evidence_hash and "evidence_hash" in outputs.columns:
            hashes = (
                outputs[(outputs["date"] <= cutoff) & (outputs["evidence_hash"].fillna("") != "")]
                .groupby("date")["evidence_hash"]
                .apply(lambda x: ",".join(sorted(set(x))))
                .reset_index()
            )
            out_qty = out_qty.merge(hashes, on="date", how="left")
    public_df = public_df.merge(out_qty, on="date", how="left")

    rows = []
    for _, row in public_df.sort_values("date").iterrows():
        item = {
            "date": row["date"].isoformat(),
            "checkin": row.get("checkin") or "",
            "checkout": row.get("checkout") or "",
            "seat_hours": round(_num(row.get("attendance_min")) / 60, 2),
            "self_study_hours": round(_num(row.get("effective_study_min")) / 60, 2),
            "lecture_hours": round(_num(row.get("lecture_min")) / 60, 2),
            "cbt_hours": round(_num(row.get("cbt_practice_min")) / 60, 2),
            "outputs_count": _int_num(row.get("outputs_count")),
            "mcq_count": _int_num(row.get("mcq_attempted")),
            "first_task_done": bool(row.get("completed_first")),
            "score": _int_num(row.get("day_score")),
            "edited": bool(row.get("edited") or 0),
            "late_entry": bool(row.get("late_entry") or 0),
        }
        if include_evidence_hash:
            item["evidence_hash"] = row.get("evidence_hash") or ""
        rows.append(item)
    return pd.DataFrame(rows, columns=columns)


def public_risk_signals(public_df: pd.DataFrame, outputs: pd.DataFrame) -> list[str]:
    if public_df.empty:
        return ["공개 가능한 기록이 아직 없습니다."]
    risks: list[str] = []
    recent7 = public_df.tail(7)
    zero_outputs = int((recent7["outputs_count"] == 0).sum())
    risks.append(f"최근 7일 중 출력 없는 날: {zero_outputs}일")
    if zero_outputs >= 2:
        risks.append("출력 공백 주의: 강의/정리보다 사례·기록·오답 산출물을 먼저 배치하세요.")

    recent14_start = date.today() - timedelta(days=13)
    if not outputs.empty:
        recent_outputs = outputs[outputs["date"] >= recent14_start]
        public_law = recent_outputs[recent_outputs["subject"].astype(str).str.contains("공법", na=False)]
        if public_law.empty:
            risks.append("최근 14일 공법 출력 공백: 14일")
        else:
            last_public_law = max(public_law["date"])
            risks.append(f"최근 14일 공법 출력 공백: {(date.today() - last_public_law).days}일")

    recent = public_df.tail(7)
    lecture_hours = float(recent["lecture_hours"].sum())
    output_count = int(recent["outputs_count"].sum())
    if lecture_hours >= 8 and output_count < 4:
        risks.append("강의시간 대비 출력 부족: 주의")
    if len(risks) == 1:
        risks.append("큰 위험 신호는 없습니다.")
    return risks


def _ja(text: str) -> str:
    if text in JA_TEXT:
        return JA_TEXT[text]
    if text.startswith("최근 7일 중 출력 없는 날:"):
        return text.replace("최근 7일 중 출력 없는 날:", "直近7日間でアウトプットがない日:").replace("일", "日")
    if text.startswith("최근 14일 공법 출력 공백:"):
        return text.replace("최근 14일 공법 출력 공백:", "直近14日間の公法アウトプット空白:").replace("일", "日")
    if text.startswith("출력 공백 주의:"):
        return "アウトプット空白に注意: 講義や整理より、答案・記録・復習の成果物を先に置きましょう。"
    if text.startswith("강의시간 대비 출력 부족:"):
        return "講義時間に対してアウトプット不足: 注意"
    return text


def public_summary(public_df: pd.DataFrame, outputs: pd.DataFrame, settings: dict[str, str]) -> dict[str, Any]:
    next_exam = _next_exam(settings)
    notice = "정확한 장소와 답안 내용은 비공개이며, 매일의 루틴과 출력량만 기록합니다."
    base = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "next_milestone": next_exam["name"],
        "next_milestone_ja": _ja(str(next_exam["name"])),
        "next_milestone_d_day": _d_day(next_exam["date"]),
        "notice": notice,
        "notice_ja": _ja(notice),
    }
    if public_df.empty:
        risks = public_risk_signals(public_df, outputs)
        return {
            **base,
            "today_status": "기록 대기",
            "today_status_ja": _ja("기록 대기"),
            "streak_days": 0,
            "weekly_score": 0,
            "risk_signals": risks,
            "risk_signals_ja": [_ja(risk) for risk in risks],
        }

    df = public_df.copy()
    df["date_obj"] = pd.to_datetime(df["date"]).dt.date
    latest = df.sort_values("date_obj").iloc[-1]
    week_start = date.today() - timedelta(days=date.today().weekday())
    week = df[df["date_obj"] >= week_start]
    streak = 0
    by_date = {r["date_obj"]: r["score"] for _, r in df.iterrows()}
    cursor = max(by_date)
    while by_date.get(cursor, 0) >= int(settings.get("daily_min_score", "35")):
        streak += 1
        cursor -= timedelta(days=1)

    risks = public_risk_signals(public_df, outputs)
    today_status = "기록 완료" if int(latest["score"]) > 0 else "기록 대기"
    return {
        **base,
        "today_status": today_status,
        "today_status_ja": _ja(today_status),
        "latest_date": latest["date"],
        "streak_days": streak,
        "weekly_score": int(week["score"].sum()) if not week.empty else 0,
        "weekly_seat_hours": round(float(week["seat_hours"].sum()), 2) if not week.empty else 0,
        "weekly_self_study_hours": round(float(week["self_study_hours"].sum()), 2) if not week.empty else 0,
        "weekly_outputs": int(week["outputs_count"].sum()) if not week.empty else 0,
        "weekly_mcq": int(week["mcq_count"].sum()) if not week.empty else 0,
        "zero_output_days_7d": int((df.tail(7)["outputs_count"] == 0).sum()),
        "risk_signals": risks,
        "risk_signals_ja": [_ja(risk) for risk in risks],
    }


def main() -> None:
    init_db()
    settings = get_settings()
    daily = load_daily()
    outputs = load_outputs()
    day_scores = compute_day_scores(daily, outputs)
    delay_hours = int(settings.get("public_delay_hours", "24"))
    include_hash = settings.get("public_include_evidence_hash", "false").lower() == "true"
    public_df = public_log_frame(daily, outputs, day_scores, delay_hours, include_hash)
    summary = public_summary(public_df, outputs, settings)
    PUBLIC_DIR.mkdir(exist_ok=True)
    public_df.to_csv(PUBLIC_DIR / "public_log.csv", index=False, encoding="utf-8-sig")
    (PUBLIC_DIR / "public_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print("Wrote public/public_log.csv")
    print("Wrote public/public_summary.json")


if __name__ == "__main__":
    main()
