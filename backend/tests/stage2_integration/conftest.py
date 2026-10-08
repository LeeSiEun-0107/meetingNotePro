"""2단계: 실제 uvicorn 프로세스 + 파일 DB + 진짜 HTTP.

기본은 Gemini 만 가짜로 바꾼 서버(tests/run_e2e_server.py)를 쓴다.
REAL_GEMINI=1 이면 가짜 없이 `uvicorn app.main:app` 을 그대로 띄워 실제 Gemini 를 쓴다.
"""
import itertools
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

BACKEND = Path(__file__).resolve().parents[2]
REAL = os.getenv("REAL_GEMINI") == "1"
PW = "password1"
_seq = itertools.count(1)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Server:
    def __init__(self, db: Path):
        self.db, self.port, self.proc = db, _free_port(), None
        self.base = f"http://127.0.0.1:{self.port}"

    def start(self, keep_db=False):
        env = os.environ.copy()
        env.update(DATABASE_URL=f"sqlite:///{self.db.as_posix()}", JWT_SECRET="stage2-secret-" + "x" * 40,
                   PYTHONIOENCODING="utf-8", KEEP_DB="1" if keep_db else "0")
        env.pop("VERCEL", None)
        if REAL:
            cmd = [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(self.port),
                   "--log-level", "warning"]
        else:
            cmd = [sys.executable, "tests/run_e2e_server.py", str(self.db), str(self.port)]
        self.proc = subprocess.Popen(cmd, cwd=BACKEND, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        deadline = time.time() + 30
        while time.time() < deadline:
            if self.proc.poll() is not None:
                raise RuntimeError("서버가 바로 종료됨: " + (self.proc.stderr.read() or b"").decode("utf-8", "replace")[-400:])
            try:
                if httpx.get(self.base + "/openapi.json", timeout=1).status_code == 200:
                    return
            except httpx.HTTPError:
                time.sleep(0.2)
        raise RuntimeError("서버가 30초 안에 뜨지 않음")

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.proc = None


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    s = Server(tmp_path_factory.mktemp("stage2") / "it.db")
    s.start()
    yield s
    s.stop()


class User:
    def __init__(self, http, name, email, token, uid):
        self.http, self.name, self.email, self.token, self.id = http, name, email, token, uid

    def req(self, method, path, **kw):
        kw.setdefault("headers", {})["Authorization"] = f"Bearer {self.token}"
        return self.http.request(method, path, **kw)

    def get(self, p, **kw): return self.req("GET", p, **kw)
    def post(self, p, **kw): return self.req("POST", p, **kw)
    def put(self, p, **kw): return self.req("PUT", p, **kw)
    def delete(self, p, **kw): return self.req("DELETE", p, **kw)


@pytest.fixture(scope="module")
def http(server):
    with httpx.Client(base_url=server.base, timeout=90) as c:
        yield c


def new_user(http, name, invite=None) -> User:
    email = f"s2u{next(_seq)}-{int(time.time()*1000)}@example.com"
    r = http.post("/api/auth/signup", json={"email": email, "password": PW, "name": name})
    assert r.status_code == 201, r.text
    u = r.json()
    user = User(http, name, email, u["token"], u["user"]["id"])
    if invite:
        j = user.post("/api/teams/join", json={"invite_code": invite})
        assert j.status_code == 200, j.text
    return user


def new_team(http, leader_name="김대리", members=("박과장", "이주임")):
    leader = new_user(http, leader_name)
    t = leader.post("/api/teams", json={"name": "기획팀"}).json()
    others = [new_user(http, n, t["invite_code"]) for n in members]
    return leader, others, t


WAV_PATH = os.getenv("REAL_WAV", r"C:\Users\LSE\Downloads\회의_녹음.wav")
