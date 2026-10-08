"""프로그램정의 3장의 사용 시나리오 4종을 실제 서버에 HTTP 로 끝에서 끝까지 돌린다."""
from .conftest import PW, User, new_team, new_user

MEETING = {"title": "2차 스프린트 계획 회의", "met_at": "2026-09-24T05:00:00Z", "attendees": "김대리, 박과장, 이주임",
           "body": "김대리: 목록은 제가 하겠습니다.\n박과장: 25MB 로 제한하죠."}


def _todos(u, team_id):
    return u.get(f"/api/teams/{team_id}/todos").json()


def test_scenario_1_leader_signup_to_assignment(http):
    """리더가 회원가입 > 로그인 > 팀 생성 · 초대코드 발급 > 멤버 합류 > 녹취 업로드 > 구분 > 할 일 배정."""
    email = "leader-s1@example.com"
    assert http.post("/api/auth/signup", json={"email": email, "password": PW, "name": "김대리"}).status_code == 201
    token = http.post("/api/auth/login", json={"email": email, "password": PW}).json()["token"]
    leader = User(http, "김대리", email, token, None)
    assert leader.get("/api/auth/me").json()["team_id"] is None
    team = leader.post("/api/teams", json={"name": "기획팀"}).json()
    assert team["invite_code"].startswith("MN-")
    new_user(http, "박과장", team["invite_code"])
    lee = new_user(http, "이주임", team["invite_code"])
    wav = b"RIFF\x24\x00\x00\x00WAVEfmt " + b"\x00" * 64
    up = leader.post("/api/upload", files={"file": ("a.wav", wav, "audio/wav")})
    assert up.status_code == 200 and up.json()["body"]
    m = leader.post(f"/api/teams/{team['id']}/meetings", json={**MEETING, "body": up.json()["body"]})
    assert m.status_code == 201
    d = m.json()
    assert d["summary"] and d["decision_count"] >= 1 and d["todo_total_count"] >= 1
    unassigned = next(t for t in _todos(leader, team["id"]) if t["assignee_id"] is None)
    r = leader.put(f"/api/todos/{unassigned['id']}", json={"assignee_id": lee.id, "due_text": "이번 달 안"})
    assert r.status_code == 200 and r.json()["assignee_name"] == "이주임"
    kinds = {a["kind"] for a in leader.get(f"/api/teams/{team['id']}/activities").json()}
    assert {"meeting_add", "todo_assign", "member_join"} <= kinds


def test_scenario_2_member_moves_card_to_done_and_it_is_logged(http):
    """팀원이 로그인 > 칸반에서 담당 할 일을 완료로 이동 > 활동 기록에 기록."""
    leader, (park, lee), team = new_team(http)
    leader.post(f"/api/teams/{team['id']}/meetings", json=MEETING)
    target = next(t for t in _todos(leader, team["id"]) if t["assignee_id"] == lee.id)
    assert all(t["id"] != target["id"] for t in park.get("/api/me/todos").json())  # 남의 할 일은 내 목록에 없다
    for status in ("DOING", "DONE"):
        r = lee.put(f"/api/todos/{target['id']}", json={"status": status})
        assert r.status_code == 200 and r.json()["status"] == status
    acts = lee.get("/api/me/activities").json()
    assert acts[0]["kind"] == "todo_done" and target["what"] in acts[0]["text"] and acts[0]["actor_name"] == "이주임"
    assert leader.get(f"/api/teams/{team['id']}/activities").json()[0]["kind"] == "todo_done"


def test_scenario_3_newcomer_finds_past_decision_and_asks_by_comment(http):
    """신규 합류자가 초대코드로 진입 > 검색으로 지난 회의 찾기 > 결정사항 읽기 > 댓글로 질문."""
    leader, _, team = new_team(http)
    leader.post(f"/api/teams/{team['id']}/meetings", json={**MEETING, "title": "배포 환경 점검", "met_at": "2026-09-18T01:30:00Z"})
    leader.post(f"/api/teams/{team['id']}/meetings", json={**MEETING, "title": "기획 킥오프", "met_at": "2026-09-10T00:00:00Z"})
    newcomer = new_user(http, "최선임", team["invite_code"])
    assert len(newcomer.get(f"/api/teams/{team['id']}/meetings").json()) == 2  # 합류 직후 첫 화면: 목록
    found = newcomer.get(f"/api/teams/{team['id']}/meetings", params={"q": "배포"}).json()
    assert [m["title"] for m in found] == ["배포 환경 점검"]
    detail = newcomer.get(f"/api/meetings/{found[0]['id']}").json()
    assert detail["decisions"].strip() and detail["body"]
    assert newcomer.post(f"/api/meetings/{found[0]['id']}/comments", json={"content": "업로드 상한은 지금 얼마인가요?"}).status_code == 201
    assert [x["user_name"] for x in leader.get(f"/api/meetings/{found[0]['id']}/comments").json()] == ["최선임"]
    assert leader.get(f"/api/teams/{team['id']}/activities").json()[0]["kind"] == "comment_add"


def test_scenario_4_leader_changes_profile_and_reviews_week_flow(http):
    """리더가 내 정보에서 이름과 비밀번호를 바꾸고 > 활동 기록으로 이번 주 팀 흐름 확인."""
    leader, (park, lee), team = new_team(http)
    leader.post(f"/api/teams/{team['id']}/meetings", json=MEETING)
    park.put(f"/api/todos/{_todos(leader, team['id'])[0]['id']}", json={"status": "DONE"})
    r = leader.put("/api/auth/me", json={"name": "김수석", "current_password": PW, "password": "newpass1234"})
    assert r.status_code == 200 and r.json()["name"] == "김수석"
    assert http.post("/api/auth/login", json={"email": leader.email, "password": "newpass1234"}).status_code == 200
    assert http.post("/api/auth/login", json={"email": leader.email, "password": PW}).status_code == 401
    flow = leader.get(f"/api/teams/{team['id']}/activities").json()
    assert {"member_join", "meeting_add", "todo_done"} <= {a["kind"] for a in flow}
    assert not any("비밀번호" in a["text"] for a in flow)  # 계정 변경은 활동 기록에 남지 않는다
    assert "김수석" in {m["name"] for m in leader.get(f"/api/teams/{team['id']}/members").json()}


def test_permissions_over_http(http):
    leader, (park, lee), team = new_team(http)
    m = park.post(f"/api/teams/{team['id']}/meetings", json=MEETING).json()
    todo = _todos(leader, team["id"])[0]
    assert lee.put(f"/api/meetings/{m['id']}", json={"title": "x"}).json()["code"] == "FORBIDDEN"
    assert lee.delete(f"/api/todos/{todo['id']}").json()["code"] == "OWNER_ONLY"
    assert lee.put(f"/api/teams/{team['id']}", json={"name": "x"}).json()["code"] == "OWNER_ONLY"
    outsider = new_user(http, "외부인")
    assert outsider.get(f"/api/meetings/{m['id']}").json()["code"] == "FORBIDDEN"
    assert http.get("/api/auth/me").json()["code"] == "UNAUTHORIZED"
    assert leader.delete(f"/api/meetings/{m['id']}").status_code == 204


def test_team_capacity_is_six_over_http(http):
    leader, _, team = new_team(http, members=("a", "b", "c", "d", "e"))  # 리더 포함 6명
    r = new_user(http, "일곱째").post("/api/teams/join", json={"invite_code": team["invite_code"]})
    assert r.status_code == 409 and r.json()["code"] == "TEAM_FULL"
    assert len(leader.get(f"/api/teams/{team['id']}/members").json()) == 6
