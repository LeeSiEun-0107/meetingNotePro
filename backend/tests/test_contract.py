"""문서의 고정 규칙: API 26개, 오류 코드, Swagger UI, 저장소 위생."""
import re
import subprocess
from pathlib import Path

from app import config, errors
from app.main import app

ROOT = config.ROOT

EXPECTED = {
    ("POST", "/api/auth/signup"), ("POST", "/api/auth/login"), ("GET", "/api/auth/me"),
    ("PUT", "/api/auth/me"), ("POST", "/api/auth/logout"),
    ("POST", "/api/teams"), ("GET", "/api/teams"), ("POST", "/api/teams/join"),
    ("GET", "/api/teams/{team_id}/members"), ("PUT", "/api/teams/{team_id}/code"), ("PUT", "/api/teams/{team_id}"),
    ("POST", "/api/teams/{team_id}/meetings"), ("GET", "/api/teams/{team_id}/meetings"),
    ("GET", "/api/meetings/{meeting_id}"), ("PUT", "/api/meetings/{meeting_id}"),
    ("DELETE", "/api/meetings/{meeting_id}"), ("POST", "/api/upload"),
    ("GET", "/api/teams/{team_id}/todos"), ("PUT", "/api/todos/{todo_id}"),
    ("GET", "/api/me/todos"), ("DELETE", "/api/todos/{todo_id}"),
    ("POST", "/api/meetings/{meeting_id}/comments"), ("GET", "/api/meetings/{meeting_id}/comments"),
    ("DELETE", "/api/comments/{comment_id}"),
    ("GET", "/api/teams/{team_id}/activities"), ("GET", "/api/me/activities"),
}


def test_exactly_the_26_documented_endpoints():
    ops = {(m.upper(), p) for p, v in app.openapi()["paths"].items() for m in v if m in ("get", "post", "put", "delete")}
    assert len(EXPECTED) == 26
    assert ops == EXPECTED


def test_swagger_ui_and_openapi_are_served_not_shadowed_by_static_files(client):
    r = client.get("/docs")
    assert r.status_code == 200 and "swagger-ui" in r.text.lower()
    assert client.get("/openapi.json").status_code == 200


def test_swagger_has_bearer_authorize_button():
    schemes = app.openapi()["components"]["securitySchemes"]
    assert any(s.get("type") == "http" and s.get("scheme") == "bearer" for s in schemes.values())


def test_login_token_works_as_swagger_bearer(client):
    r = client.post("/api/auth/signup", json={"email": "s@example.com", "password": "password1", "name": "스웨거"})
    token = r.json()["token"]
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200


def test_root_redirects_to_login_page(client):
    r = client.get("/", follow_redirects=False)
    assert r.status_code in (302, 307) and r.headers["location"] == "/login.html"


def test_unknown_api_path_is_code_msg(client):
    r = client.get("/api/nope")
    assert r.status_code == 404 and set(r.json()) == {"code", "msg"}


def test_error_codes_are_the_documented_15():
    assert len(errors.CODES) == 15
    assert {"EMAIL_INVALID", "PASSWORD_TOO_WEAK", "TOKEN_EXPIRED", "INVITE_NOT_FOUND", "MEETING_NOT_FOUND",
            "EMAIL_DUPLICATED", "TEAM_FULL", "PAYLOAD_TOO_LARGE", "UNSUPPORTED_MEDIA_TYPE",
            "INVALID_CREDENTIALS", "FORBIDDEN", "OWNER_ONLY", "VALIDATION_ERROR", "NOT_FOUND",
            "UNAUTHORIZED"} == set(errors.CODES)


def test_every_error_response_is_code_msg_and_code_is_documented(client):
    samples = [
        client.get("/api/auth/me"),
        client.post("/api/auth/login", json={"email": "x@example.com", "password": "password1"}),
        client.post("/api/auth/signup", json={}),
        client.get("/api/meetings/1"),
    ]
    for r in samples:
        assert r.status_code >= 400
        assert set(r.json()) == {"code", "msg"} and r.json()["code"] in errors.CODES


def test_tables_are_the_documented_7():
    from app.db import Base
    assert set(Base.metadata.tables) == {"users", "teams", "memberships", "meetings", "todos", "comments", "activities"}


def test_activity_kinds_are_exactly_five():
    from app.util import KINDS
    assert KINDS == ("meeting_add", "todo_assign", "todo_done", "comment_add", "member_join")


def test_database_url_switch_sqlite_vs_postgres(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert config.database_url().startswith("sqlite:///") and config.database_url().endswith("meetingnote.db")
    monkeypatch.setenv("DATABASE_URL", "postgres://u:p@host/db")
    assert config.database_url() == "postgresql+psycopg://u:p@host/db"
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host/db?sslmode=require")
    assert config.database_url().startswith("postgresql+psycopg://")


def test_env_example_has_only_the_two_gemini_lines_and_no_secret():
    lines = [ln for ln in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert [ln.split("=")[0] for ln in lines] == ["GEMINI_API_KEY", "GEMINI_MODEL"]
    assert lines[0] == "GEMINI_API_KEY="


def test_dotenv_is_not_tracked_by_git():
    out = subprocess.run(["git", "ls-files", ".env"], cwd=ROOT, capture_output=True, text=True).stdout
    assert out.strip() == ""


def test_no_api_key_like_string_in_tracked_source():
    files = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout.splitlines()
    pat = re.compile(r"AIza[0-9A-Za-z_\-]{30,}")
    bad = [f for f in files if f.endswith((".py", ".js", ".html", ".md", ".yaml", ".json", ".toml", ".example"))
           and pat.search((ROOT / f).read_text(encoding="utf-8", errors="ignore"))]
    assert bad == []
