"""Vercel 배포 준비: 설정 파일, 안전장치, 업로드 상한."""
import importlib
import json
import re
import sys
import tomllib

import pytest

from app import config

ROOT = config.ROOT


def test_pyproject_points_vercel_at_an_importable_fastapi_app():
    cfg = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    module, _, attr = cfg["tool"]["vercel"]["entrypoint"].partition(":")
    assert (module, attr) == ("backend.app.main", "app")
    sys.path.insert(0, str(ROOT))
    try:
        mod = importlib.import_module(module)
    finally:
        sys.path.remove(str(ROOT))
    from fastapi import FastAPI
    assert isinstance(getattr(mod, attr), FastAPI)


def test_pyproject_dependencies_cover_backend_requirements():
    cfg = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    name = lambda spec: re.split(r"[<>=\[ ]", spec, maxsplit=1)[0].lower()
    declared = {name(d) for d in cfg["project"]["dependencies"]}
    wanted = {name(ln) for ln in (ROOT / "backend" / "requirements.txt").read_text(encoding="utf-8").splitlines()
              if ln.strip() and not ln.startswith(("#", "-"))}
    assert wanted <= declared, wanted - declared


def test_vercel_json_function_path_exists():
    cfg = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    for path in cfg["functions"]:
        assert (ROOT / path).is_file(), path


def test_vercelignore_keeps_secrets_and_dev_files_out_of_the_deploy():
    lines = {ln.strip() for ln in (ROOT / ".vercelignore").read_text(encoding="utf-8").splitlines()}
    assert {".env", "backend/.venv/", "backend/tests/", "*.db"} <= lines


def test_frontend_dir_exists_for_the_static_mount():
    assert (ROOT / "frontend" / "login.html").is_file()


def test_vercel_without_jwt_secret_refuses_to_use_the_public_default(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.delenv("JWT_SECRET", raising=False)
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        config.jwt_secret()
    monkeypatch.setenv("JWT_SECRET", "x" * 40)
    assert config.jwt_secret() == "x" * 40


def test_local_without_jwt_secret_still_works(monkeypatch):
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.delenv("JWT_SECRET", raising=False)
    assert len(config.jwt_secret()) >= 32


def test_vercel_without_database_url_refuses_sqlite(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        config.database_url()
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host/db?sslmode=require")
    assert config.database_url().startswith("postgresql+psycopg://")


def test_upload_limit_leaves_headroom_under_vercel_function_body_limit():
    # Vercel 은 헤더 포함 본문 4,500,000바이트까지. 실측으로 파일 4,493,750바이트까지 통과한다
    assert config.MAX_UPLOAD_BYTES == 4_400_000
    assert config.MAX_UPLOAD_BYTES < 4_493_750
