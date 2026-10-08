import time

import jwt
import pytest

from app import config
from app.security import ALGO
from conftest import PW, signup


def _signup_body(**kw):
    b = {"email": "a@example.com", "password": PW, "name": "홍길동"}
    b.update(kw)
    return b


def test_signup_ok_returns_201_jwt_and_no_team(client):
    r = client.post("/api/auth/signup", json=_signup_body())
    assert r.status_code == 201
    d = r.json()
    assert d["token"]
    assert d["user"]["team_id"] is None and d["user"]["role"] is None


def test_signup_password_is_hashed(client, db_engine):
    client.post("/api/auth/signup", json=_signup_body())
    from app.models import User
    from sqlalchemy.orm import Session
    with Session(db_engine) as s:
        u = s.query(User).one()
        assert u.password_hash != PW and u.password_hash.startswith("$2")
        assert u.password_hash.split("$")[2] == "11"  # 비용 11


@pytest.mark.parametrize("email", ["user@@example", "nodomain", "a b@example.com", ""])
def test_signup_email_invalid(client, email):
    r = client.post("/api/auth/signup", json=_signup_body(email=email))
    assert r.status_code == 400 and r.json()["code"] == "EMAIL_INVALID"


def test_signup_password_too_weak(client):
    r = client.post("/api/auth/signup", json=_signup_body(password="1234567"))
    assert r.status_code == 400 and r.json()["code"] == "PASSWORD_TOO_WEAK"


def test_signup_email_duplicated(client):
    client.post("/api/auth/signup", json=_signup_body())
    r = client.post("/api/auth/signup", json=_signup_body(name="다른이름"))
    assert r.status_code == 409 and r.json()["code"] == "EMAIL_DUPLICATED"


def test_signup_missing_field_is_validation_error_with_code_msg(client):
    r = client.post("/api/auth/signup", json={"email": "a@example.com"})
    assert r.status_code == 400
    assert set(r.json()) == {"code", "msg"} and r.json()["code"] == "VALIDATION_ERROR"


def test_signup_with_valid_invite_joins_team(client, team):
    r = client.post("/api/auth/signup", json=_signup_body(email="n@example.com", invite_code=team["code"]))
    assert r.status_code == 201
    assert r.json()["user"]["team_id"] == team["id"] and r.json()["user"]["role"] == "member"


def test_signup_bad_invite_keeps_account_but_fails_join(client):
    r = client.post("/api/auth/signup", json=_signup_body(invite_code="MN-0000"))
    assert r.status_code == 404 and r.json()["code"] == "INVITE_NOT_FOUND"
    # 가입은 되었으므로 로그인이 된다
    r = client.post("/api/auth/login", json={"email": "a@example.com", "password": PW})
    assert r.status_code == 200 and r.json()["user"]["team_id"] is None


def test_login_ok(client):
    client.post("/api/auth/signup", json=_signup_body())
    r = client.post("/api/auth/login", json={"email": "a@example.com", "password": PW})
    assert r.status_code == 200 and r.json()["token"]


def test_login_wrong_password_and_unknown_email_look_the_same(client):
    client.post("/api/auth/signup", json=_signup_body())
    wrong_pw = client.post("/api/auth/login", json={"email": "a@example.com", "password": "nope-nope-1"})
    no_user = client.post("/api/auth/login", json={"email": "zz@example.com", "password": PW})
    assert wrong_pw.status_code == no_user.status_code == 401
    assert wrong_pw.json() == no_user.json()
    assert wrong_pw.json()["code"] == "INVALID_CREDENTIALS"


def test_token_expires_in_24h(client):
    who = signup(client, "홍")
    data = jwt.decode(who.token, config.jwt_secret(), algorithms=[ALGO])
    assert data["exp"] - data["iat"] == 24 * 3600


def test_expired_token_gives_token_expired_401(client):
    who = signup(client, "홍")
    now = int(time.time())
    old = jwt.encode({"sub": str(who.id), "iat": now - 90000, "exp": now - 3600}, config.jwt_secret(), algorithm=ALGO)
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {old}"})
    assert r.status_code == 401 and r.json()["code"] == "TOKEN_EXPIRED"


