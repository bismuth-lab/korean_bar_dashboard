# BarPass OS — 변호사시험 동기부여/합격가능성 트래커

Streamlit + SQLite 기반의 로컬 실행 앱입니다. 공부시간보다 **출력물, 오답, 모의고사, CBT 답안연습, 루틴 유지**를 추적합니다.

## 빠른 실행: 포트 8502

### Windows 11 PowerShell
```powershell
cd barpass_os
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py --server.port 8502
```

또는 포함된 스크립트를 실행하세요.
```powershell
cd barpass_os
.\run_8502.ps1
```

실행 정책 오류가 나면 PowerShell을 관리자 권한이 아닌 일반 권한으로 열고 아래를 한 번 실행하세요.
```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

### macOS / Linux
```bash
cd barpass_os
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py --server.port 8502
```

또는:
```bash
./run_8502.sh
```

`.streamlit/config.toml`에도 기본 포트 8502가 설정되어 있습니다.

## 데이터 저장 위치

- SQLite DB: `barpass_os.db`
- 인증 사진/답안 사진: `evidence/`

로컬 저장 앱입니다. 민감한 사진을 올릴 때는 개인 PC에서만 사용하세요.

## 중요한 입력 원칙

- `입실/퇴실`: 자습실/열람실 출근 루틴 확인용입니다.
- `실제 자습/문제풀이`: 강의와 학교수업을 제외한 직접 공부 시간입니다. 답안작성, 선택형, 오답, 암기재현이 여기에 들어갑니다.
- `인강/학교수업`: 자습은 포함하지 않습니다. 수동 입력시간을 감시하는 용도입니다.
- `CBT 답안 연습`: 노트북으로 사례형/기록형을 본시험처럼 쓴 시간입니다.
- `출력/문제풀이`: 정답을 보기 전에 네가 만든 답안, 목차, 기록형 서면, 선택형 풀이, 오답복기, 암기재현입니다.

## 추적 철학

- 공부시간은 보조지표입니다.
- 본지표는 답안/목차/기록형/선택형/오답/암기 재현입니다.
- 합격률 추정은 실제 예측기가 아니라, 베이지안 사고를 빌린 **동기부여·위험관리용 게임 지표**입니다.
- 하루 기록은 확률을 작게 움직이고, 7월·10월 모의고사는 확률을 크게 움직입니다.

## Codex로 확장할 때 추천 작업

1. `Coach Checks`의 체크 항목을 사용자의 로스쿨 커리큘럼과 선택법에 맞게 세분화하기
2. 캘린더 히트맵을 월별 구분선이 있는 GitHub 스타일 CSS 컴포넌트로 바꾸기
3. 모의고사 성적표 CSV import 기능 추가
4. 모바일 `Quick Input`을 더 작고 빠른 UI로 다듬기
5. 오답 원인별 자동 코칭 리포트 강화

## Public Accountability Export

Public Dashboard 페이지를 열면 공개용 요약 파일이 자동 생성됩니다.

- `public/public_log.csv`
- `public/public_summary.json`

공개 로그에는 장소, 기분/불안/수면, 답안 사진 경로, 오답 상세 메모를 넣지 않습니다. 기본 공개 항목은 날짜, 앉은 시간, 떠난 시간, 착석시간, 실제 자습시간, 인강/수업시간, CBT 연습시간, 출력 개수, 선택형 문항 수, 첫 과제 완료 여부, 합격기여점수, 수정/지연입력 표시입니다.

정적 GitHub Pages용 HTML은 아래 명령으로 생성합니다.

```powershell
.\.venv\Scripts\python.exe export_static_public.py
```

생성되는 원본 파일은 `public/index.html`입니다. GitHub Pages의 branch 배포 화면은 보통 `/public`을 직접 선택할 수 없으므로, publish 스크립트가 같은 파일을 `docs/`에도 복사합니다. GitHub Pages에서는 `docs` 폴더를 배포 대상으로 선택하세요.

공개 파일 생성부터 GitHub push까지 한 번에 하려면 아래 스크립트를 사용합니다.

```powershell
.\publish_public.ps1
```

macOS에서는:

```bash
chmod +x publish_public.sh
./publish_public.sh
```

맥북에서 매일 자동 실행하려면 `crontab -e`에 아래처럼 추가할 수 있습니다.

```cron
0 23 * * * cd /path/to/barpass_os_streamlit_v2_8502 && ./publish_public.sh >> public_publish.log 2>&1
```

또는 포함된 `launchd` 설정을 설치할 수 있습니다. 이 방식은 macOS에서 더 자연스럽고, 매일 07:10에 `publish_public.sh`를 실행합니다.

```bash
chmod +x publish_public.sh install_launchd_publish.sh
./install_launchd_publish.sh
```

처음 GitHub 저장소를 연결할 때는 아래 순서로 진행하세요.

```bash
git init
git add .gitignore README.md app.py barpassos export_public.py export_static_public.py publish_public.sh publish_public.ps1 run_8502.sh requirements.txt public launchd install_launchd_publish.sh
git commit -m "Initial BarPass OS public dashboard"
git branch -M main
git remote add origin https://github.com/YOUR_ID/YOUR_REPO.git
git push -u origin main
```

GitHub Pages는 저장소 `Settings > Pages`에서 `main` 브랜치의 `/docs` 폴더를 배포 대상으로 선택하세요. 앱 설정의 `공개 지연 시간` 기본값이 24시간이라 오늘 기록은 다음날 공개 파일에 반영됩니다.

GitHub에는 `public/`만 공개 repo 또는 Pages 배포 브랜치에 올리는 것을 권장합니다. `barpass_os.db`, `evidence/`, `.venv/`는 공개 repo에 올리지 마세요.
