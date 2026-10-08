import pytest

from app import ai, config
from conftest import signup


def _create(client, team, who, **kw):
    body = {"title": "배포 환경 점검", "met_at": "2026-09-18T01:30:00Z", "attendees": "박과장, 최선임",
            "body": "본문"}
    body.update(kw)
    return client.post(f"/api/teams/{team['id']}/meetings", json=body, headers=who.h)


def test_create_splits_into_three_items_and_todos(client, team, meeting):
    assert meeting["summary"].count("\n") == 1
    assert meeting["decisions"].split("\n") == ["검색은 제목과 참석자 범위로 한정", "업로드 상한은 25MB"]
    assert meeting["decision_count"] == 2 and meeting["todo_total_count"] == 3
    todos = client.get(f"/api/teams/{team['id']}/todos", headers=team["owner"].h).json()
    by = {t["what"]: t for t in todos}
    assert by["목록 화면 구현"]["assignee_name"] == "김대리" and by["목록 화면 구현"]["due_text"] == "다음 주 금요일"
    assert by["사용자 인터뷰"]["assignee_id"] is None and by["사용자 인터뷰"]["assignee_name"] == "미정"
    assert by["사용자 인터뷰"]["due_text"] == "미정"
    assert all(t["status"] == "OPEN" for t in todos)


def test_todo_with_unknown_assignee_name_becomes_undecided(client, team, monkeypatch):
    monkeypatch.setattr(ai, "split_meeting", lambda b, n: {
        "summary": "s", "decisions": [], "todos": [{"what": "x", "assignee": "없는사람", "due": "내일"}]})
    _create(client, team, team["park"])
    todo = client.get(f"/api/teams/{team['id']}/todos", headers=team["owner"].h).json()[0]
    assert todo["assignee_id"] is None


def test_no_decisions_stays_empty(client, team, monkeypatch):
    monkeypatch.setattr(ai, "split_meeting", lambda b, n: {"summary": "s", "decisions": [], "todos": []})
    d = _create(client, team, team["park"]).json()
    assert d["decisions"] == "" and d["decision_count"] == 0 and d["todo_total_count"] == 0


def test_ai_failure_keeps_body_and_empties_three_items(client, team, monkeypatch):
    def boom(b, n):
        raise ai.AiError("down")
    monkeypatch.setattr(ai, "split_meeting", boom)
    r = _create(client, team, team["park"], body="그대로 남아야 하는 본문")
    assert r.status_code == 201
    d = r.json()
    assert d["body"] == "그대로 남아야 하는 본문" and d["summary"] == "" and d["decisions"] == ""
    assert d["todo_total_count"] == 0


@pytest.mark.parametrize("missing", ["title", "met_at", "body"])
def test_required_fields(client, team, missing):
    r = _create(client, team, team["park"], **{missing: " "})
    assert r.status_code == 400 and r.json()["code"] == "VALIDATION_ERROR"


def test_bad_met_at_is_validation_error(client, team):
    assert _create(client, team, team["park"], met_at="어제").json()["code"] == "VALIDATION_ERROR"


def test_met_at_is_stored_utc_and_returned_iso_z(client, team):
    d = _create(client, team, team["park"], met_at="2026-09-18T10:30:00+09:00").json()
    assert d["met_at"] == "2026-09-18T01:30:00Z"


def test_list_has_no_body_and_has_aggregates_and_author(client, team, meeting):
    items = client.get(f"/api/teams/{team['id']}/meetings", headers=team["lee"].h).json()
    assert len(items) == 1 and "body" not in items[0] and "decisions" not in items[0]
    it = items[0]
    assert it["author_id"] == team["park"].id
    assert (it["todo_done_count"], it["todo_total_count"], it["decision_count"]) == (0, 3, 2)
    assert {"id", "title", "met_at", "attendees", "summary", "created_at"} <= set(it)


