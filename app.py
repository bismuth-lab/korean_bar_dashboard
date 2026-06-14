from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

from barpassos.db import (
    EVIDENCE_DIR,
    delete_row,
    get_settings,
    init_db,
    insert_mock,
    insert_output,
    load_daily,
    load_mocks,
    load_outputs,
    set_setting,
    upsert_daily,
)
from barpassos.heatmap import github_heatmap
from barpassos.metrics import (
    build_risk_flags,
    compute_day_scores,
    current_streak,
    day_likelihood_ratio,
    estimate_probability,
    probability_after_lr,
    weekly_summary,
)

st.set_page_config(page_title="BarPass OS", page_icon="⚖️", layout="wide")

CUSTOM_CSS = """
<style>
:root {
  --card-bg: rgba(255,255,255,0.82);
  --border: rgba(49, 63, 89, 0.12);
}
.block-container {padding-top: 1.4rem; padding-bottom: 3rem;}
[data-testid="stSidebar"] {background: linear-gradient(180deg, #f7f8fb 0%, #eef2f6 100%);}
.metric-card {
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 18px 18px 14px 18px;
  box-shadow: 0 8px 30px rgba(30, 55, 90, 0.06);
  min-height: 116px;
}
.metric-label {font-size: 0.9rem; color: #687083; margin-bottom: 6px;}
.metric-value {font-size: 2.0rem; font-weight: 800; color: #111827;}
.metric-sub {font-size: 0.85rem; color: #687083; margin-top: 6px;}
.hero {
  border-radius: 8px;
  padding: 18px 22px;
  background: linear-gradient(120deg, #111827 0%, #26324a 58%, #334155 100%);
  color: white;
  box-shadow: 0 18px 60px rgba(17,24,39,0.22);
}
.hero h1 {font-size: 2.0rem; margin: 0 0 8px 0;}
.hero p {margin: 0; color: rgba(255,255,255,0.82); font-size: 1.02rem;}
.small-muted {font-size: 0.86rem; color: #6b7280;}
.warning-card {
  border-radius: 8px;
  border: 1px solid rgba(245,158,11,0.22);
  background: rgba(255,251,235,0.86);
  padding: 14px 16px;
  margin: 8px 0;
}
.good-card {
  border-radius: 8px;
  border: 1px solid rgba(34,197,94,0.18);
  background: rgba(240,253,244,0.86);
  padding: 14px 16px;
  margin: 8px 0;
}
.badge {
  display:inline-block; padding: 4px 8px; border-radius: 999px; background: #eef2ff;
  color: #3730a3; font-weight: 700; font-size: 0.78rem; margin-right: 6px;
}
.action-card {
  border: 1px solid rgba(17,24,39,0.10);
  border-radius: 8px;
  background: #ffffff;
  padding: 16px 18px;
  min-height: 132px;
}
.action-title {font-weight: 800; color: #111827; margin-bottom: 8px;}
.action-main {font-size: 1.15rem; font-weight: 800; color: #0f172a; margin-bottom: 6px;}
.action-sub {font-size: 0.9rem; color: #667085;}
.progress-rail {height: 8px; background: #eef2f7; border-radius: 999px; overflow:hidden; margin-top: 10px;}
.progress-fill {height: 8px; background: #2563eb; border-radius: 999px;}
.attendance-list {display:flex; flex-direction:column; gap:10px; margin: 8px 0 18px;}
.attendance-axis {
  display:grid; grid-template-columns: 86px 54px minmax(130px, 1fr) 54px 48px;
  gap:10px; align-items:center; font-size:0.75rem; color:#667085;
}
.attendance-ticks {display:flex; justify-content:space-between; font-variant-numeric:tabular-nums;}
.attendance-row {
  display:grid; grid-template-columns: 86px 54px minmax(130px, 1fr) 54px 48px;
  gap:10px; align-items:center; font-size:0.9rem;
}
.attendance-date {font-weight:800; color:#111827;}
.attendance-time {font-variant-numeric:tabular-nums; color:#475467;}
.attendance-rail {height:14px; border-radius:999px; background:#f1f5f9; position:relative; overflow:hidden; border:1px solid #e2e8f0;}
.attendance-fill {position:absolute; top:0; bottom:0; border-radius:999px; background:#ef4444;}
.attendance-hours {font-weight:800; color:#991b1b; text-align:right; font-variant-numeric:tabular-nums;}
.output-guide {
  border: 1px solid rgba(37,99,235,0.18);
  border-radius: 8px;
  background: #f8fbff;
  padding: 12px 14px;
  margin: 8px 0 12px 0;
}
hr {margin-top: 1.5rem; margin-bottom: 1.5rem;}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

init_db()
settings = get_settings()
PUBLIC_DIR = Path("public")

SUBJECTS = ["민사법", "형사법", "공법", "상법", "민소", "형소", "헌법", "행정법", "선택법", "기타"]
OUTPUT_TYPES = ["사례답안", "CBT답안", "사례목차", "기록형", "기록형목차", "선택형", "오답복기", "암기재현", "판례문장", "재풀이", "기타"]
ERROR_REASONS = ["", "지식부족", "쟁점누락", "사실관계 신호 못 봄", "시간부족", "암기실패", "목차불량", "포섭부족", "실수", "문제요구 오독"]
AVOIDANCE_TAGS = ["자료쇼핑", "계획리셋", "강의만 듣기", "집공 무너짐", "합격수기 과다", "비교/커뮤니티", "기록형 회피", "사례형 회피", "오답 방치", "자습실 결석"]
OUTPUT_GUIDE = {
    "사례답안": "시간을 재고 실제 답안처럼 쓴 글. 완성도가 낮아도 1개입니다.",
    "CBT답안": "노트북으로 본시험처럼 쓴 사례형/기록형 답안. 시간감각 훈련용입니다.",
    "사례목차": "답안 전체가 아니라 쟁점, 요건, 포섭 순서만 잡은 것. 막힌 날의 최소 출력입니다.",
    "기록형": "기록을 읽고 청구취지, 요건사실, 서면 구조를 만든 것.",
    "기록형목차": "기록형 전체 답안 전 단계. 쟁점과 서면 구조만 잡아도 기록합니다.",
    "선택형": "객관식 풀이. 이 유형일 때만 푼 문항/정답 수가 핵심입니다.",
    "오답복기": "왜 틀렸는지 원인을 적고 다시 맞히는 길을 만든 것.",
    "암기재현": "책을 덮고 조문, 요건, 판례문구를 손으로 다시 써본 것.",
    "판례문장": "판례 키워드가 아니라 답안에 쓸 문장 형태로 재현한 것.",
    "재풀이": "틀렸거나 시간초과한 문제를 다시 푼 것. 회복 보너스의 핵심입니다.",
    "기타": "위 유형에 안 들어가지만 사진이나 메모로 남길 수 있는 산출물입니다.",
}
OUTPUT_STARTER_ROWS = [
    ["강의 들은 날", "사례목차 1개 또는 선택형 20문항을 추가"],
    ["집중이 낮은 날", "오답복기 1개 또는 암기재현 1개만 추가"],
    ["컨디션 좋은 날", "사례답안/CBT답안/기록형 중 하나를 시간 재고 추가"],
    ["모의고사 직후", "오답복기, 약점 메모, 재풀이 날짜를 같이 남김"],
]


def reload_data():
    daily = load_daily()
    outputs = load_outputs()
    mocks = load_mocks()
    day_scores = compute_day_scores(daily, outputs)
    return daily, outputs, mocks, day_scores


def metric_card(label: str, value: str, sub: str = "") -> None:
    st.markdown(
        f"""
        <div class='metric-card'>
          <div class='metric-label'>{label}</div>
          <div class='metric-value'>{value}</div>
          <div class='metric-sub'>{sub}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def action_card(title: str, main: str, sub: str = "", progress: float | None = None) -> None:
    progress_html = ""
    if progress is not None:
        pct = max(0, min(100, progress))
        progress_html = f"<div class='progress-rail'><div class='progress-fill' style='width:{pct:.0f}%'></div></div>"
    st.markdown(
        f"""
        <div class='action-card'>
          <div class='action-title'>{title}</div>
          <div class='action-main'>{main}</div>
          <div class='action-sub'>{sub}</div>
          {progress_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def save_upload(uploaded_file) -> tuple[str, str]:
    if uploaded_file is None:
        return "", ""
    EVIDENCE_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = uploaded_file.name.replace("/", "_").replace("\\", "_")
    path = EVIDENCE_DIR / f"{timestamp}_{safe_name}"
    data = uploaded_file.getbuffer()
    path.write_bytes(data)
    return str(path), hashlib.sha256(data).hexdigest()[:16]


def probability_examples(prior: float) -> pd.DataFrame:
    examples = [
        ("강한 출력일: 80점 이상 + 사례/기록 또는 선택형 60문항", 1.015),
        ("좋은 루틴일: 65점 이상", 1.010),
        ("최소 루틴일: 35점 이상", 1.003),
        ("기록은 했지만 출력 약함", 0.993),
        ("완전 결손일", 0.985),
        ("7월 진단 모의고사: 좋음", 1.25),
        ("7월 진단 모의고사: 나쁨 + 복기 미완", 0.85),
        ("7월 진단 모의고사: 나쁨 + 72시간 복기/2주 재풀이", 1.05),
        ("모의고사 상위 50% 부근", 1.8),
        ("10월/3차 모의고사 상위 35% 부근", 3.0 ** 1.6),
    ]
    rows = []
    for label, lr in examples:
        after = probability_after_lr(prior, lr)
        rows.append({"행동/증거": label, "LR": round(lr, 3), "예상 변화": f"{prior*100:.1f}% → {after*100:.1f}%"})
    return pd.DataFrame(rows)


def _setting_date(key: str, fallback: str) -> date:
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


def build_milestones() -> list[dict[str, str | date]]:
    exam_date = _setting_date("exam_date", "2028-01-11")
    return [
        {
            "kind": "시험",
            "name": "7월 학교/학원 모의고사",
            "role": "중간보스/진단전",
            "date": _setting_date("mock_july_date", "2027-07-15"),
            "goal": "약점 3개 등록, 반복오답 10개, 72시간 복기",
        },
        {
            "kind": "시험",
            "name": "10월 법전협/실전 모의고사",
            "role": "본시험 예측 신호",
            "date": _setting_date("mock_october_date", "2027-10-15"),
            "goal": "사례형 12개, 기록형 4개, CBT 6시간 감각 확인",
        },
        {
            "kind": "최종",
            "name": "2028 변호사시험",
            "role": "최종 보스",
            "date": exam_date,
            "goal": "기출 패턴, 선택형 하방, 기록형 시간관리 완성",
        },
        {
            "kind": "운영",
            "name": "현재 기말고사 시작",
            "role": "진행 중인 학교시험",
            "date": _setting_date("current_final_start", "2026-06-10"),
            "goal": "내신 우선, 변시 루틴은 최소 출력으로 끊기지 않게 유지",
        },
        {
            "kind": "운영",
            "name": "현재 기말고사 종료",
            "role": "방학 루틴 전환",
            "date": _setting_date("current_final_end", "2026-06-21"),
            "goal": "시험 후 48시간 안에 오답/약점 목록으로 전환",
        },
        {
            "kind": "운영",
            "name": "여름방학 종료",
            "role": "방학 퀘스트 마감",
            "date": _setting_date("summer_break_end", "2026-08-31"),
            "goal": "사례 목차/기록형/선택형/CBT 출력량 점검",
        },
        {
            "kind": "운영",
            "name": "2학기 개강",
            "role": "수업+복습+최소출력 모드 전환",
            "date": _setting_date("fall_semester_start", "2026-09-01"),
            "goal": "개강 후 2주 루틴 유지",
        },
        {
            "kind": "운영",
            "name": "중간고사 시작",
            "role": "학교시험-변시기출 연결",
            "date": _setting_date("midterm_start", "2026-10-19"),
            "goal": "내신 대비 중에도 변시 출력 0 방지",
        },
        {
            "kind": "운영",
            "name": "중간고사 종료",
            "role": "모의고사/기출 회복",
            "date": _setting_date("midterm_end", "2026-10-30"),
            "goal": "밀린 오답과 사례 출력 복구",
        },
        {
            "kind": "운영",
            "name": "기말고사 시작",
            "role": "내신 관리+변시 감각 유지",
            "date": _setting_date("final_start", "2026-12-07"),
            "goal": "최소 선택형/오답 루틴 유지",
        },
        {
            "kind": "운영",
            "name": "2학기 종강",
            "role": "겨울 집중모드 준비",
            "date": _setting_date("fall_semester_end", "2026-12-18"),
            "goal": "학기 중 약점 목록 재정렬",
        },
        {
            "kind": "운영",
            "name": "겨울방학 시작",
            "role": "전범위 집중모드",
            "date": _setting_date("winter_break_start", "2026-12-21"),
            "goal": "전범위 회독과 출력량 재상승",
        },
        {
            "kind": "운영",
            "name": "2027년 1학기 개강",
            "role": "수업+변시 출력 병행",
            "date": _setting_date("spring_2027_start", "2027-03-02"),
            "goal": "학기 첫 2주에 최소 루틴 고정",
        },
        {
            "kind": "운영",
            "name": "2027년 1학기 중간고사 시작",
            "role": "내신-변시 병행 압박 구간",
            "date": _setting_date("spring_2027_midterm_start", "2027-04-20"),
            "goal": "학교시험 대비 중에도 선택형/오답 루틴 0 방지",
        },
        {
            "kind": "운영",
            "name": "2027년 1학기 중간고사 종료",
            "role": "모의고사 전 회복 구간",
            "date": _setting_date("spring_2027_midterm_end", "2027-05-01"),
            "goal": "밀린 사례 목차와 반복오답을 1주 안에 복구",
        },
        {
            "kind": "운영",
            "name": "2027년 1학기 기말고사 시작",
            "role": "7월 모의고사 직전 압박 구간",
            "date": _setting_date("spring_2027_final_start", "2027-06-08"),
            "goal": "내신 마무리와 7월 진단전 준비를 분리해서 관리",
        },
        {
            "kind": "운영",
            "name": "2027년 1학기 기말고사 종료",
            "role": "7월 진단전 전환",
            "date": _setting_date("spring_2027_final_end", "2027-06-19"),
            "goal": "72시간 안에 약점 3개와 7월 모의고사 체크리스트 확정",
        },
    ]


def _next_milestone(milestones: list[dict[str, str | date]], kinds: set[str]) -> dict[str, str | date] | None:
    today = date.today()
    future = [m for m in milestones if m["kind"] in kinds and m["date"] >= today]
    return min(future, key=lambda m: m["date"]) if future else None


def milestone_table(milestones: list[dict[str, str | date]]) -> pd.DataFrame:
    rows = []
    for item in sorted(milestones, key=lambda m: m["date"]):
        rows.append(
            {
                "구분": item["kind"],
                "마일스톤": item["name"],
                "의미": item["role"],
                "날짜": item["date"].isoformat(),
                "D-Day": _d_day(item["date"]),
                "목표": item["goal"],
            }
        )
    return pd.DataFrame(rows)


def _fmt_hours(minutes: int | float) -> str:
    minutes = int(minutes or 0)
    return f"{minutes // 60}h {minutes % 60:02d}m"


def _time_to_minutes(value: str | None) -> int | None:
    if not value:
        return None
    try:
        t = datetime.strptime(str(value).strip(), "%H:%M")
    except ValueError:
        return None
    return t.hour * 60 + t.minute


def _duration_minutes(checkin: str | None, checkout: str | None) -> int:
    start = _time_to_minutes(checkin)
    end = _time_to_minutes(checkout)
    if start is None or end is None:
        return 0
    if end < start:
        end += 24 * 60
    return max(0, end - start)


def flash_success(message: str) -> None:
    st.session_state["flash_success"] = f"{message} · {datetime.now().strftime('%H:%M:%S')}"


def show_flash_success() -> None:
    message = st.session_state.pop("flash_success", "")
    if message:
        st.success(message)


def attendance_bars_html(rows: pd.DataFrame) -> str:
    if rows.empty:
        return ""
    day_start = 7 * 60
    day_span = 17 * 60
    axis = (
        "<div class='attendance-axis'>"
        "<div></div><div></div>"
        "<div class='attendance-ticks'><span>07</span><span>12</span><span>18</span><span>24</span></div>"
        "<div></div><div></div>"
        "</div>"
    )
    items = []
    for _, row in rows.iterrows():
        checkin = str(row.get("checkin") or "")
        checkout = str(row.get("checkout") or "")
        start = _time_to_minutes(checkin)
        end = _time_to_minutes(checkout)
        duration = _duration_minutes(checkin, checkout)
        if start is None or end is None:
            fill = "<div class='attendance-rail'></div>"
            hours = "-"
        else:
            if end < start:
                end += 24 * 60
            left = max(0, min(100, (start - day_start) / day_span * 100))
            right = max(left, min(100, (end - day_start) / day_span * 100))
            fill = (
                "<div class='attendance-rail'>"
                f"<div class='attendance-fill' style='left:{left:.2f}%; width:{right-left:.2f}%;'></div>"
                "</div>"
            )
            hours = f"{duration / 60:.1f}h"
        items.append(
            "<div class='attendance-row'>"
            f"<div class='attendance-date'>{row.get('date')}</div>"
            f"<div class='attendance-time'>{checkin or '-'}</div>"
            f"{fill}"
            f"<div class='attendance-time'>{checkout or '-'}</div>"
            f"<div class='attendance-hours'>{hours}</div>"
            "</div>"
        )
    return "<div class='attendance-list'>" + axis + "".join(items) + "</div>"


def _daily_record_from_row(row: dict, stamped: dict[str, str]) -> dict:
    merged = {**row, **stamped}
    return {
        "date": merged.get("date", date.today()).isoformat() if isinstance(merged.get("date"), date) else str(merged.get("date", date.today().isoformat())),
        "checkin": merged.get("checkin") or "",
        "checkout": merged.get("checkout") or "",
        "location": merged.get("location") or "자습실",
        "first_task": merged.get("first_task") or "",
        "completed_first": int(merged.get("completed_first") or 0),
        "lecture_min": int(merged.get("lecture_min") or 0),
        "self_study_min": int(merged.get("self_study_min") or 0),
        "cbt_practice_min": int(merged.get("cbt_practice_min") or 0),
        "study_blocks": int(merged.get("study_blocks") or 0),
        "sleep_hours": float(merged.get("sleep_hours") or 0),
        "exercise_min": int(merged.get("exercise_min") or 0),
        "mood": int(merged.get("mood") or 3),
        "energy": int(merged.get("energy") or 3),
        "anxiety": int(merged.get("anxiety") or 3),
        "avoidance": merged.get("avoidance") or [],
        "note": merged.get("note") or "",
    }


def _stamp_today(row: dict, field: str) -> None:
    now_text = datetime.now().strftime("%H:%M")
    upsert_daily(_daily_record_from_row(row, {field: now_text}))


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
            "seat_hours": round(float(row.get("attendance_min") or 0) / 60, 2),
            "self_study_hours": round(float(row.get("effective_study_min") or 0) / 60, 2),
            "lecture_hours": round(float(row.get("lecture_min") or 0) / 60, 2),
            "cbt_hours": round(float(row.get("cbt_practice_min") or 0) / 60, 2),
            "outputs_count": int(row.get("outputs_count") or 0),
            "mcq_count": int(row.get("mcq_attempted") or 0),
            "first_task_done": bool(row.get("completed_first")),
            "score": int(row.get("day_score") or 0),
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


def public_ja(text: str) -> str:
    mapping = {
        "공개 가능한 기록이 아직 없습니다.": "公開できる記録はまだありません。",
        "큰 위험 신호는 없습니다.": "大きなリスクサインはありません。",
        "7월 학교/학원 모의고사": "7月 学内・予備校模試",
        "10월 법전협/실전 모의고사": "10月 実戦模試",
        "2028 변호사시험": "2028年 韓国弁護士試験",
    }
    if text in mapping:
        return mapping[text]
    if text.startswith("최근 7일 중 출력 없는 날:"):
        return text.replace("최근 7일 중 출력 없는 날:", "直近7日間でアウトプットがない日:").replace("일", "日")
    if text.startswith("최근 14일 공법 출력 공백:"):
        return text.replace("최근 14일 공법 출력 공백:", "直近14日間の公法アウトプット空白:").replace("일", "日")
    if text.startswith("출력 공백 주의:"):
        return "アウトプット空白に注意: 講義や整理より、答案・記録・復習の成果物を先に置きましょう。"
    if text.startswith("강의시간 대비 출력 부족:"):
        return "講義時間に対してアウトプット不足: 注意"
    return text


def public_summary(public_df: pd.DataFrame, milestones: list[dict[str, str | date]], outputs: pd.DataFrame) -> dict[str, object]:
    next_exam = _next_milestone(milestones, {"시험", "최종"})
    notice = "정확한 장소와 답안 내용은 비공개이며, 매일의 루틴과 출력량만 기록합니다."
    if public_df.empty:
        return {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "today_status": "기록 대기",
            "today_status_ja": "記録待ち",
            "streak_days": 0,
            "weekly_score": 0,
            "next_milestone": next_exam["name"] if next_exam else "",
            "next_milestone_ja": public_ja(str(next_exam["name"])) if next_exam else "",
            "next_milestone_d_day": _d_day(next_exam["date"]) if next_exam else "",
            "risk_signals": public_risk_signals(public_df, outputs),
            "risk_signals_ja": ["公開できる記録はまだありません。"],
            "notice": notice,
            "notice_ja": "正確な場所と答案の内容は非公開にし、毎日のルーティンとアウトプット量だけを記録します。",
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
    today_status = "기록 완료" if int(latest["score"]) > 0 else "기록 대기"
    risk_signals = public_risk_signals(public_df, outputs)
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "today_status": today_status,
        "today_status_ja": "記録完了" if today_status == "기록 완료" else "記録待ち",
        "latest_date": latest["date"],
        "streak_days": streak,
        "weekly_score": int(week["score"].sum()) if not week.empty else 0,
        "weekly_seat_hours": round(float(week["seat_hours"].sum()), 2) if not week.empty else 0,
        "weekly_self_study_hours": round(float(week["self_study_hours"].sum()), 2) if not week.empty else 0,
        "weekly_outputs": int(week["outputs_count"].sum()) if not week.empty else 0,
        "weekly_mcq": int(week["mcq_count"].sum()) if not week.empty else 0,
        "zero_output_days_7d": int((df.tail(7)["outputs_count"] == 0).sum()),
        "next_milestone": next_exam["name"] if next_exam else "",
        "next_milestone_ja": public_ja(str(next_exam["name"])) if next_exam else "",
        "next_milestone_d_day": _d_day(next_exam["date"]) if next_exam else "",
        "risk_signals": risk_signals,
        "risk_signals_ja": [public_ja(risk) for risk in risk_signals],
        "notice": notice,
        "notice_ja": "正確な場所と答案の内容は非公開にし、毎日のルーティンとアウトプット量だけを記録します。",
    }


def export_public_files(public_df: pd.DataFrame, summary: dict[str, object]) -> None:
    PUBLIC_DIR.mkdir(exist_ok=True)
    public_df.to_csv(PUBLIC_DIR / "public_log.csv", index=False, encoding="utf-8-sig")
    (PUBLIC_DIR / "public_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def output_help() -> None:
    with st.expander("출력/문제풀이를 어떻게 적으면 되는지", expanded=False):
        st.markdown(
            """
            **출력**은 정답을 보기 전에 네 머리와 손으로 만들어낸 결과물입니다. 강의 필기, 책 읽기, 판례 복사는 출력이 아닙니다.

            - **사례답안**: 시간 제한을 걸고 쓴 실제 답안. 완성도가 낮아도 출력입니다.
            - **CBT답안**: 노트북으로 본시험처럼 쓴 사례형/기록형 답안. 2028 시험 대비 핵심 훈련입니다.
            - **사례목차**: 답안 전체를 쓰지 못해도 쟁점·요건·포섭 순서만 잡은 것.
            - **기록형**: 기록을 읽고 청구취지, 요건사실, 공격방어, 서면 구조를 만들어낸 것.
            - **선택형**: 객관식 문제풀이. 문항 수와 정답 수를 같이 입력해야 의미가 있습니다.
            - **오답복기**: 틀린 이유를 `지식부족/쟁점누락/사실관계 신호/시간부족/암기실패` 등으로 분류한 것.
            - **암기재현/판례문장**: 책을 보고 외운 게 아니라, 가리고 실제로 써본 문장.

            기준은 간단합니다. **사진으로 남길 수 있으면 출력이고, 머릿속으로 이해만 했으면 입력입니다.**
            """
        )
        st.dataframe(pd.DataFrame(OUTPUT_STARTER_ROWS, columns=["상황", "이렇게 기록"]), hide_index=True, use_container_width=True)


def page_dashboard():
    daily, outputs, mocks, day_scores = reload_data()
    exam_date = datetime.strptime(settings.get("exam_date", "2028-01-11"), "%Y-%m-%d").date()
    days_left = max(0, (exam_date - date.today()).days)
    prior = float(settings.get("prior_probability", "0.70"))
    posterior, updates = estimate_probability(prior, day_scores, mocks)
    week = weekly_summary(day_scores, outputs)
    streak = current_streak(day_scores, int(settings.get("daily_min_score", "35")))
    milestones = build_milestones()
    next_exam = _next_milestone(milestones, {"시험", "최종"})
    next_ops = _next_milestone(milestones, {"운영"})

    st.markdown(
        """
        <div class='hero'>
          <h1>BarPass OS</h1>
          <p>자습실 출근 → 출력 → 오답복기 → 모의고사 위치 확인. 합격에 가까워지는 행동만 추적합니다.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.write("")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        if next_exam:
            metric_card("다음 보스전", _d_day(next_exam["date"]), f"{next_exam['name']} · {next_exam['role']}")
        else:
            metric_card("D-Day", f"D-{days_left}", f"시험일 설정: {exam_date.isoformat()}")
    with c2:
        if next_ops:
            metric_card("다음 전환점", _d_day(next_ops["date"]), f"{next_ops['name']} · {next_ops['role']}")
        else:
            metric_card("현재 루틴 연속", f"{streak}일", "합격기여점수 기준")
    with c3:
        metric_card("최종 보스", f"D-{days_left}", f"2028 변호사시험 · {exam_date.isoformat()}")
    with c4:
        delta = posterior - prior
        metric_card("게임형 합격가능성", f"{posterior*100:.1f}%", f"초기값 대비 {delta*100:+.1f}%p")

    if next_exam:
        st.info(f"다음 보스: **{next_exam['name']} {_d_day(next_exam['date'])}** · 목표: {next_exam['goal']}")
    if next_ops:
        st.caption(f"현재 운영 기준: 다음 스테이지 전환은 **{next_ops['name']} {_d_day(next_ops['date'])}**입니다. 방학/학기 날짜는 합격률을 직접 흔들지 않고 공부 모드만 바꿉니다.")

    st.subheader("오늘 작전")
    a1, a2, a3 = st.columns(3)
    output_goal = max(1, int(settings.get("weekly_output_goal", "12")))
    mcq_goal = max(1, int(settings.get("weekly_mcq_goal", "200")))
    with a1:
        if week["heavy_outputs"] < 4:
            action_card("최우선", "사례/기록 출력 1개", f"이번 주 {week['heavy_outputs']}개 · 최소 4개부터", min(100, week["heavy_outputs"] / 4 * 100))
        else:
            action_card("최우선", "오답복기 1개", "출력은 올라왔습니다. 회수율을 올릴 차례입니다.", 100)
    with a2:
        action_card("선택형 하방", f"{week['mcq_attempted']} / {mcq_goal}문항", "20~40문항이라도 끊기지 않게", min(100, week["mcq_attempted"] / mcq_goal * 100))
    with a3:
        action_card("이번 주 총출력", f"{week['output_qty']} / {output_goal}개", "사진이나 메모로 남길 수 있으면 출력입니다.", min(100, week["output_qty"] / output_goal * 100))

    left, right = st.columns([1.05, 0.95])
    with left:
        st.subheader("이번 주 요약")
        summary_rows = [
            ["자습실/열람실 체류", f"{week['attendance_hours']} 시간"],
            ["실제 자습·문제풀이", f"{week['self_study_hours']} 시간"],
            ["인강/학교수업", f"{week['lecture_hours']} 시간"],
            ["CBT 답안 연습", f"{week['cbt_hours']} 시간"],
            ["사례/기록형 출력", f"{week['heavy_outputs']} 개"],
            ["선택형 풀이", f"{week['mcq_attempted']} 문항"],
            ["첫 과제 완료율", f"{week['first_task_rate']*100:.0f}%"],
            ["평균 합격기여점수", f"{week['avg_score']:.1f}"],
        ]
        st.dataframe(pd.DataFrame(summary_rows, columns=["항목", "값"]), hide_index=True, use_container_width=True)

    with right:
        st.subheader("위험 신호")
        for flag in build_risk_flags(day_scores, outputs, daily):
            st.markdown(f"<div class='warning-card'>{flag}</div>", unsafe_allow_html=True)

    detail_tab, heatmap_tab, milestone_tab = st.tabs(["흐름", "히트맵", "마일스톤"])
    with detail_tab:
        st.subheader("이번 방학 강공 퀘스트")
        st.markdown(
            """
            - 민사 사례 목차 40개
            - 형사 사례 목차 25개
            - 공법 사례 목차 20개
            - 기록형 6회
            - 선택형 1,200문항
            - CBT 답안 연습 20시간
            - 반복오답 TOP 50 정리
            """
        )
    with heatmap_tab:
        st.subheader("GitHub식 합격기여 히트맵")
        st.plotly_chart(github_heatmap(day_scores), use_container_width=True)
    with milestone_tab:
        st.subheader("마일스톤 타임라인")
        st.dataframe(milestone_table(milestones), hide_index=True, use_container_width=True)

    with st.expander("확률은 어떤 감각으로 움직이나"):
        st.caption("실제 예측기가 아니라 게임형 계기판입니다. 하루 행동은 작게, 모의고사는 크게 움직입니다.")
        st.dataframe(probability_examples(prior), hide_index=True, use_container_width=True)
        st.write("핵심은 숫자를 맞히는 게 아니라, 숫자가 올라가는 행동을 반복하게 만드는 것입니다.")

    st.subheader("최근 베이지안 업데이트")
    if updates:
        st.dataframe(pd.DataFrame(updates).tail(10), hide_index=True, use_container_width=True)
    else:
        st.info("모의고사 또는 루틴 기록이 쌓이면 업데이트가 표시됩니다.")


def render_public_dashboard(public_df: pd.DataFrame, summary: dict[str, object], delay_hours: int, empty_message: str) -> None:
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        metric_card("오늘의 상태 / 今日の状態", str(summary["today_status"]), f"{summary.get('today_status_ja', '')} · 공개 지연 {delay_hours}시간")
    with c2:
        metric_card("연속 기록 / 連続記録", f"{summary['streak_days']}일", f"{summary['streak_days']}日 · 공개 로그 기준")
    with c3:
        metric_card("이번 주 합격기여점수 / 今週の貢献点", f"{summary['weekly_score']}점", f"출력 {summary.get('weekly_outputs', 0)}개")
    with c4:
        metric_card("다음 보스 / 次のボス", str(summary["next_milestone_d_day"]), f"{summary['next_milestone']} · {summary.get('next_milestone_ja', '')}")

    st.subheader("GitHub식 공개 히트맵")
    if public_df.empty:
        st.info(empty_message)
    else:
        public_scores = public_df[["date", "score"]].copy()
        public_scores["date"] = pd.to_datetime(public_scores["date"]).dt.date
        public_scores = public_scores.rename(columns={"score": "day_score"})
        st.plotly_chart(github_heatmap(public_scores), use_container_width=True)

    st.subheader("최근 7일 공개 로그")
    if public_df.empty:
        st.dataframe(public_df, hide_index=True, use_container_width=True)
    else:
        recent = public_df.tail(7).copy()
        st.markdown(attendance_bars_html(recent), unsafe_allow_html=True)
        recent["착석"] = recent["seat_hours"].apply(lambda h: _fmt_hours(round(float(h) * 60)))
        recent["자습"] = recent["self_study_hours"].apply(lambda h: _fmt_hours(round(float(h) * 60)))
        recent["첫 과제"] = recent["first_task_done"].map({True: "완료", False: "미완료"})
        recent["수정"] = recent["edited"].map({True: "수정됨", False: ""})
        recent["지연입력"] = recent["late_entry"].map({True: "지연", False: ""})
        show_cols = ["date", "checkin", "checkout", "착석", "자습", "outputs_count", "mcq_count", "첫 과제", "score", "수정", "지연입력"]
        st.dataframe(
            recent[show_cols].rename(
                columns={
                    "date": "날짜",
                    "checkin": "앉음",
                    "checkout": "떠남",
                    "outputs_count": "출력",
                    "mcq_count": "선택형",
                    "score": "점수",
                }
            ),
            hide_index=True,
            use_container_width=True,
        )

    st.subheader("공개용 주간 요약")
    weekly_rows = [
        ["착석", f"{summary.get('weekly_seat_hours', 0)}시간"],
        ["실제 자습", f"{summary.get('weekly_self_study_hours', 0)}시간"],
        ["사례/기록 출력", f"{summary.get('weekly_outputs', 0)}개"],
        ["선택형", f"{summary.get('weekly_mcq', 0)}문항"],
        ["최근 7일 중 출력 없는 날", f"{summary.get('zero_output_days_7d', 0)}일"],
    ]
    st.dataframe(pd.DataFrame(weekly_rows, columns=["항목", "값"]), hide_index=True, use_container_width=True)

    st.subheader("위험 신호")
    risk_ja = summary.get("risk_signals_ja", [])
    for idx, risk in enumerate(summary.get("risk_signals", [])):
        ja = risk_ja[idx] if isinstance(risk_ja, list) and idx < len(risk_ja) else ""
        st.markdown(f"<div class='warning-card'>{risk}<br><span class='small-muted'>{ja}</span></div>", unsafe_allow_html=True)


def page_public_dashboard():
    st.header("Public Dashboard")
    st.caption("정확한 장소와 답안 내용은 비공개이며, 매일의 루틴과 출력량만 기록합니다.")
    st.caption("正確な場所と答案の内容は非公開にし、毎日のルーティンとアウトプット量だけを記録します。")
    st.markdown(
        """
        <div class='warning-card'>
          <strong>공개 목적 / 公開の目的</strong><br>
          누군가에게 감시받기보다, 도망치면 빈칸이 남는 구조를 만들기 위한 로그입니다.<br>
          <span class='small-muted'>誰かに監視されるためではなく、逃げた日には空白が残る仕組みを作るためのログです。</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    daily, outputs, _, day_scores = reload_data()
    delay_hours = int(settings.get("public_delay_hours", "24"))
    include_hash = settings.get("public_include_evidence_hash", "false").lower() == "true"
    public_df = public_log_frame(daily, outputs, day_scores, delay_hours, include_hash)
    summary = public_summary(public_df, build_milestones(), outputs)
    export_public_files(public_df, summary)
    render_public_dashboard(
        public_df,
        summary,
        delay_hours,
        "공개 가능한 기록이 아직 없습니다. 24시간 지연 공개 옵션이 켜져 있으면 오늘 기록은 내일 공개됩니다.",
    )

    st.subheader("공개 파일")
    st.code("public/public_log.csv\npublic/public_summary.json", language="text")
    st.caption("Public Dashboard를 열 때마다 공개용 CSV/JSON이 갱신됩니다.")


def page_public_preview():
    st.header("Public Preview")
    st.caption("지금 입력된 데이터가 공개 대시보드에 어떻게 보일지 지연 없이 미리 봅니다. 이 화면은 공개 파일을 갱신하지 않습니다.")
    daily, outputs, _, day_scores = reload_data()
    include_hash = settings.get("public_include_evidence_hash", "false").lower() == "true"
    public_df = public_log_frame(daily, outputs, day_scores, 0, include_hash)
    summary = public_summary(public_df, build_milestones(), outputs)
    render_public_dashboard(
        public_df,
        summary,
        0,
        "아직 미리보기할 기록이 없습니다. 오늘 기록을 저장하면 이 화면에 바로 반영됩니다.",
    )


def _daily_form(existing_row: dict, form_key: str = "daily_form", compact: bool = False):
    today = date.today()
    with st.form(form_key):
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            d = st.date_input("날짜", value=today, key=f"{form_key}_date")
            location = st.text_input("장소", value=existing_row.get("location", "자습실"), key=f"{form_key}_location")
        with c2:
            checkin = st.text_input("입실", value=existing_row.get("checkin", "09:00"), help="HH:MM", key=f"{form_key}_checkin")
            checkout = st.text_input("퇴실", value=existing_row.get("checkout", ""), help="HH:MM", key=f"{form_key}_checkout")
        with c3:
            self_study_min = st.number_input("실제 자습/문제풀이(분)", min_value=0, max_value=900, value=int(existing_row.get("self_study_min") or 0), step=10, help="강의·수업을 제외하고 직접 푼 시간, 답안작성, 오답, 암기재현 시간을 적습니다.", key=f"{form_key}_self")
            lecture_min = st.number_input("인강/학교수업(분, 자습 제외)", min_value=0, max_value=900, value=int(existing_row.get("lecture_min") or 0), step=10, key=f"{form_key}_lecture")
        with c4:
            cbt_practice_min = st.number_input("CBT 답안 연습(분)", min_value=0, max_value=600, value=int(existing_row.get("cbt_practice_min") or 0), step=10, help="노트북으로 본시험처럼 작성한 사례/기록형 시간입니다.", key=f"{form_key}_cbt")
            study_blocks = st.number_input("집중 블록 수", min_value=0, max_value=20, value=int(existing_row.get("study_blocks") or 0), step=1, key=f"{form_key}_blocks")

        first_task = st.text_input("내일/오늘 첫 과제 하나", value=existing_row.get("first_task", ""), placeholder="예: 민법 사례형 채권자대위권 목차 1개", key=f"{form_key}_first")
        completed_first = st.checkbox("첫 과제 완료", value=bool(existing_row.get("completed_first", 0)), key=f"{form_key}_completed")

        if compact:
            sleep = float(existing_row.get("sleep_hours") or 0.0)
            exercise = int(existing_row.get("exercise_min") or 0)
            mood = int(existing_row.get("mood") or 3)
            energy = int(existing_row.get("energy") or 3)
            anxiety = int(existing_row.get("anxiety") or 3)
            avoidance = existing_row.get("avoidance", []) or []
            note = existing_row.get("note", "")
        else:
            c5, c6, c7, c8, c9 = st.columns(5)
            with c5:
                sleep = st.number_input("수면", min_value=0.0, max_value=14.0, value=float(existing_row.get("sleep_hours") or 0.0), step=0.5, key=f"{form_key}_sleep")
            with c6:
                exercise = st.number_input("운동/산책(분)", min_value=0, max_value=300, value=int(existing_row.get("exercise_min") or 0), step=5, key=f"{form_key}_exercise")
            with c7:
                mood = st.slider("기분", 1, 5, int(existing_row.get("mood") or 3), key=f"{form_key}_mood")
            with c8:
                energy = st.slider("에너지", 1, 5, int(existing_row.get("energy") or 3), key=f"{form_key}_energy")
            with c9:
                anxiety = st.slider("불안", 1, 5, int(existing_row.get("anxiety") or 3), key=f"{form_key}_anxiety")
            avoidance = st.multiselect("오늘 회피행동 태그", AVOIDANCE_TAGS, default=existing_row.get("avoidance", []) or [], key=f"{form_key}_avoidance")
            note = st.text_area("메모", value=existing_row.get("note", ""), height=90, key=f"{form_key}_note")

        saved = st.form_submit_button("오늘 기록 저장", use_container_width=True)
        if saved:
            upsert_daily(
                {
                    "date": d.isoformat(),
                    "checkin": checkin,
                    "checkout": checkout,
                    "location": location,
                    "first_task": first_task,
                    "completed_first": int(completed_first),
                    "lecture_min": int(lecture_min),
                    "self_study_min": int(self_study_min),
                    "cbt_practice_min": int(cbt_practice_min),
                    "study_blocks": int(study_blocks),
                    "sleep_hours": float(sleep),
                    "exercise_min": int(exercise),
                    "mood": int(mood),
                    "energy": int(energy),
                    "anxiety": int(anxiety),
                    "avoidance": avoidance,
                    "note": note,
                }
            )
            flash_success("오늘 기록을 저장했습니다")
            st.rerun()


def _output_form(form_key: str = "output_form", compact: bool = False):
    today = date.today()
    with st.form(form_key, clear_on_submit=True):
        st.markdown(
            """
            <div class='output-guide'>
              <strong>기록 기준:</strong> 사진이나 메모로 남길 수 있으면 출력입니다. 이해만 하고 넘어간 것은 입력입니다.
            </div>
            """,
            unsafe_allow_html=True,
        )
        c1, c2, c3 = st.columns([0.9, 1.0, 0.8])
        with c1:
            od = st.date_input("출력 날짜", value=today, key=f"{form_key}_date")
            subject = st.selectbox("과목", SUBJECTS, key=f"{form_key}_subject")
        with c2:
            output_type = st.selectbox("유형", OUTPUT_TYPES, key=f"{form_key}_type", help="막히면 사례목차, 선택형, 오답복기 중 하나로 시작하세요.")
            st.caption(OUTPUT_GUIDE.get(output_type, "사진이나 메모로 남길 수 있는 산출물을 기록합니다."))
        with c3:
            quantity_label = "문항 수" if output_type == "선택형" else "개수"
            quantity = st.number_input(quantity_label, min_value=1, max_value=300, value=20 if output_type == "선택형" else 1, key=f"{form_key}_qty")
            duration = st.number_input("소요시간(분)", min_value=0, max_value=600, value=0, step=5, key=f"{form_key}_dur")

        attempted = int(quantity) if output_type == "선택형" else 0
        correct = 0
        score = 0.0
        error_reason = ""
        if output_type == "선택형":
            c4, c5 = st.columns(2)
            with c4:
                correct = st.number_input("정답 수", min_value=0, max_value=300, value=0, key=f"{form_key}_correct")
            with c5:
                error_reason = st.selectbox("주된 오답 원인", ERROR_REASONS, key=f"{form_key}_error")
        else:
            with st.expander("선택 입력: 점수·오답 원인·사진"):
                c4, c5 = st.columns(2)
                with c4:
                    score = st.number_input("답안/모의 점수", min_value=0.0, max_value=2000.0, value=0.0, step=0.5, key=f"{form_key}_score")
                with c5:
                    error_reason = st.selectbox("오답/부족 원인", ERROR_REASONS, key=f"{form_key}_error")
                evidence = st.file_uploader("답안/문제풀이 사진", type=["png", "jpg", "jpeg", "pdf", "heic"], key=f"{form_key}_evidence")
        if output_type == "선택형":
            evidence = None
            score = 0.0
        out_note = "" if compact else st.text_area("한 줄 메모", height=70, placeholder="예: 민법 채권자대위권 목차. 시간 부족으로 포섭 약함.", key=f"{form_key}_note")
        submitted = st.form_submit_button("출력 추가", use_container_width=True)
        if submitted:
            evidence_path, evidence_hash = save_upload(evidence)
            insert_output(
                {
                    "date": od.isoformat(),
                    "subject": subject,
                    "output_type": output_type,
                    "quantity": int(quantity),
                    "duration_min": int(duration),
                    "attempted": int(attempted),
                    "correct": int(correct),
                    "score": None if score == 0 else float(score),
                    "error_reason": error_reason,
                    "evidence_path": evidence_path,
                    "evidence_hash": evidence_hash,
                    "note": out_note,
                }
            )
            flash_success("출력을 추가했습니다")
            st.rerun()


def page_today():
    st.header("오늘 기록")
    show_flash_success()
    daily, _, _, _ = reload_data()
    today = date.today()
    existing = daily[daily["date"] == today] if not daily.empty else pd.DataFrame()
    row = existing.iloc[0].to_dict() if not existing.empty else {}

    st.info("`인강/학교수업`에는 자습을 포함하지 마세요. 자습은 `실제 자습/문제풀이`에 따로 적습니다. 입실/퇴실은 장소 고정 루틴 확인용입니다.")
    b1, b2, b3 = st.columns([1, 1, 2])
    with b1:
        if st.button("지금 앉음", use_container_width=True):
            _stamp_today(row, "checkin")
            flash_success("앉은 시간을 저장했습니다")
            st.rerun()
    with b2:
        if st.button("지금 떠남", use_container_width=True):
            _stamp_today(row, "checkout")
            flash_success("떠난 시간을 저장했습니다")
            st.rerun()
    with b3:
        if row.get("checkin") or row.get("checkout"):
            st.caption(f"오늘 기록: 앉음 {row.get('checkin') or '-'} · 떠남 {row.get('checkout') or '-'}")
    _daily_form(row)

    st.divider()
    st.subheader("출력/문제풀이 빠른 추가")
    output_help()
    _output_form()


def page_quick():
    st.header("60초 빠른 입력")
    show_flash_success()
    st.caption("모바일이나 피곤한 날에는 여기만 써도 됩니다. 완벽한 기록보다 끊기지 않는 기록이 우선입니다.")
    daily, _, _, _ = reload_data()
    today = date.today()
    existing = daily[daily["date"] == today] if not daily.empty else pd.DataFrame()
    row = existing.iloc[0].to_dict() if not existing.empty else {}
    b1, b2 = st.columns(2)
    with b1:
        if st.button("지금 앉음", use_container_width=True, key="quick_checkin"):
            _stamp_today(row, "checkin")
            st.rerun()
    with b2:
        if st.button("지금 떠남", use_container_width=True, key="quick_checkout"):
            _stamp_today(row, "checkout")
            st.rerun()
    _daily_form(row, form_key="quick_daily", compact=True)
    st.divider()
    _output_form(form_key="quick_output", compact=True)


def page_outputs():
    st.header("출력·오답 로그")
    _, outputs, _, _ = reload_data()
    output_help()
    st.subheader("유형 선택 기준")
    guide_rows = [
        ["사례목차", "막힌 날의 최소 출력. 쟁점·요건·포섭 순서만 잡아도 기록"],
        ["사례답안/CBT답안", "시간 재고 실제 답안처럼 쓴 날. 완성도보다 손으로 쓴 사실이 중요"],
        ["기록형/기록형목차", "서면 구조, 청구취지, 요건사실을 만든 날"],
        ["선택형", "문항 수와 정답 수를 같이 남기는 객관식 풀이"],
        ["오답복기/재풀이", "틀린 이유를 고치고 다시 푸는 회복 작업"],
        ["암기재현/판례문장", "책을 덮고 답안에 쓸 문장으로 다시 써본 것"],
    ]
    st.dataframe(pd.DataFrame(guide_rows, columns=["유형", "언제 쓰나"]), hide_index=True, use_container_width=True)
    if outputs.empty:
        st.info("아직 출력 기록이 없습니다.")
        return
    c1, c2 = st.columns([0.65, 0.35])
    with c1:
        st.subheader("최근 출력")
        show = outputs.sort_values(["date", "id"], ascending=False).head(150)
        st.dataframe(show, hide_index=True, use_container_width=True)
    with c2:
        st.subheader("삭제")
        rid = st.number_input("삭제할 output id", min_value=0, value=0)
        if st.button("삭제", type="secondary") and rid:
            delete_row("outputs", int(rid))
            st.rerun()

    st.subheader("과목별 출력량")
    chart_df = outputs.groupby(["subject", "output_type"], as_index=False)["quantity"].sum()
    st.bar_chart(chart_df, x="subject", y="quantity", color="output_type")

    st.subheader("오답 원인")
    err = outputs[outputs["error_reason"].fillna("") != ""]
    if not err.empty:
        st.dataframe(err.groupby(["subject", "error_reason"], as_index=False).size().sort_values("size", ascending=False), hide_index=True, use_container_width=True)
    else:
        st.caption("오답 원인이 아직 없습니다.")


def page_mocks():
    st.header("모의고사 & 베이지안 업데이트")
    show_flash_success()
    st.markdown(
        """
        2027년 모의고사는 7월 진단전과 10월 실전예측전으로 나눠 봅니다.
        7월은 합격률 판정이 아니라 약점 발견과 퀘스트 방향 전환, 10월은 본시험 예측 신호로 더 크게 반영합니다.
        단, 이 수치는 실제 합격예측 서비스가 아니라 **내 공부 방향을 조정하기 위한 게임형 계기판**입니다.
        """
    )
    st.subheader("모의고사 후 72시간 복기 체크")
    st.checkbox("성적 입력")
    st.checkbox("과목별 약점 3개 기록")
    st.checkbox("반복오답 10개 등록")
    st.checkbox("사례/기록형 시간초과 원인 기록")
    st.checkbox("2주 내 재풀이 날짜 지정")

    with st.form("mock_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            md = st.date_input("모의고사 날짜", value=date.today())
            mock_name = st.text_input("이름", value="7월 학교/학원 모의고사")
        with c2:
            round_no = st.selectbox("회차", [0, 1, 2, 3], format_func=lambda x: "미지정" if x == 0 else f"{x}차")
            top_percent = st.number_input("전국/학교 상위 %", min_value=0.0, max_value=100.0, value=50.0, step=1.0, help="낮을수록 좋습니다. 예: 상위 35%면 35 입력")
        with c3:
            total_score = st.number_input("총점", min_value=0.0, max_value=2000.0, value=0.0, step=1.0)
            pass_cut = st.number_input("합격권/컷 추정점수", min_value=0.0, max_value=2000.0, value=0.0, step=1.0)
        c4, c5, c6 = st.columns(3)
        with c4:
            selected_score = st.number_input("선택형", min_value=0.0, max_value=500.0, value=0.0, step=0.5)
        with c5:
            essay_score = st.number_input("사례형", min_value=0.0, max_value=1000.0, value=0.0, step=0.5)
        with c6:
            record_score = st.number_input("기록형", min_value=0.0, max_value=500.0, value=0.0, step=0.5)
        note = st.text_area("복기 메모", height=90, placeholder="예: 약점 3개, 반복오답 10개, 시간초과 원인, 2주 내 재풀이 날짜")
        submitted = st.form_submit_button("모의고사 저장", use_container_width=True)
        if submitted:
            insert_mock(
                {
                    "date": md.isoformat(),
                    "mock_name": mock_name,
                    "round_no": int(round_no),
                    "total_score": None if total_score == 0 else float(total_score),
                    "pass_cut": None if pass_cut == 0 else float(pass_cut),
                    "top_percent": None if top_percent == 0 else float(top_percent),
                    "selected_score": None if selected_score == 0 else float(selected_score),
                    "essay_score": None if essay_score == 0 else float(essay_score),
                    "record_score": None if record_score == 0 else float(record_score),
                    "note": note,
                }
            )
            flash_success("모의고사를 저장했습니다")
            st.rerun()

    daily, outputs, mocks, day_scores = reload_data()
    st.subheader("저장된 모의고사")
    if mocks.empty:
        st.info("모의고사 기록이 없습니다.")
    else:
        st.dataframe(mocks.sort_values("date", ascending=False), hide_index=True, use_container_width=True)
        rid = st.number_input("삭제할 mock id", min_value=0, value=0)
        if st.button("모의고사 삭제") and rid:
            delete_row("mocks", int(rid))
            st.rerun()

    st.subheader("합격가능성 계산")
    prior = float(settings.get("prior_probability", "0.70"))
    posterior, updates = estimate_probability(prior, day_scores, mocks)
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Prior", f"{prior*100:.1f}%")
    with c2:
        st.metric("Posterior", f"{posterior*100:.1f}%", f"{(posterior-prior)*100:+.1f}%p")
    with c3:
        last_lr = updates[-1]["lr"] if updates else 1.0
        st.metric("마지막 LR", f"{last_lr}")
    with st.expander("게임 규칙 보기"):
        st.dataframe(probability_examples(prior), hide_index=True, use_container_width=True)
        st.markdown(
            """
            - 7월 모의고사 결과가 나쁘면 소폭 하락하지만, 약점 3개 등록과 2주 내 재풀이가 있으면 회복 가능한 이벤트로 봅니다.
            - 10월 모의고사는 본시험 예측 신호라서 같은 성적이라도 더 크게 반영합니다.
            - 방학 종료, 2학기 개강, 중간/기말고사는 확률 이벤트가 아니라 운영 모드 전환점입니다.
            """
        )
    if updates:
        st.dataframe(pd.DataFrame(updates), hide_index=True, use_container_width=True)


def page_checks():
    st.header("합격수기 기반 체크")
    daily, outputs, mocks, day_scores = reload_data()
    week = weekly_summary(day_scores, outputs)
    flags = build_risk_flags(day_scores, outputs, daily)
    today = date.today()
    recent_start = today - timedelta(days=13)
    recent_outputs = outputs[outputs["date"] >= recent_start] if not outputs.empty else pd.DataFrame()
    recent_daily = day_scores[day_scores["date"] >= recent_start] if not day_scores.empty else pd.DataFrame()

    checks = []
    checks.append((week["mcq_attempted"] >= int(settings.get("weekly_mcq_goal", "200")), "선택형 하방", f"이번 주 {week['mcq_attempted']}문항 / 목표 {settings.get('weekly_mcq_goal')}문항"))
    checks.append((week["heavy_outputs"] >= 4, "사례·기록형 출력", f"이번 주 {week['heavy_outputs']}개 / 최소 4개"))
    checks.append((week["first_task_rate"] >= 0.6, "첫 과제 잠금", f"이번 주 완료율 {week['first_task_rate']*100:.0f}%"))
    checks.append((week["lecture_hours"] <= 12 or week["heavy_outputs"] >= 4, "강의 과잉 방지", f"강의 {week['lecture_hours']}시간, 사례/기록 {week['heavy_outputs']}개"))
    checks.append((week["cbt_hours"] >= 1.0, "CBT 시간감각", f"이번 주 CBT 연습 {week['cbt_hours']}시간"))

    for subject in ["민사법", "형사법", "공법"]:
        count = 0 if recent_outputs.empty else int(recent_outputs[recent_outputs["subject"] == subject]["quantity"].sum())
        checks.append((count > 0, f"{subject} 공백 방지", f"최근 2주 출력 {count}개"))

    err_count = 0 if recent_outputs.empty else int((recent_outputs["error_reason"].fillna("") != "").sum())
    checks.append((err_count >= 5, "오답 원인 기록", f"최근 2주 원인 기록 {err_count}개"))

    if not mocks.empty:
        last_mock = mocks.sort_values("date").iloc[-1]
        has_mock_note = bool(str(last_mock.get("note") or "").strip())
        checks.append((has_mock_note, "모의고사 복기", "마지막 모의고사 복기 메모 있음" if has_mock_note else "마지막 모의고사 복기 메모 없음"))
    else:
        checks.append((False, "모의고사 위치 확인", "모의고사 기록 없음"))

    rows = []
    for ok, name, detail in checks:
        rows.append({"상태": "✅" if ok else "⚠️", "체크": name, "현재": detail, "판단": "유지" if ok else "보완 필요"})
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

    st.subheader("이 체크를 넣은 이유")
    st.markdown(
        """
        - 선택형은 객관식 점수가 원점수로 총점에 반영되므로 매주 문항 수와 정답률을 본다.
        - 사례·기록형은 강의 이해보다 제한시간 내 목차/답안/서면을 만들어내는 훈련이 중요하다.
        - 2024년 제13회부터 논술형 CBT가 시행됐고, 2028년을 목표로 한다면 노트북 답안 시간감각을 주간 체크로 올려야 한다.
        - 합격수기에서 반복되는 핵심은 `기출 패턴`, `선택형 하방`, `기록형 시간관리`, `모의고사 복기`, `자료보다 반복`이다.
        """
    )

    st.subheader("현재 위험 신호")
    for flag in flags:
        st.markdown(f"<div class='warning-card'>{flag}</div>", unsafe_allow_html=True)


def page_review():
    st.header("주간 리뷰")
    daily, outputs, mocks, day_scores = reload_data()
    if day_scores.empty:
        st.info("기록이 쌓이면 주간 리뷰가 생성됩니다.")
        return
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    ds = day_scores[(day_scores["date"] >= week_start) & (day_scores["date"] <= today)]
    outs = outputs[(outputs["date"] >= week_start) & (outputs["date"] <= today)] if not outputs.empty else pd.DataFrame()
    flags = build_risk_flags(day_scores, outputs, daily)

    report_lines = [
        f"# {week_start.isoformat()} 주간 리뷰",
        f"- 평균 합격기여점수: {ds['day_score'].mean():.1f}" if not ds.empty else "- 평균 합격기여점수: 0",
        f"- 자습실 체류: {float(ds['attendance_min'].sum())/60:.1f}시간" if not ds.empty else "- 자습실 체류: 0시간",
        f"- 실제 자습·문제풀이: {float(ds['effective_study_min'].sum())/60:.1f}시간" if not ds.empty else "- 실제 자습·문제풀이: 0시간",
        f"- 인강/학교수업: {float(ds['lecture_min'].sum())/60:.1f}시간" if not ds.empty else "- 인강/학교수업: 0시간",
        f"- 선택형 풀이: {int(ds['mcq_attempted'].sum()) if not ds.empty else 0}문항",
        f"- 사례/기록형 출력: {int(ds['heavy_outputs'].sum()) if not ds.empty else 0}개",
        f"- CBT 답안 연습: {float(ds['cbt_practice_min'].sum())/60:.1f}시간" if not ds.empty else "- CBT 답안 연습: 0시간",
        "",
        "## 위험 신호",
        *[f"- {flag}" for flag in flags],
        "",
        "## 다음 주 원칙",
        "- 월요일 첫 블록은 가장 피하고 싶은 과목으로 시작한다.",
        "- 강의 1개를 들으면 문제/목차/오답 중 하나를 반드시 남긴다.",
        "- 새 자료는 일요일 30분 검토 시간에만 결정한다.",
        "- CBT 답안 작성은 주 1회 이상 한다.",
    ]
    if not outs.empty:
        subject = outs.groupby("subject")["quantity"].sum().sort_values(ascending=False)
        report_lines.insert(8, "- 과목별 출력: " + ", ".join([f"{k} {int(v)}" for k, v in subject.items()]))

    report = "\n".join(report_lines)
    st.text_area("복사용 리뷰", value=report, height=420)
    st.download_button("Markdown 다운로드", report.encode("utf-8"), file_name=f"review_{week_start.isoformat()}.md")


def page_settings():
    st.header("설정 / 백업")
    show_flash_success()
    with st.form("settings"):
        exam_date = st.date_input("시험일", value=datetime.strptime(settings.get("exam_date", "2028-01-11"), "%Y-%m-%d").date())
        mock_july_date = st.date_input("7월 학교/학원 모의고사", value=_setting_date("mock_july_date", "2027-07-15"))
        mock_october_date = st.date_input("10월 법전협/실전 모의고사", value=_setting_date("mock_october_date", "2027-10-15"))
        current_final_start = st.date_input("현재 기말고사 시작", value=_setting_date("current_final_start", "2026-06-10"))
        current_final_end = st.date_input("현재 기말고사 종료", value=_setting_date("current_final_end", "2026-06-21"))
        summer_break_end = st.date_input("여름방학 종료", value=_setting_date("summer_break_end", "2026-08-31"))
        fall_semester_start = st.date_input("2학기 개강", value=_setting_date("fall_semester_start", "2026-09-01"))
        midterm_start = st.date_input("중간고사 시작", value=_setting_date("midterm_start", "2026-10-19"))
        midterm_end = st.date_input("중간고사 종료", value=_setting_date("midterm_end", "2026-10-30"))
        final_start = st.date_input("기말고사 시작", value=_setting_date("final_start", "2026-12-07"))
        fall_semester_end = st.date_input("2학기 종강", value=_setting_date("fall_semester_end", "2026-12-18"))
        winter_break_start = st.date_input("겨울방학 시작", value=_setting_date("winter_break_start", "2026-12-21"))
        spring_2027_start = st.date_input("2027년 1학기 개강", value=_setting_date("spring_2027_start", "2027-03-02"))
        spring_2027_midterm_start = st.date_input("2027년 1학기 중간고사 시작", value=_setting_date("spring_2027_midterm_start", "2027-04-20"))
        spring_2027_midterm_end = st.date_input("2027년 1학기 중간고사 종료", value=_setting_date("spring_2027_midterm_end", "2027-05-01"))
        spring_2027_final_start = st.date_input("2027년 1학기 기말고사 시작", value=_setting_date("spring_2027_final_start", "2027-06-08"))
        spring_2027_final_end = st.date_input("2027년 1학기 기말고사 종료", value=_setting_date("spring_2027_final_end", "2027-06-19"))
        prior = st.slider("초기 합격가능성 prior", 0.05, 0.95, float(settings.get("prior_probability", "0.70")), 0.01)
        daily_min = st.number_input("최소 루틴 점수", min_value=0, max_value=100, value=int(settings.get("daily_min_score", "35")))
        daily_target = st.number_input("목표 루틴 점수", min_value=0, max_value=100, value=int(settings.get("daily_target_score", "70")))
        weekly_output_goal = st.number_input("주간 출력 목표", min_value=0, max_value=100, value=int(settings.get("weekly_output_goal", "12")))
        weekly_mcq_goal = st.number_input("주간 선택형 목표", min_value=0, max_value=1000, value=int(settings.get("weekly_mcq_goal", "200")))
        weekly_cbt_goal = st.number_input("주간 CBT 답안 목표", min_value=0, max_value=20, value=int(settings.get("weekly_cbt_goal", "2")))
        public_delay_hours = st.number_input("공개 지연 시간", min_value=0, max_value=72, value=int(settings.get("public_delay_hours", "24")), help="예: 24로 두면 오늘 기록은 24시간 뒤 공개용 CSV/JSON에 반영됩니다.")
        public_include_evidence_hash = st.checkbox("공개 로그에 증거사진 해시 포함", value=settings.get("public_include_evidence_hash", "false").lower() == "true", help="사진 자체나 경로는 공개하지 않고, 증거가 있었다는 짧은 해시만 내보냅니다.")
        submitted = st.form_submit_button("설정 저장", use_container_width=True)
        if submitted:
            set_setting("exam_date", exam_date.isoformat())
            set_setting("mock_july_date", mock_july_date.isoformat())
            set_setting("mock_october_date", mock_october_date.isoformat())
            set_setting("current_final_start", current_final_start.isoformat())
            set_setting("current_final_end", current_final_end.isoformat())
            set_setting("summer_break_end", summer_break_end.isoformat())
            set_setting("fall_semester_start", fall_semester_start.isoformat())
            set_setting("midterm_start", midterm_start.isoformat())
            set_setting("midterm_end", midterm_end.isoformat())
            set_setting("final_start", final_start.isoformat())
            set_setting("fall_semester_end", fall_semester_end.isoformat())
            set_setting("winter_break_start", winter_break_start.isoformat())
            set_setting("spring_2027_start", spring_2027_start.isoformat())
            set_setting("spring_2027_midterm_start", spring_2027_midterm_start.isoformat())
            set_setting("spring_2027_midterm_end", spring_2027_midterm_end.isoformat())
            set_setting("spring_2027_final_start", spring_2027_final_start.isoformat())
            set_setting("spring_2027_final_end", spring_2027_final_end.isoformat())
            set_setting("prior_probability", prior)
            set_setting("daily_min_score", daily_min)
            set_setting("daily_target_score", daily_target)
            set_setting("weekly_output_goal", weekly_output_goal)
            set_setting("weekly_mcq_goal", weekly_mcq_goal)
            set_setting("weekly_cbt_goal", weekly_cbt_goal)
            set_setting("public_delay_hours", public_delay_hours)
            set_setting("public_include_evidence_hash", str(public_include_evidence_hash).lower())
            flash_success("설정을 저장했습니다")
            st.rerun()

    st.subheader("CSV 백업")
    daily, outputs, mocks, day_scores = reload_data()
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.download_button("daily_records.csv", daily.to_csv(index=False).encode("utf-8-sig"), "daily_records.csv")
    with col2:
        st.download_button("outputs.csv", outputs.to_csv(index=False).encode("utf-8-sig"), "outputs.csv")
    with col3:
        st.download_button("mocks.csv", mocks.to_csv(index=False).encode("utf-8-sig"), "mocks.csv")
    with col4:
        st.download_button("day_scores.csv", day_scores.to_csv(index=False).encode("utf-8-sig"), "day_scores.csv")

    st.subheader("실행 포트")
    st.code("streamlit run app.py --server.port 8502", language="powershell")

    st.subheader("GitHub 공개 자동화")
    st.caption("처음 한 번 GitHub 원격 저장소를 연결하면, 맥북이 켜져 있는 동안 매일 07:10에 전날까지의 공개 로그를 push합니다.")
    st.code(
        """git init
git add .gitignore README.md app.py barpassos export_public.py export_static_public.py publish_public.sh publish_public.ps1 run_8502.sh requirements.txt public launchd install_launchd_publish.sh
git commit -m "Initial BarPass OS public dashboard"
git branch -M main
git remote add origin https://github.com/YOUR_ID/YOUR_REPO.git
git push -u origin main
chmod +x publish_public.sh install_launchd_publish.sh
./install_launchd_publish.sh""",
        language="bash",
    )
    st.caption("GitHub Pages는 저장소 Settings > Pages에서 `main` 브랜치의 `/docs` 폴더를 배포 대상으로 선택하세요. `public/`은 생성 원본이고, publish 스크립트가 `docs/`로 복사합니다.")


PAGES = {
    "Dashboard": page_dashboard,
    "Public Dashboard": page_public_dashboard,
    "Public Preview": page_public_preview,
    "Today": page_today,
    "Quick Input": page_quick,
    "Outputs": page_outputs,
    "Mocks/Bayes": page_mocks,
    "Coach Checks": page_checks,
    "Weekly Review": page_review,
    "Settings": page_settings,
}

st.sidebar.title("⚖️ BarPass OS")
st.sidebar.caption("출력 중심 변시 트래커 · port 8502")
page = st.sidebar.radio("메뉴", list(PAGES.keys()))
st.sidebar.divider()
st.sidebar.markdown("**오늘 원칙**")
st.sidebar.write("강의보다 출력. 자료보다 오답. 불안보다 최소 루틴.")
st.sidebar.markdown("<span class='badge'>자습</span><span class='badge'>CBT</span><span class='badge'>오답</span>", unsafe_allow_html=True)
PAGES[page]()
