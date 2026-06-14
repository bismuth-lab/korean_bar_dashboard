from __future__ import annotations

import csv
import html
import json
from datetime import date, datetime, timedelta
from pathlib import Path


PUBLIC_DIR = Path("public")
LOG_PATH = PUBLIC_DIR / "public_log.csv"
SUMMARY_PATH = PUBLIC_DIR / "public_summary.json"
INDEX_PATH = PUBLIC_DIR / "index.html"


def _read_rows() -> list[dict[str, str]]:
    if not LOG_PATH.exists():
        return []
    with LOG_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _read_summary() -> dict[str, object]:
    if not SUMMARY_PATH.exists():
        return {}
    return json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))


def _score_class(score: int) -> str:
    if score <= 0:
        return "s0"
    if score < 20:
        return "s1"
    if score < 40:
        return "s2"
    if score < 60:
        return "s3"
    if score < 75:
        return "s4"
    return "s5"


def _time_to_minutes(value: str | None) -> int | None:
    if not value:
        return None
    try:
        parsed = datetime.strptime(str(value).strip(), "%H:%M")
    except ValueError:
        return None
    return parsed.hour * 60 + parsed.minute


def _attendance_minutes(checkin: str | None, checkout: str | None) -> int:
    start = _time_to_minutes(checkin)
    end = _time_to_minutes(checkout)
    if start is None or end is None:
        return 0
    if end < start:
        end += 24 * 60
    return max(0, end - start)


def _heatmap(rows: list[dict[str, str]]) -> str:
    score_by_date = {row["date"]: int(float(row.get("score") or 0)) for row in rows}
    end = date.today()
    start = end - timedelta(days=180)
    start = start - timedelta(days=start.weekday())
    days = []
    cursor = start
    while cursor <= end:
        days.append(cursor)
        cursor += timedelta(days=1)
    cells = []
    for day in days:
        score = score_by_date.get(day.isoformat(), 0)
        cells.append(
            f"<span class='cell {_score_class(score)}' title='{day.isoformat()} score {score}'></span>"
        )
    return "<div class='heatmap'>" + "".join(cells) + "</div>"


def _recent_table(rows: list[dict[str, str]]) -> str:
    recent = rows[-7:]
    body = []
    for row in recent:
        first = "완료" if str(row.get("first_task_done")).lower() == "true" else "미완료"
        body.append(
            "<tr>"
            f"<td>{html.escape(row.get('date', ''))}</td>"
            f"<td>{html.escape(row.get('checkin', ''))}</td>"
            f"<td>{html.escape(row.get('checkout', ''))}</td>"
            f"<td>{float(row.get('seat_hours') or 0):.1f}h</td>"
            f"<td>{float(row.get('self_study_hours') or 0):.1f}h</td>"
            f"<td>{int(float(row.get('outputs_count') or 0))}</td>"
            f"<td>{int(float(row.get('mcq_count') or 0))}</td>"
            f"<td>{first}</td>"
            f"<td>{int(float(row.get('score') or 0))}</td>"
            "</tr>"
        )
    return (
        "<table><thead><tr><th>날짜</th><th>앉음</th><th>떠남</th><th>착석</th><th>자습</th><th>출력</th>"
        "<th>선택형</th><th>첫 과제</th><th>점수</th></tr></thead><tbody>"
        + "".join(body)
        + "</tbody></table>"
    )


def _recent_attendance(rows: list[dict[str, str]]) -> str:
    recent = rows[-7:]
    day_start = 5 * 60
    day_span = 19 * 60
    body = []
    for row in recent:
        checkin = row.get("checkin") or ""
        checkout = row.get("checkout") or ""
        start = _time_to_minutes(checkin)
        end = _time_to_minutes(checkout)
        duration = _attendance_minutes(checkin, checkout)
        if start is None or end is None:
            rail = "<div class='attendance-rail'></div>"
            hours = "-"
        else:
            if end < start:
                end += 24 * 60
            left = max(0, min(100, (start - day_start) / day_span * 100))
            right = max(left, min(100, (end - day_start) / day_span * 100))
            rail = (
                "<div class='attendance-rail'>"
                f"<div class='attendance-fill' style='left:{left:.2f}%;width:{right-left:.2f}%;'></div>"
                "</div>"
            )
            hours = f"{duration / 60:.1f}h"
        body.append(
            "<div class='attendance-row'>"
            f"<div class='attendance-date'>{html.escape(row.get('date', ''))}</div>"
            f"<div class='attendance-time'>{html.escape(checkin or '-')}</div>"
            f"{rail}"
            f"<div class='attendance-time'>{html.escape(checkout or '-')}</div>"
            f"<div class='attendance-hours'>{hours}</div>"
            "</div>"
        )
    return "<div class='attendance-list'>" + "".join(body) + "</div>"


