import re

from conftest import signup


def test_create_team_makes_owner_and_invite_code(client):
    who = signup(client, "김대리")
    r = client.post("/api/teams", json={"name": "기획팀"}, headers=who.h)
    assert r.status_code == 201
    d = r.json()
    assert d["role"] == "owner" and re.fullmatch(r"MN-[A-Z0-9]{4}", d["invite_code"])
    assert client.get("/api/auth/me", headers=who.h).json()["role"] == "owner"


def test_one_person_one_team(client, team):
    r = client.post("/api/teams", json={"name": "둘째 팀"}, headers=team["park"].h)
    assert r.status_code == 400 and r.json()["code"] == "VALIDATION_ERROR"
    r = client.post("/api/teams/join", json={"invite_code": team["code"]}, headers=team["park"].h)
    assert r.json()["code"] == "VALIDATION_ERROR"


def test_my_teams_is_empty_without_team_and_single_with_team(client, team):
    solo = signup(client, "혼자")
    assert client.get("/api/teams", headers=solo.h).json() == []
    teams = client.get("/api/teams", headers=team["park"].h).json()
    assert len(teams) == 1 and teams[0]["id"] == team["id"] and teams[0]["member_count"] == 3


def test_join_ok_logs_member_join(client, team):
    new = signup(client, "최선임")
    r = client.post("/api/teams/join", json={"invite_code": team["code"]}, headers=new.h)
    assert r.status_code == 200 and r.json()["role"] == "member"
    kinds = [a["kind"] for a in client.get(f"/api/teams/{team['id']}/activities", headers=team["owner"].h).json()]
    assert kinds.count("member_join") == 3


def test_join_unknown_code(client):
    who = signup(client, "혼자")
    r = client.post("/api/teams/join", json={"invite_code": "MN-0000"}, headers=who.h)
    assert r.status_code == 404 and r.json()["code"] == "INVITE_NOT_FOUND"


def test_team_capacity_is_six(client, team):
    for n in range(3):  # 이미 3명 + 3명 = 6명
        signup(client, f"멤버{n}", team["code"])
    seventh = signup(client, "일곱째")
    r = client.post("/api/teams/join", json={"invite_code": team["code"]}, headers=seventh.h)
    assert r.status_code == 409 and r.json()["code"] == "TEAM_FULL"
    members = client.get(f"/api/teams/{team['id']}/members", headers=team["owner"].h).json()
    assert len(members) == 6


def test_signup_with_invite_into_full_team_fails_but_account_exists(client, team):
    for n in range(3):
        signup(client, f"멤버{n}", team["code"])
    r = client.post("/api/auth/signup", json={"email": "late@example.com", "password": "password1",
                                              "name": "늦은이", "invite_code": team["code"]})
    assert r.status_code == 409 and r.json()["code"] == "TEAM_FULL"
    assert client.post("/api/auth/login", json={"email": "late@example.com", "password": "password1"}).status_code == 200


def test_reissue_code_owner_only_and_old_code_dies(client, team):
    r = client.put(f"/api/teams/{team['id']}/code", headers=team["park"].h)
    assert r.status_code == 403 and r.json()["code"] == "OWNER_ONLY"
    r = client.put(f"/api/teams/{team['id']}/code", headers=team["owner"].h)
    assert r.status_code == 200
    new_code = r.json()["invite_code"]
    assert new_code != team["code"]
    late = signup(client, "늦은이")
    r = client.post("/api/teams/join", json={"invite_code": team["code"]}, headers=late.h)
    assert r.json()["code"] == "INVITE_NOT_FOUND"
    assert client.post("/api/teams/join", json={"invite_code": new_code}, headers=late.h).status_code == 200
    # 이미 합류한 멤버는 그대로
    assert len(client.get(f"/api/teams/{team['id']}/members", headers=team["owner"].h).json()) == 4


def test_rename_owner_only(client, team):
    r = client.put(f"/api/teams/{team['id']}", json={"name": "새 이름"}, headers=team["lee"].h)
    assert r.status_code == 403 and r.json()["code"] == "OWNER_ONLY"
    r = client.put(f"/api/teams/{team['id']}", json={"name": "새 이름"}, headers=team["owner"].h)
    assert r.status_code == 200 and r.json()["name"] == "새 이름"
    assert client.get("/api/auth/me", headers=team["lee"].h).json()["team_name"] == "새 이름"


def test_members_have_role_and_todo_count(client, team, meeting):
    members = {m["name"]: m for m in client.get(f"/api/teams/{team['id']}/members", headers=team["lee"].h).json()}
    assert members["김대리"]["role"] == "owner" and members["박과장"]["role"] == "member"
    assert members["김대리"]["todo_count"] == 1 and members["이주임"]["todo_count"] == 1
    assert members["박과장"]["todo_count"] == 0
    assert set(members["김대리"]) == {"id", "name", "email", "role", "todo_count"}


def test_non_member_cannot_see_team(client, team):
    outsider = signup(client, "외부인")
    for path in (f"/api/teams/{team['id']}/members", f"/api/teams/{team['id']}/meetings",
                 f"/api/teams/{team['id']}/todos", f"/api/teams/{team['id']}/activities"):
        r = client.get(path, headers=outsider.h)
        assert r.status_code == 403 and r.json()["code"] == "FORBIDDEN", path
