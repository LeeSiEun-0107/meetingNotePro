from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import config, errors, models  # noqa: F401  (models: 테이블 등록)
from .db import Base, engine
from .routers import activities, auth, comments, meetings, teams, todos, upload

FRONTEND = config.ROOT / "frontend"

TAGS = [
    {"name": "Auth", "description": "가입 · 로그인 · 내 정보. 로그인 응답의 token 을 우측 위 Authorize 에 넣으면 아래 API 를 바로 호출해 볼 수 있다"},
    {"name": "Team", "description": "팀 · 초대코드 · 멤버"},
    {"name": "Meeting", "description": "회의록 · 녹취 업로드"},
    {"name": "Todo", "description": "할 일 칸반"},
    {"name": "Comment", "description": "회의록 댓글"},
    {"name": "Activity", "description": "활동 기록"},
]


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)
    yield


app = FastAPI(
    title="MeetingNote Pro API",
    description="팀이 함께 쓰는 회의록. API 26개. 오류는 항상 `{code, msg}`.",
    version="0.1.0",
    openapi_tags=TAGS,
    docs_url="/docs",  # Swagger UI
    redoc_url=None,
    lifespan=lifespan,
)
errors.install(app)

for r in (auth.router, teams.router, meetings.router, upload.router, todos.router,
          comments.router, activities.router):
    app.include_router(r)


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/login.html")


# /docs · /openapi.json · /api/* 는 위에서 먼저 잡히고, 나머지는 정적 파일로 간다
if FRONTEND.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="frontend")
