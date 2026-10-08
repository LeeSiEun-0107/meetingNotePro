# Proposal

## Why

팀이 회의 녹취를 올리면 요약 · 결정사항 · 할 일로 나누고, 할 일을 칸반으로 추적하며, 댓글과 활동 기록을 남기는 웹앱이 없다. 프로그램 정의서(`docs/MeetingNote Pro_프로그램정의.pdf`)와 스토리보드 62개 상태, 확정 퍼블리싱 HTML(`publish/`)이 이미 있어 구현 입력이 갖춰졌다.

## What Changes

- FastAPI 백엔드를 만든다 (`backend/`). 로컬은 SQLite, `DATABASE_URL` 이 있으면 Neon Postgres. API 26개, DB 7테이블
- Vanilla JS 프론트엔드를 만든다 (`frontend/`). `publish/` 의 6개 화면과 `theme.js` 를 그대로 구현하고, 가짜 데이터와 STATE 바와 API 설명 줄은 빼고 실제 API 호출로 바꾼다
- 녹취(mp3 · wav, 25MB 이하)를 Gemini 로 받아쓰고, 본문을 요약 · 결정사항 · 할 일 세 항목으로 나눈다
- 업로드는 브라우저가 Vercel Blob 에 직접 올리고 서버는 그 주소로 받아쓰기만 한다. 파일은 보관하지 않는다
- Vercel + Neon 에 배포한다
- 범위 외: 실시간 녹음 · 화자 자동 구분 · 외부 연동 · owner/member 외 권한 등급 · 분할 업로드 · 푸시 알림

### 확정한 결정

1. 가입은 팀 없이 끝난다. 소속 팀이 없으면 팀 설정 화면(F-02)에서 팀을 만들거나 초대코드로 합류한다
2. 업로드는 25MB 를 유지한다 (Vercel 함수 본문 한도를 피하려고 Blob 직접 업로드)
3. 기한 지남은 화면이 판정한다. `어제` · `지난 주` · `지난 달` 과 `N월 N일`(연도는 회의록 `met_at`)을 쓰고 완료 항목은 제외한다
4. 확정 HTML 을 그대로 구현한다. 디자인 규칙과 어긋난 곳은 design.md 의 열린 항목으로만 둔다
5. 스토리보드에 없는 오류 상태는 공통 red 알림으로 처리하고, 401 은 로그인 화면으로 보낸다
6. 비밀번호를 바꿀 때 현재 비밀번호를 받는다 (틀리면 401 `UNAUTHORIZED`). `profile.html` 에 입력칸 하나를 더한다
7. 회의록 목록과 상세 응답에 올린 사람 id `author_id` 를 더한다 (화면의 수정 · 삭제 가능 여부 판정용)

## Capabilities

### New Capabilities
- `user-auth`: 회원가입 · 로그인 · JWT(24h) · 내 정보 조회와 수정 · 로그아웃
- `team`: 팀 생성 · 목록 · 초대코드 발급과 재발급 · 합류 · 멤버 목록 · 팀 이름 변경(owner)
- `meeting-notes`: 녹취 업로드와 받아쓰기 · 세 항목 구분 · 회의록 CRUD · 검색(제목 · 참석자 · 기간)
- `todo-board`: 대기 · 진행 · 완료 3열 칸반 · 상태 변경 · 담당자 배정 · 기한 지남 표시 · 삭제(owner)
- `meeting-comments`: 회의록 댓글 작성 · 목록 · 삭제(쓴 사람과 owner)
- `activity-log`: 팀 활동 · 내 활동 (kind 5종)

### Modified Capabilities

없음. 현재 `openspec/specs/` 가 비어 있다.

## Impact

- 새 폴더: `backend/` · `frontend/`. 기존 `publish/` 는 고치지 않는다
- 외부 서비스: Google Gemini API, Neon Postgres, Vercel(함수 · Blob)
- 환경변수: 로컬 `.env` 는 `GEMINI_API_KEY` · `GEMINI_MODEL` 둘. 배포 환경변수는 `JWT_SECRET` · `DATABASE_URL` · Blob 토큰이 더해진다
- `.env` 는 `.gitignore` 로 제외한다 (이미 반영됨)