def test_missing_or_garbage_token_is_unauthorized(client):
    assert client.get("/api/auth/me").json()["code"] == "UNAUTHORIZED"
    r = client.get("/api/auth/me", headers={"Authorization": "Bearer garbage"})
    assert r.status_code == 401 and r.json()["code"] == "UNAUTHORIZED"


def test_me_has_team_id_name_and_role(client, team):
    d = client.get("/api/auth/me", headers=team["owner"].h).json()
    assert d["team_id"] == team["id"] and d["team_name"] == "기획팀" and d["role"] == "owner"
    d = client.get("/api/auth/me", headers=team["park"].h).json()
    assert d["role"] == "member"


def test_update_name_only_keeps_password_and_needs_no_current_password(client):
    who = signup(client, "홍")
    r = client.put("/api/auth/me", json={"name": "김수석"}, headers=who.h)
    assert r.status_code == 200 and r.json()["name"] == "김수석"
    assert client.post("/api/auth/login", json={"email": who.email, "password": PW}).status_code == 200


def test_change_password_with_correct_current(client):
    who = signup(client, "홍")
    r = client.put("/api/auth/me", json={"current_password": PW, "password": "newpass1234"}, headers=who.h)
    assert r.status_code == 200
    assert client.post("/api/auth/login", json={"email": who.email, "password": PW}).status_code == 401
    assert client.post("/api/auth/login", json={"email": who.email, "password": "newpass1234"}).status_code == 200


def test_change_password_wrong_current_is_401_unauthorized(client):
    who = signup(client, "홍")
    r = client.put("/api/auth/me", json={"current_password": "wrong-wrong", "password": "newpass1234"}, headers=who.h)
    assert r.status_code == 401 and r.json()["code"] == "UNAUTHORIZED"
    assert client.post("/api/auth/login", json={"email": who.email, "password": PW}).status_code == 200


def test_change_password_without_current_is_validation_error(client):
    who = signup(client, "홍")
    r = client.put("/api/auth/me", json={"password": "newpass1234"}, headers=who.h)
    assert r.status_code == 400 and r.json()["code"] == "VALIDATION_ERROR"


def test_change_password_too_weak(client):
    who = signup(client, "홍")
    r = client.put("/api/auth/me", json={"current_password": PW, "password": "1234"}, headers=who.h)
    assert r.status_code == 400 and r.json()["code"] == "PASSWORD_TOO_WEAK"


def test_email_cannot_be_changed(client):
    who = signup(client, "홍")
    client.put("/api/auth/me", json={"email": "hacker@example.com", "name": "홍"}, headers=who.h)
    assert client.get("/api/auth/me", headers=who.h).json()["email"] == who.email


def test_logout_is_200(client):
    who = signup(client, "홍")
    assert client.post("/api/auth/logout", headers=who.h).status_code == 200


def test_account_change_is_not_logged_as_activity(client, team):
    before = client.get("/api/me/activities", headers=team["park"].h).json()
    client.put("/api/auth/me", json={"name": "박부장"}, headers=team["park"].h)
    after = client.get("/api/me/activities", headers=team["park"].h).json()
    assert len(after) == len(before)


def test_signup_and_login_stay_under_250ms(client):
    """프로그램정의 Metrics: 가입 · 로그인은 bcrypt 비용 때문에 250ms 이내."""
    import time
    t0 = time.perf_counter()
    client.post("/api/auth/signup", json=_signup_body(email="perf@example.com"))
    signup_ms = (time.perf_counter() - t0) * 1000
    t0 = time.perf_counter()
    client.post("/api/auth/login", json={"email": "perf@example.com", "password": PW})
    login_ms = (time.perf_counter() - t0) * 1000
    assert signup_ms < 250 and login_ms < 250, (signup_ms, login_ms)


def test_general_api_under_100ms(client):
    import time
    who = signup(client, "홍")
    ms = []
    for _ in range(20):
        t0 = time.perf_counter()
        client.get("/api/auth/me", headers=who.h)
        ms.append((time.perf_counter() - t0) * 1000)
    assert sum(ms) / len(ms) < 100, ms
