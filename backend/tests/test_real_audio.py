"""실제 Gemini 로 녹취 파일을 받아쓴다. 키와 비용이 들어서 기본으로는 건너뛴다.

    REAL_GEMINI=1 REAL_WAV=C:\경로\회의_녹음.wav [REAL_MP3=C:\경로\회의_녹음.mp3] pytest tests/test_real_audio.py
"""
import os
from pathlib import Path

import pytest

from app import ai, config
from app.routers.upload import sniff_audio
from conftest import signup

pytestmark = pytest.mark.skipif(
    os.getenv("REAL_GEMINI") != "1" or not config.gemini_api_key(),
    reason="REAL_GEMINI=1 과 GEMINI_API_KEY 가 있을 때만 실행",
)


@pytest.fixture(autouse=True)
def real_ai(monkeypatch):
    """conftest 의 가짜 AI 를 되돌려 실제 함수를 쓴다."""
    import importlib
    real = importlib.reload(ai)
    monkeypatch.setattr("app.routers.upload.ai", real)
    monkeypatch.setattr("app.routers.meetings.ai", real)


def _file(env):
    p = os.getenv(env)
    if not p or not Path(p).is_file():
        pytest.skip(f"{env} 파일이 없음")
    return Path(p).read_bytes()


@pytest.mark.parametrize("env, mime, name", [("REAL_WAV", "audio/wav", "a.wav"), ("REAL_MP3", "audio/mpeg", "a.mp3")])
def test_real_file_is_transcribed_through_the_api(client, team, env, mime, name):
    data = _file(env)
    assert len(data) <= config.MAX_UPLOAD_BYTES and sniff_audio(data[:16]) == mime
    r = client.post("/api/upload", files={"file": (name, data, mime)}, headers=team["park"].h)
    assert r.status_code == 200, r.text
    assert len(r.json()["body"]) > 100


def test_real_transcript_becomes_a_meeting_with_three_items(client, team):
    body = client.post("/api/upload", files={"file": ("a.wav", _file("REAL_WAV"), "audio/wav")},
                       headers=team["park"].h).json()["body"]
    r = client.post(f"/api/teams/{team['id']}/meetings", headers=team["park"].h,
                    json={"title": "실제 녹음", "met_at": "2026-09-24T05:00:00Z", "attendees": "김대리, 박과장, 이주임", "body": body})
    assert r.status_code == 201
    d = r.json()
    assert d["summary"] and d["decision_count"] >= 1 and d["todo_total_count"] >= 1
