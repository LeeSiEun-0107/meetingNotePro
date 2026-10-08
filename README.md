# MeetingNote Pro

팀이 함께 쓰는 회의록. 녹취를 받아쓴 본문을 요약 · 결정사항 · 할 일로 나누고, 할 일은 칸반으로 추적한다.
설계 문서는 `docs/`, 확정 디자인은 `publish/`, 구현 명세는 `openspec/changes/add-mvp-core/` 에 있다.

## 폴더

| 폴더 | 내용 |
|---|---|
| `backend/` | FastAPI (API 26개, SQLAlchemy) |
| `frontend/` | Vanilla JS + Tailwind CDN. `publish/` 의 6개 화면을 실제 API 에 연결한 것 |
| `publish/` | 확정된 디자인 구현체 (고치지 않는다) |
| `docs/` | 프로그램 정의 · 스토리보드 · 디자인 시스템 |

## 로컬 실행

Python 3.11 이상이 필요하다.

```bash
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt     # macOS/리눅스는 .venv/bin/python
cp ../.env.example ../.env                                        # 그리고 GEMINI_API_KEY 를 채운다
.venv/Scripts/python -m uvicorn app.main:app --reload             # http://127.0.0.1:8000
```

- 화면: `http://127.0.0.1:8000/` (로그인 화면으로 이동)
- **Swagger UI: `http://127.0.0.1:8000/docs`** — 가입 또는 로그인 응답의 `token` 을 복사해 오른쪽 위 `Authorize` 에 붙여 넣으면 보호된 API 를 화면에서 바로 호출해 볼 수 있다
- `DATABASE_URL` 이 없으면 프로젝트 루트의 `meetingnote.db`(SQLite)를 쓴다. 있으면 Postgres(Neon)

## 환경변수

| 이름 | 어디에 | 설명 |
|---|---|---|
| `GEMINI_API_KEY` | 로컬 `.env` · 배포 | 받아쓰기와 세 항목 구분에 쓰는 Gemini 키 |
| `GEMINI_MODEL` | 로컬 `.env` · 배포 | 기본 `gemini-3.1-flash-lite` |
| `JWT_SECRET` | 배포에만 | 로컬은 개발용 기본값이 있다. **배포에서는 반드시 덮어쓴다** |
| `DATABASE_URL` | 배포 (Neon 연결 시 자동) | 있으면 Postgres, 없으면 SQLite |

`.env` 는 git 에 올리지 않는다 (`.gitignore`). 저장소가 공개이므로 키를 코드나 문서에 적지 않는다.

## 테스트

```bash
cd backend
.venv/Scripts/python -m pytest                                       # 전체 (1단계 + 2단계)
.venv/Scripts/python -m pytest tests --ignore=tests/stage2_integration   # 1단계만
.venv/Scripts/python -m pytest tests/stage2_integration                  # 2단계만
```

| 단계 | 무엇을 | 어떻게 |
|---|---|---|
| 1단계 | API 26개, 권한, 오류 코드, 문서 규칙, 프런트 규칙(클래스 보존 · 매핑표 대조) | 메모리 DB, Gemini 는 가짜 |
| 2단계 | 사용 시나리오 4종, 권한, 정원 6명, 동시 50명, 성능 기준(API 100ms · 가입/로그인 250ms), 서버 재시작 뒤 데이터 유지 | 실제 uvicorn 프로세스 + 파일 DB + HTTP |

프런트 규칙 검사와 `isLate` 검사에는 `node` 가 필요하다 (없으면 건너뛴다).

**실제 Gemini 로 돌리기** (키와 비용이 들어서 기본은 건너뛴다):

```bash
REAL_GEMINI=1 REAL_WAV=C:\경로\회의_녹음.wav pytest tests/test_real_audio.py tests/stage2_integration/test_real_gemini.py
```

키 없이 브라우저로 화면 흐름을 보려면 Gemini 만 가짜로 바꾼 서버를 쓴다.

```bash
.venv/Scripts/python tests/run_e2e_server.py <임시 DB 경로> 8765
```

## 알려둘 것

- 업로드(`/api/upload`)는 로컬에서 서버가 파일을 직접 받는다. 배포(Vercel)의 Blob 직접 업로드는 아직 구현 전이다 (`tasks.md` 4.1 · 4.6)
- Gemini 는 실제 키로 확인했다 (100초 wav 4.19MB 받아쓰기 약 5초, 같은 내용의 mp3 약 4초, 세 항목 구분). 업로드 상한은 4.5MB 다. 자동 테스트는 Gemini 를 가짜로 대체하고, 실제 호출 테스트는 `REAL_GEMINI=1` 일 때만 돈다

## Vercel 배포

설정 파일은 준비되어 있다 (`pyproject.toml` 의 `[tool.vercel]`, `vercel.json`, `.vercelignore`). 계정이 필요한 단계는 직접 한다.

1. Vercel 에서 이 저장소(GitHub)를 가져온다. Framework 는 FastAPI(자동 감지)
2. **Storage 에서 Neon Postgres 를 연결한다.** `DATABASE_URL` 이 자동으로 들어간다
3. Environment Variables 에 넣는다 (모두 Production):

| 이름 | 값 |
|---|---|
| `GEMINI_API_KEY` | Gemini 키 |
| `GEMINI_MODEL` | `gemini-3.1-flash-lite` |
| `JWT_SECRET` | 길고 무작위인 문자열 (예: `python -c "import secrets; print(secrets.token_urlsafe(48))"`) |

4. 배포 후 `https://<프로젝트>.vercel.app/` 에서 가입 · 팀 만들기 · 회의록 저장을 해 보고, `/docs` 로 API 를 호출해 본다

`JWT_SECRET` 이나 `DATABASE_URL` 이 없으면 앱이 일부러 기동을 거부한다 (공개된 기본 비밀키 사용과 읽기 전용 디스크의 SQLite 를 막는 장치).
Vercel 함수 요청 본문 한도가 4.5MB 라 업로드 상한도 4.5MB 다.
- **폰트:** 사용자 요청으로 Mac 폰트 스타일을 쓴다. Mac 에서는 시스템 폰트(San Francisco · Apple SD Gothic Neo)를 그대로 쓰고, 그 밖의 기기는 SF 와 닮은 오픈소스 폰트 Pretendard(jsDelivr CDN)로 대신한다. SF 는 라이선스상 웹으로 배포할 수 없다. `frontend/theme.js` 의 폰트 줄과 로더만 `publish/theme.js` 와 다르고, `publish/` 는 고치지 않았다
