from conftest import signup


def _todos(client, team, who=None):
    return client.get(f"/api/teams/{team['id']}/todos", headers=(who or team["owner"]).h).json()


def _by(todos, what):
    return next(t for t in todos if t["what"] == what)


# ---- 할 일 ----

def test_team_todos_have_required_fields_and_meeting_title(client, team, meeting):
    t = _todos(client, team)[0]
    assert set(t) >= {"id", "what", "assignee_id", "assignee_name", "due_text", "status", "meeting_title"}
    assert t["meeting_title"] == "2차 스프린트 계획 회의"


def test_my_todos_only_mine(client, team, meeting):
    mine = client.get("/api/me/todos", headers=team["owner"].h).json()
    assert [t["what"] for t in mine] == ["목록 화면 구현"]
    assert client.get("/api/me/todos", headers=team["park"].h).json() == []


def test_empty_todos_is_empty_array(client, team):
    assert _todos(client, team) == []
    assert client.get("/api/me/todos", headers=team["park"].h).json() == []


def test_todos_sorted_by_status_then_due_text(client, team, meeting):
    todos = _todos(client, team)
    doing = _by(todos, "받아쓰기 오류 처리")
    client.put(f"/api/todos/{doing['id']}", json={"status": "DONE"}, headers=team["lee"].h)
    statuses = [t["status"] for t in _todos(client, team)]
    assert statuses == sorted(statuses, key=["OPEN", "DOING", "DONE"].index)
    open_due = [t["due_text"] for t in _todos(client, team) if t["status"] == "OPEN"]
    assert open_due == sorted(open_due)


def test_any_member_can_change_status_both_ways(client, team, meeting):
    t = _by(_todos(client, team), "목록 화면 구현")
    for who, status in ((team["lee"], "DOING"), (team["park"], "DONE"), (team["lee"], "OPEN")):
        r = client.put(f"/api/todos/{t['id']}", json={"status": status}, headers=who.h)
        assert r.status_code == 200 and r.json()["status"] == status


def test_invalid_status_rejected(client, team, meeting):
    t = _todos(client, team)[0]
    r = client.put(f"/api/todos/{t['id']}", json={"status": "FINISHED"}, headers=team["lee"].h)
    assert r.status_code == 400 and r.json()["code"] == "VALIDATION_ERROR"


def test_assign_and_unassign_and_due(client, team, meeting):
    t = _by(_todos(client, team), "사용자 인터뷰")
    r = client.put(f"/api/todos/{t['id']}", json={"assignee_id": team["lee"].id, "due_text": "이번 달 안"}, headers=team["park"].h)
    assert r.status_code == 200 and r.json()["assignee_name"] == "이주임" and r.json()["due_text"] == "이번 달 안"
    r = client.put(f"/api/todos/{t['id']}", json={"assignee_id": None}, headers=team["park"].h)
    assert r.json()["assignee_id"] is None and r.json()["assignee_name"] == "미정"
    assert r.json()["due_text"] == "이번 달 안"  # 보내지 않은 필드는 그대로


def test_cannot_assign_to_outsider(client, team, meeting):
    outsider = signup(client, "외부인")
    t = _todos(client, team)[0]
    r = client.put(f"/api/todos/{t['id']}", json={"assignee_id": outsider.id}, headers=team["owner"].h)
    assert r.status_code == 400 and r.json()["code"] == "VALIDATION_ERROR"


def test_other_team_member_cannot_update(client, team, meeting):
    outsider = signup(client, "외부인")
    t = _todos(client, team)[0]
    r = client.put(f"/api/todos/{t['id']}", json={"status": "DONE"}, headers=outsider.h)
    assert r.status_code == 403 and r.json()["code"] == "FORBIDDEN"


def test_unknown_todo_404(client, team):
    assert client.put("/api/todos/9999", json={"status": "DONE"}, headers=team["owner"].h).json()["code"] == "NOT_FOUND"


def test_delete_todo_owner_only(client, team, meeting):
    t = _todos(client, team)[0]
    r = client.delete(f"/api/todos/{t['id']}", headers=team["park"].h)
    assert r.status_code == 403 and r.json()["code"] == "OWNER_ONLY"
    assert client.delete(f"/api/todos/{t['id']}", headers=team["owner"].h).status_code == 204
    assert len(_todos(client, team)) == 2


def test_meeting_counts_follow_todo_status(client, team, meeting):
    t = _by(_todos(client, team), "목록 화면 구현")
    client.put(f"/api/todos/{t['id']}", json={"status": "DONE"}, headers=team["owner"].h)
    it = client.get(f"/api/teams/{team['id']}/meetings", headers=team["owner"].h).json()[0]
    assert (it["todo_done_count"], it["todo_total_count"]) == (1, 3)


# ---- 댓글 ----

def _comment(client, meeting, who, text="의견입니다"):
    return client.post(f"/api/meetings/{meeting['id']}/comments", json={"content": text}, headers=who.h)


def test_comment_create_and_list_oldest_first_with_can_delete(client, team, meeting):
    assert _comment(client, meeting, team["lee"], "첫째").status_code == 201
    _comment(client, meeting, team["park"], "둘째")
    rows = client.get(f"/api/meetings/{meeting['id']}/comments", headers=team["lee"].h).json()
    assert [c["content"] for c in rows] == ["첫째", "둘째"]
    assert [c["can_delete"] for c in rows] == [True, False]  # 이주임 입장: 내 것만
    rows = client.get(f"/api/meetings/{meeting['id']}/comments", headers=team["owner"].h).json()
    assert [c["can_delete"] for c in rows] == [True, True]  # owner 는 모두
    assert set(rows[0]) == {"id", "user_id", "user_name", "content", "created_at", "can_delete"}


