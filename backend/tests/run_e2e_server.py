"""브라우저 확인용 서버. Gemini 만 가짜로 바꿔 띄운다 (키 없이 화면 흐름을 보기 위한 개발 도구).

    python backend/tests/run_e2e_server.py <임시 DB 경로> [포트]

실제 서버 실행(uvicorn app.main:app)과 코드는 같고, 아래 두 함수만 바뀐다.
"""
import os
import sys
from pathlib import Path

db = sys.argv[1] if len(sys.argv) > 1 else str(Path.home() / "mnp-e2e.db")
port = int(sys.argv[2]) if len(sys.argv) > 2 else 8000
Path(db).unlink(missing_ok=True)
os.environ["DATABASE_URL"] = "sqlite:///" + db.replace("\\", "/")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import uvicorn  # noqa: E402

from app import ai  # noqa: E402


def fake_split(body, names):
    todos = []
    if names:
        todos.append({"what": "목록 화면 및 검색 구현", "assignee": names[0], "due": "다음 주 금요일"})
        todos.append({"what": "받아쓰기 오류 처리", "assignee": names[-1], "due": "어제"})
    todos.append({"what": "사용자 다섯 분 인터뷰", "assignee": "", "due": ""})
    return {
        "summary": "회의록 정리기 2차 스프린트 계획을 다루었다.\n검색 범위를 제목과 참석자로 확정했다.\n업로드 용량은 25MB 로 제한하기로 했다.",
        "decisions": ["목록 검색은 제목과 참석자 범위로 한정", "업로드 용량 상한은 25MB"],
        "todos": todos,
    }


ai.split_meeting = fake_split
ai.transcribe = lambda data, mime: "김대리: 목록 화면 검색 범위를 제목과 참석자로 하겠습니다.\n박과장: 업로드 용량은 25MB 로 제한하죠."

from app.main import app  # noqa: E402

uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
