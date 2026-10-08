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
.venv/Scripts/python -m pytest
```

Gemini 는 부르지 않고 가짜로 바꿔 돌린다. 프런트 규칙 검사와 `isLate` 검사에는 `node` 가 필요하다 (없으면 건너뛴다).

키 없이 브라우저로 화면 흐름을 보려면 Gemini 만 가짜로 바꾼 서버를 쓴다.

```bash
.venv/Scripts/python tests/run_e2e_server.py <임시 DB 경로> 8765     # 8000 이 비어 있으면 포트 생략 가능
```

## 알려둘 것

- 업로드(`/api/upload`)는 로컬에서 서버가 파일을 직접 받는다. 배포(Vercel)의 Blob 직접 업로드는 아직 구현 전이다 (`tasks.md` 4.1 · 4.6)
- Gemini 는 실제 키로 확인했다 (100초 wav 4.19MB 받아쓰기 약 5초, 같은 내용의 mp3 약 4초, 세 항목 구분). 업로드 상한은 5MB 다. 자동 테스트는 Gemini 를 가짜로 대체하고, 실제 호출 테스트는 `REAL_GEMINI=1` 일 때만 돈다
