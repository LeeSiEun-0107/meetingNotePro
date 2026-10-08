import itertools

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app import ai
from app.db import Base, get_db, make_engine
from app.main import app

PW = "password1"
_seq = itertools.count(1)


@pytest.fixture()
def db_engine():
    engine = make_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def client(db_engine):
    Session = sessionmaker(bind=db_engine, autoflush=False, expire_on_commit=False)

    def _get_db():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _get_db
    yield TestClient(app)  # with 를 쓰지 않아 실제 DB 를 만드는 lifespan 은 돌지 않는다
    app.dependency_overrides.clear()


SAMPLE_SPLIT = {
    "summary": "2차 스프린트 계획을 다루었다.\n검색 범위를 확정했다.",
    "decisions": ["검색은 제목과 참석자 범위로 한정", "업로드 상한은 25MB"],
    "todos": [
        {"what": "목록 화면 구현", "assignee": "김대리", "due": "다음 주 금요일"},
        {"what": "받아쓰기 오류 처리", "assignee": "이주임", "due": "이번 주 안"},
        {"what": "사용자 인터뷰", "assignee": "", "due": ""},
    ],
}


@pytest.fixture(autouse=True)
def fake_ai(monkeypatch):
    """Gemini 는 부르지 않는다. 테스트마다 monkeypatch 로 바꿀 수 있다."""
    monkeypatch.setattr(ai, "split_meeting", lambda body, names: dict(SAMPLE_SPLIT))
    monkeypatch.setattr(ai, "transcribe", lambda data, mime: "김대리: 받아쓴 본문입니다.")


class Who:
    def __init__(self, client, name, email, token, user_id):
        self.client, self.name, self.email, self.token, self.id = client, name, email, token, user_id

    @property
    def h(self):
        return {"Authorization": f"Bearer {self.token}"}


def signup(client, name, invite_code=None) -> Who:
    email = f"u{next(_seq)}@example.com"
    body = {"email": email, "password": PW, "name": name}
    if invite_code:
        body["invite_code"] = invite_code
    r = client.post("/api/auth/signup", json=body)
    assert r.status_code == 201, r.text
    d = r.json()
    return Who(client, name, email, d["token"], d["user"]["id"])


@pytest.fixture()
def team(client):
    """김대리(owner) + 박과장 · 이주임(member) 한 팀."""
    owner = signup(client, "김대리")
    r = client.post("/api/teams", json={"name": "기획팀"}, headers=owner.h)
    assert r.status_code == 201
    t = r.json()
    park = signup(client, "박과장", t["invite_code"])
    lee = signup(client, "이주임", t["invite_code"])
    return {"id": t["id"], "code": t["invite_code"], "owner": owner, "park": park, "lee": lee}


@pytest.fixture()
def meeting(client, team):
    """박과장이 올린 회의록 1건 (할 일 3개)."""
    r = client.post(
        f"/api/teams/{team['id']}/meetings",
        json={"title": "2차 스프린트 계획 회의", "met_at": "2026-09-24T05:00:00Z",
              "attendees": "김대리, 박과장, 이주임", "body": "김대리: 목록은 제가 하겠습니다."},
        headers=team["park"].h,
    )
    assert r.status_code == 201, r.text
    return r.json()