def test_list_sorted_by_met_at_desc(client, team):
    _create(client, team, team["park"], title="오래된", met_at="2026-09-10T00:00:00Z")
    _create(client, team, team["park"], title="최근", met_at="2026-09-24T00:00:00Z")
    _create(client, team, team["park"], title="중간", met_at="2026-09-18T00:00:00Z")
    titles = [m["title"] for m in client.get(f"/api/teams/{team['id']}/meetings", headers=team["lee"].h).json()]
    assert titles == ["최근", "중간", "오래된"]


def test_search_title_and_attendees_only_not_body(client, team):
    _create(client, team, team["park"], title="배포 환경 점검", attendees="박과장", body="비밀단어")
    _create(client, team, team["park"], title="킥오프", attendees="최선임, 김대리", body="x")
    url = f"/api/teams/{team['id']}/meetings"
    h = team["lee"].h
    assert [m["title"] for m in client.get(url, params={"q": "배포"}, headers=h).json()] == ["배포 환경 점검"]
    assert [m["title"] for m in client.get(url, params={"q": "최선임"}, headers=h).json()] == ["킥오프"]
    assert client.get(url, params={"q": "비밀단어"}, headers=h).json() == []


def test_search_none_is_200_empty_list_not_404(client, team, meeting):
    r = client.get(f"/api/teams/{team['id']}/meetings", params={"q": "없는말"}, headers=team["lee"].h)
    assert r.status_code == 200 and r.json() == []


def test_empty_team_list_is_empty_array(client, team):
    r = client.get(f"/api/teams/{team['id']}/meetings", headers=team["lee"].h)
    assert r.status_code == 200 and r.json() == []


def test_period_filter(client, team):
    _create(client, team, team["park"], title="9월 10일", met_at="2026-09-10T09:00:00Z")
    _create(client, team, team["park"], title="9월 24일", met_at="2026-09-24T09:00:00Z")
    url, h = f"/api/teams/{team['id']}/meetings", team["lee"].h
    got = client.get(url, params={"from": "2026-09-20", "to": "2026-09-30"}, headers=h).json()
    assert [m["title"] for m in got] == ["9월 24일"]
    got = client.get(url, params={"from": "2026-09-10", "to": "2026-09-10"}, headers=h).json()
    assert [m["title"] for m in got] == ["9월 10일"]  # to 가 날짜만이면 그날 끝까지
    assert client.get(url, params={"from": "x"}, headers=h).json()["code"] == "VALIDATION_ERROR"


def test_detail_has_body_and_author(client, meeting, team):
    d = client.get(f"/api/meetings/{meeting['id']}", headers=team["lee"].h).json()
    assert d["body"] == "김대리: 목록은 제가 하겠습니다." and d["author_id"] == team["park"].id


def test_detail_404_meeting_not_found(client, team):
    r = client.get("/api/meetings/9999", headers=team["lee"].h)
    assert r.status_code == 404 and r.json()["code"] == "MEETING_NOT_FOUND"


def test_detail_forbidden_for_other_team(client, meeting):
    outsider = signup(client, "외부인")
    r = client.get(f"/api/meetings/{meeting['id']}", headers=outsider.h)
    assert r.status_code == 403 and r.json()["code"] == "FORBIDDEN"


def test_update_by_author_does_not_rerun_ai(client, team, meeting, monkeypatch):
    def must_not_run(*a, **k):
        raise AssertionError("수정은 세 항목 구분을 다시 돌리지 않는다")
    monkeypatch.setattr(ai, "split_meeting", must_not_run)
    r = client.put(f"/api/meetings/{meeting['id']}", json={"title": "새 제목", "body": "고친 본문"}, headers=team["park"].h)
    assert r.status_code == 200 and r.json()["title"] == "새 제목" and r.json()["body"] == "고친 본문"
    assert r.json()["summary"] == meeting["summary"] and r.json()["todo_total_count"] == 3


