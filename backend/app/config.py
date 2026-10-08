"""환경변수. 로컬은 프로젝트 루트의 .env, 배포는 Vercel 환경변수에서 읽는다."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MAX_TEAM_MEMBERS = 6
MAX_COMMENT_LEN = 500
ACTIVITY_LIMIT = 50
TOKEN_HOURS = 24


def gemini_api_key() -> str:
    return os.getenv("GEMINI_API_KEY", "")


def gemini_model() -> str:
    return os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")


def jwt_secret() -> str:
    # 배포에서는 반드시 환경변수로 덮는다. 로컬 기본값은 개발 전용
    return os.getenv("JWT_SECRET", "dev-only-secret-change-me-0123456789abcdef")


def database_url() -> str:
    """DATABASE_URL 이 있으면 Postgres(Neon), 없으면 로컬 SQLite 한 줄 분기."""
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        return f"sqlite:///{ROOT / 'meetingnote.db'}"
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url
