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


class FreshStaticFiles(StaticFiles):
    """화면 파일을 고쳐도 브라우저가 옛 파일을 계속 쓰지 않도록 매번 최신 여부를 확인하게 한다.
    (Cache-Control 이 없으면 브라우저가 Last-Modified 로 짐작해 한동안 캐시를 그대로 쓴다.
    파일이 그대로면 304 로 가볍게 끝난다.) 미들웨어 대신 응답 헤더만 더해, Vercel 이 정적 파일을
    CDN 으로 올리는 동작을 막지 않는다."""

    def file_response(self, *args, **kwargs):
        resp = super().file_response(*args, **kwargs)
        resp.headers["Cache-Control"] = "no-cache"
        return resp


# /docs · /openapi.json · /api/* 는 위에서 먼저 잡히고, 나머지는 정적 파일로 간다
if FRONTEND.is_dir():
    app.mount("/", FreshStaticFiles(directory=FRONTEND, html=True), name="frontend")
