# Codex 작업 지시서

이 저장소는 Streamlit + SQLite로 만든 개인용 변호사시험 동기부여 앱입니다. 기본 실행 포트는 8502입니다.

## 반드시 지킬 것

- 한국어 UI 라벨을 유지한다.
- 민감한 답안 사진/DB를 외부로 전송하지 않는다.
- Bayesian warning text 또는 "게임형 계기판" 설명을 삭제하지 않는다.
- 기존 SQLite 사용자의 DB가 깨지지 않도록 migration을 보존한다.
- 수정 후 다음을 실행한다.

```bash
python -m py_compile app.py barpassos/*.py
streamlit run app.py --server.port 8502
```

## Task 1 — UI polishing
Dashboard를 더 예쁜 생산성 앱처럼 다듬어라. 카드, 히트맵, 위험 신호, 합격가능성 설명이 한눈에 들어오게 한다.

## Task 2 — True GitHub heatmap
Plotly heatmap을 HTML/CSS 기반의 더 GitHub스러운 calendar component로 교체한다. 점수 bins: 0, 1-34, 35-59, 60-79, 80-100.

## Task 3 — Mobile quick input
`Quick Input`을 60초 이내 입력에 맞게 더 줄인다. 날짜, 입퇴실, 실제 자습분, 첫 과제, 첫 과제 완료, 출력 1개, 선택형 문항/정답, 증거사진만 남긴다.

## Task 4 — Mock import
CSV import for mock exam scores. Expected columns: date, mock_name, round_no, total_score, pass_cut, top_percent, selected_score, essay_score, record_score, note.

## Task 5 — Weakness guard
사용자 성향에 맞게 회피행동 감지 기능을 강화한다. 특히 자료쇼핑, 계획리셋, 강의만 듣기, 사례형/기록형 회피가 2주 이상 반복될 때 경고한다.

## Task 6 — Output taxonomy
출력 유형을 본시험 구조에 맞게 더 세분화한다. 예: 민사 기록형 청구취지, 요건사실, 항변/재항변, 공법 청구유형, 형사 기록형 공소장/변론요지 등.