def _risk_list(summary: dict[str, object]) -> str:
    risks = summary.get("risk_signals") or []
    risks_ja = summary.get("risk_signals_ja") or []
    if not isinstance(risks, list):
        risks = []
    if not isinstance(risks_ja, list):
        risks_ja = []
    items = ""
    for idx, risk in enumerate(risks):
        ja = risks_ja[idx] if idx < len(risks_ja) else ""
        items += (
            "<li>"
            f"<strong>{html.escape(str(risk))}</strong>"
            + (f"<span>{html.escape(str(ja))}</span>" if ja else "")
            + "</li>"
        )
    return f"<ul class='risks'>{items}</ul>"


def build_html(rows: list[dict[str, str]], summary: dict[str, object]) -> str:
    generated = summary.get("generated_at") or datetime.now().isoformat(timespec="seconds")
    notice_ko = str(summary.get("notice", "정확한 장소와 답안 내용은 비공개이며, 매일의 루틴과 출력량만 기록합니다."))
    notice_ja = str(summary.get("notice_ja", "正確な場所と答案の内容は非公開にし、毎日のルーティンとアウトプット量だけを記録します。"))
    status = str(summary.get("today_status", "기록 대기"))
    status_ja = str(summary.get("today_status_ja", "記録待ち"))
    next_milestone = str(summary.get("next_milestone", ""))
    next_milestone_ja = str(summary.get("next_milestone_ja", ""))
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>BarPass Public Log</title>
  <style>
    :root {{ color-scheme: light; --ink:#111827; --muted:#667085; --line:#e5e7eb; }}
    body {{ margin:0; font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color:var(--ink); background:#f8fafc; }}
    main {{ max-width:980px; margin:0 auto; padding:32px 18px 48px; }}
    h1 {{ margin:0 0 8px; font-size:32px; }}
    h2 {{ margin:28px 0 12px; font-size:20px; }}
    p {{ color:var(--muted); }}
    .ja {{ color:var(--muted); font-size:14px; margin-top:4px; }}
    .hero-note {{ max-width:760px; }}
    .accountability {{ margin-top:16px; padding:14px 16px; background:#fff7ed; border:1px solid #fed7aa; border-radius:8px; }}
    .accountability strong {{ display:block; margin-bottom:4px; }}
    .cards {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(180px, 1fr)); gap:12px; margin-top:20px; }}
    .card {{ background:white; border:1px solid var(--line); border-radius:8px; padding:16px; }}
    .label {{ color:var(--muted); font-size:13px; }}
    .value {{ font-size:26px; font-weight:800; margin-top:6px; }}
    .heatmap {{ display:grid; grid-template-rows:repeat(7, 13px); grid-auto-flow:column; gap:4px; overflow-x:auto; padding:14px; background:white; border:1px solid var(--line); border-radius:8px; }}
    .cell {{ width:13px; height:13px; border-radius:3px; background:#ebedf0; }}
    .s1 {{ background:#d8f3dc; }} .s2 {{ background:#95d5b2; }} .s3 {{ background:#52b788; }} .s4 {{ background:#2d6a4f; }} .s5 {{ background:#1b4332; }}
    .attendance-list {{ display:flex; flex-direction:column; gap:10px; margin: 8px 0 14px; padding:14px; background:white; border:1px solid var(--line); border-radius:8px; }}
    .attendance-row {{ display:grid; grid-template-columns:86px 54px minmax(130px,1fr) 54px 48px; gap:10px; align-items:center; font-size:14px; }}
    .attendance-date {{ font-weight:800; }}
    .attendance-time {{ color:#475467; font-variant-numeric:tabular-nums; }}
    .attendance-rail {{ height:14px; border-radius:999px; background:#f1f5f9; position:relative; overflow:hidden; border:1px solid #e2e8f0; }}
    .attendance-fill {{ position:absolute; top:0; bottom:0; border-radius:999px; background:#ef4444; }}
    .attendance-hours {{ text-align:right; font-weight:800; color:#991b1b; font-variant-numeric:tabular-nums; }}
    @media (max-width: 640px) {{ .attendance-row {{ grid-template-columns:70px 48px minmax(80px,1fr) 48px; }} .attendance-hours {{ display:none; }} }}
    .risks {{ background:white; border:1px solid var(--line); border-radius:8px; padding:16px 28px; }}
    .risks li {{ margin:8px 0; }}
    .risks span {{ display:block; color:var(--muted); font-size:14px; margin-top:3px; }}
    table {{ width:100%; border-collapse:collapse; background:white; border:1px solid var(--line); border-radius:8px; overflow:hidden; }}
    th, td {{ padding:10px 12px; border-bottom:1px solid var(--line); text-align:left; }}
    th {{ font-size:13px; color:var(--muted); background:#f9fafb; }}
    footer {{ margin-top:28px; color:var(--muted); font-size:13px; }}
  </style>
</head>
<body>
<main>
  <h1>BarPass Public Log</h1>
  <p class="hero-note">{html.escape(notice_ko)}</p>
  <p class="ja">{html.escape(notice_ja)}</p>
  <div class="accountability">
    <strong>공개 목적 / 公開の目的</strong>
    <div>누군가에게 감시받기보다, 도망치면 빈칸이 남는 구조를 만들기 위한 로그입니다.</div>
    <div class="ja">誰かに監視されるためではなく、逃げた日には空白が残る仕組みを作るためのログです。</div>
  </div>
  <section class="cards">
    <div class="card"><div class="label">오늘의 상태 / 今日の状態</div><div class="value">{html.escape(status)}</div><div class="ja">{html.escape(status_ja)}</div></div>
    <div class="card"><div class="label">연속 기록 / 連続記録</div><div class="value">{summary.get("streak_days", 0)}일</div><div class="ja">{summary.get("streak_days", 0)}日</div></div>
    <div class="card"><div class="label">이번 주 합격기여점수 / 今週の貢献点</div><div class="value">{summary.get("weekly_score", 0)}점</div><div class="ja">{summary.get("weekly_score", 0)}点</div></div>
    <div class="card"><div class="label">다음 보스 / 次のボス</div><div class="value">{html.escape(str(summary.get("next_milestone_d_day", "")))}</div><p>{html.escape(next_milestone)}</p><div class="ja">{html.escape(next_milestone_ja)}</div></div>
  </section>
  <h2>GitHub식 히트맵 / GitHub風ヒートマップ</h2>
  {_heatmap(rows)}
  <h2>최근 7일 공개 로그 / 直近7日間の公開ログ</h2>
  {_recent_attendance(rows)}
  {_recent_table(rows)}
  <h2>이번 주 요약 / 今週の要約</h2>
  <section class="cards">
    <div class="card"><div class="label">착석 / 着席</div><div class="value">{summary.get("weekly_seat_hours", 0)}h</div></div>
    <div class="card"><div class="label">실제 자습 / 実学習</div><div class="value">{summary.get("weekly_self_study_hours", 0)}h</div></div>
    <div class="card"><div class="label">사례/기록 출력 / 答案アウトプット</div><div class="value">{summary.get("weekly_outputs", 0)}개</div></div>
    <div class="card"><div class="label">선택형 / 短答</div><div class="value">{summary.get("weekly_mcq", 0)}문항</div></div>
  </section>
  <h2>위험 신호 / リスクサイン</h2>
  {_risk_list(summary)}
  <footer>Generated at {html.escape(str(generated))}</footer>
</main>
</body>
</html>
"""


def main() -> None:
    PUBLIC_DIR.mkdir(exist_ok=True)
    INDEX_PATH.write_text(build_html(_read_rows(), _read_summary()), encoding="utf-8")
    print(f"Wrote {INDEX_PATH}")


if __name__ == "__main__":
    main()
