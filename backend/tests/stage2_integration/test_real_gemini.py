"""실제 Gemini + 실제 녹음 파일. REAL_GEMINI=1 일 때만 (그때는 서버도 가짜 없이 뜬다)."""
import time
from pathlib import Path

import pytest

from .conftest import REAL, WAV_PATH, new_team

pytestmark = pytest.mark.skipif(not REAL or not Path(WAV_PATH).is_file(),
                                reason="REAL_GEMINI=1 과 녹음 파일이 있을 때만")


def test_real_wav_upload_then_save_then_three_items(http):
    leader, _, team = new_team(http)
    data = Path(WAV_PATH).read_bytes()
    t = time.perf_counter()
    up = leader.post("/api/upload", files={"file": ("회의_녹음.wav", data, "audio/wav")})
    sec = time.perf_counter() - t
    assert up.status_code == 200 and sec < 60, (up.status_code, sec)
    body = up.json()["body"]
    assert len(body) > 300 and "스프린트" in body
    m = leader.post(f"/api/teams/{team['id']}/meetings", json={
        "title": "실제 녹음", "met_at": "2026-09-24T05:00:00Z", "attendees": "김대리, 박과장, 이주임", "body": body}).json()
    assert m["decision_count"] >= 2 and m["todo_total_count"] >= 3
    assigned = {t["assignee_name"] for t in leader.get(f"/api/teams/{team['id']}/todos").json()}
    assert {"김대리", "박과장", "이주임"} <= assigned, assigned
    print(f"\n[실제 Gemini] 받아쓰기 {sec:.1f}초, 본문 {len(body)}자, 결정 {m['decision_count']}, 할 일 {m['todo_total_count']}")