def test_comment_500_chars_ok_501_rejected_and_empty_rejected(client, team, meeting):
    assert _comment(client, meeting, team["lee"], "가" * 500).status_code == 201
    r = _comment(client, meeting, team["lee"], "가" * 501)
    assert r.status_code == 400 and r.json()["code"] == "VALIDATION_ERROR"
    assert _comment(client, meeting, team["lee"], "   ").json()["code"] == "VALIDATION_ERROR"


def test_no_comments_is_empty_array(client, team, meeting):
    r = client.get(f"/api/meetings/{meeting['id']}/comments", headers=team["lee"].h)
    assert r.status_code == 200 and r.json() == []


def test_comment_on_unknown_meeting(client, team):
    assert _comment(client, {"id": 9999}, team["lee"]).json()["code"] == "MEETING_NOT_FOUND"


def test_comment_delete_author_owner_ok_other_forbidden(client, team, meeting):
    cid = _comment(client, meeting, team["lee"]).json()["id"]
    r = client.delete(f"/api/comments/{cid}", headers=team["park"].h)
    assert r.status_code == 403 and r.json()["code"] == "FORBIDDEN"
    assert client.delete(f"/api/comments/{cid}", headers=team["lee"].h).status_code == 204
    cid = _comment(client, meeting, team["lee"]).json()["id"]
    assert client.delete(f"/api/comments/{cid}", headers=team["owner"].h).status_code == 204
    assert client.get(f"/api/meetings/{meeting['id']}/comments", headers=team["lee"].h).json() == []


def test_comment_outsider_forbidden(client, team, meeting):
    outsider = signup(client, "외부인")
    assert _comment(client, meeting, outsider).json()["code"] == "FORBIDDEN"
    assert client.get(f"/api/meetings/{meeting['id']}/comments", headers=outsider.h).json()["code"] == "FORBIDDEN"


# ---- 활동 기록 ----

def test_five_kinds_are_recorded(client, team, meeting):
    t = _by(_todos(client, team), "사용자 인터뷰")
    client.put(f"/api/todos/{t['id']}", json={"assignee_id": team["lee"].id}, headers=team["owner"].h)
    client.put(f"/api/todos/{t['id']}", json={"status": "DONE"}, headers=team["lee"].h)
    _comment(client, meeting, team["lee"])
    acts = client.get(f"/api/teams/{team['id']}/activities", headers=team["owner"].h).json()
    kinds = {a["kind"] for a in acts}
    assert kinds == {"member_join", "meeting_add", "todo_assign", "todo_done", "comment_add"}


def test_activity_shape_order_and_text(client, team, meeting):
    _comment(client, meeting, team["lee"])
    acts = client.get(f"/api/teams/{team['id']}/activities", headers=team["owner"].h).json()
    assert set(acts[0]) == {"id", "kind", "actor_name", "text", "created_at"}
    assert acts[0]["kind"] == "comment_add" and acts[0]["actor_name"] == "이주임"
    assert acts[0]["text"] == "회의록 「2차 스프린트 계획 회의」에 댓글 작성"
    ids = [a["id"] for a in acts]
    assert ids == sorted(ids, reverse=True)  # 최근 순
    assert acts[0]["created_at"].endswith("Z")


def test_assign_text_names_the_assignee(client, team, meeting):
    t = _by(_todos(client, team), "사용자 인터뷰")
    client.put(f"/api/todos/{t['id']}", json={"assignee_id": team["lee"].id}, headers=team["owner"].h)
    top = client.get(f"/api/teams/{team['id']}/activities", headers=team["owner"].h).json()[0]
    assert top["kind"] == "todo_assign" and top["text"] == "할 일 「사용자 인터뷰」를 이주임에게 배정"


def test_reassigning_same_person_or_same_status_logs_nothing(client, team, meeting):
    t = _by(_todos(client, team), "목록 화면 구현")  # 이미 김대리 / OPEN
    before = len(client.get(f"/api/teams/{team['id']}/activities", headers=team["owner"].h).json())
    client.put(f"/api/todos/{t['id']}", json={"assignee_id": team["owner"].id, "status": "OPEN"}, headers=team["owner"].h)
    after = len(client.get(f"/api/teams/{team['id']}/activities", headers=team["owner"].h).json())
    assert after == before


def test_doing_does_not_log_only_done_does(client, team, meeting):
    t = _by(_todos(client, team), "목록 화면 구현")
    client.put(f"/api/todos/{t['id']}", json={"status": "DOING"}, headers=team["owner"].h)
    assert "todo_done" not in {a["kind"] for a in client.get(f"/api/teams/{team['id']}/activities", headers=team["owner"].h).json()}
    client.put(f"/api/todos/{t['id']}", json={"status": "DONE"}, headers=team["owner"].h)
    assert client.get(f"/api/teams/{team['id']}/activities", headers=team["owner"].h).json()[0]["kind"] == "todo_done"


def test_my_activities_only_mine_and_empty_for_new_user(client, team, meeting):
    mine = client.get("/api/me/activities", headers=team["park"].h).json()
    assert {a["kind"] for a in mine} == {"member_join", "meeting_add"}
    assert all(a["actor_name"] == "박과장" for a in mine)
    assert client.get("/api/me/activities", headers=signup(client, "신입").h).json() == []


def test_activity_limit_is_50(client, team, meeting):
    for i in range(60):
        _comment(client, meeting, team["lee"], f"댓글 {i}")
    assert len(client.get(f"/api/teams/{team['id']}/activities", headers=team["owner"].h).json()) == 50
    assert len(client.get("/api/me/activities", headers=team["lee"].h).json()) == 50