def test_update_by_owner_ok_by_other_member_forbidden(client, team, meeting):
    assert client.put(f"/api/meetings/{meeting['id']}", json={"title": "owner 수정"}, headers=team["owner"].h).status_code == 200
    r = client.put(f"/api/meetings/{meeting['id']}", json={"title": "x"}, headers=team["lee"].h)
    assert r.status_code == 403 and r.json()["code"] == "FORBIDDEN"


def test_delete_cascades_todos_and_comments_and_checks_permission(client, team, meeting):
    client.post(f"/api/meetings/{meeting['id']}/comments", json={"content": "의견"}, headers=team["lee"].h)
    r = client.delete(f"/api/meetings/{meeting['id']}", headers=team["lee"].h)
    assert r.status_code == 403 and r.json()["code"] == "FORBIDDEN"
    assert client.delete(f"/api/meetings/{meeting['id']}", headers=team["park"].h).status_code == 204
    assert client.get(f"/api/meetings/{meeting['id']}", headers=team["owner"].h).status_code == 404
    assert client.get(f"/api/teams/{team['id']}/todos", headers=team["owner"].h).json() == []


def test_delete_by_owner_of_someone_elses_meeting(client, team, meeting):
    assert client.delete(f"/api/meetings/{meeting['id']}", headers=team["owner"].h).status_code == 204


def test_create_logs_meeting_add(client, team, meeting):
    acts = client.get(f"/api/teams/{team['id']}/activities", headers=team["owner"].h).json()
    top = acts[0]
    assert top["kind"] == "meeting_add" and top["actor_name"] == "박과장" and "2차 스프린트 계획 회의" in top["text"]


# ---- 업로드 ----

WAV = b"RIFF\x24\x00\x00\x00WAVEfmt " + b"\x00" * 40
MP3_ID3 = b"ID3\x03\x00\x00\x00\x00\x00\x00" + b"\x00" * 40
MP3_FRAME = b"\xff\xfb\x90\x00" + b"\x00" * 40
MP4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 40


def _upload(client, who, data, name="a.wav"):
    return client.post("/api/upload", files={"file": (name, data, "application/octet-stream")}, headers=who.h)


@pytest.mark.parametrize("data", [WAV, MP3_ID3, MP3_FRAME])
def test_upload_ok_returns_text_only(client, team, data):
    r = _upload(client, team["park"], data)
    assert r.status_code == 200 and r.json() == {"body": "김대리: 받아쓴 본문입니다."}


def test_upload_judges_by_content_not_extension(client, team):
    assert _upload(client, team["park"], WAV, name="fake.mp4").status_code == 200
    r = _upload(client, team["park"], MP4, name="real.wav")
    assert r.status_code == 415 and r.json()["code"] == "UNSUPPORTED_MEDIA_TYPE"


def test_upload_over_limit_is_413(client, team):
    big = WAV + b"\x00" * (5 * 1024 * 1024)
    r = _upload(client, team["park"], big)
    assert r.status_code == 413 and r.json()["code"] == "PAYLOAD_TOO_LARGE"


def test_upload_exactly_at_limit_is_accepted(client, team):
    data = WAV + b"\x00" * (config.MAX_UPLOAD_BYTES - len(WAV))
    assert _upload(client, team["park"], data).status_code == 200


def test_upload_requires_login(client):
    r = client.post("/api/upload", files={"file": ("a.wav", WAV)})
    assert r.status_code == 401


def test_upload_does_not_save_a_meeting(client, team):
    _upload(client, team["park"], WAV)
    assert client.get(f"/api/teams/{team['id']}/meetings", headers=team["park"].h).json() == []


def test_upload_ai_failure_is_reported_not_crashed(client, team, monkeypatch):
    def boom(d, m):
        raise ai.AiError("down")
    monkeypatch.setattr(ai, "transcribe", boom)
    r = _upload(client, team["park"], WAV)
    assert r.status_code == 502 and set(r.json()) == {"code", "msg"}
