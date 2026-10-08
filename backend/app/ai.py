"""Gemini 호출. 받아쓰기와 세 항목 구분을 한 공급자로 한다.

모델은 .env 의 GEMINI_MODEL, 키는 GEMINI_API_KEY. 키가 없거나 호출이 실패하면 AiError.
"""
import base64
import json

import httpx

from . import config

BASE = "https://generativelanguage.googleapis.com"
TIMEOUT = 60.0  # 받아쓰기 60초 이내가 제약
INLINE_LIMIT = 14 * 1024 * 1024  # 이보다 크면 Files API 로 올린다 (요청 본문 20MB 제한 때문)


class AiError(Exception):
    pass


def _headers() -> dict:
    key = config.gemini_api_key()
    if not key:
        raise AiError("GEMINI_API_KEY 가 설정되지 않음")
    return {"x-goog-api-key": key, "Content-Type": "application/json"}


def _generate(parts: list[dict], generation_config: dict | None = None) -> str:
    url = f"{BASE}/v1beta/models/{config.gemini_model()}:generateContent"
    body = {"contents": [{"role": "user", "parts": parts}]}
    if generation_config:
        body["generationConfig"] = generation_config
    try:
        r = httpx.post(url, headers=_headers(), json=body, timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()
        return "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"]).strip()
    except (httpx.HTTPError, KeyError, IndexError, ValueError) as e:
        raise AiError(f"Gemini 호출 실패: {e.__class__.__name__}") from e


def _upload_file(data: bytes, mime: str) -> str:
    """Files API 재개 가능 업로드. file uri 를 돌려준다."""
    key = config.gemini_api_key()
    if not key:
        raise AiError("GEMINI_API_KEY 가 설정되지 않음")
    try:
        start = httpx.post(
            f"{BASE}/upload/v1beta/files",
            headers={
                "x-goog-api-key": key,
                "X-Goog-Upload-Protocol": "resumable",
                "X-Goog-Upload-Command": "start",
                "X-Goog-Upload-Header-Content-Length": str(len(data)),
                "X-Goog-Upload-Header-Content-Type": mime,
                "Content-Type": "application/json",
            },
            json={"file": {"display_name": "meeting-audio"}},
            timeout=TIMEOUT,
        )
        start.raise_for_status()
        up_url = start.headers["x-goog-upload-url"]
        done = httpx.post(
            up_url,
            headers={
                "Content-Length": str(len(data)),
                "X-Goog-Upload-Offset": "0",
                "X-Goog-Upload-Command": "upload, finalize",
            },
            content=data,
            timeout=TIMEOUT,
        )
        done.raise_for_status()
        return done.json()["file"]["uri"]
    except (httpx.HTTPError, KeyError, ValueError) as e:
        raise AiError(f"Gemini 파일 올리기 실패: {e.__class__.__name__}") from e


def transcribe(data: bytes, mime: str) -> str:
    """녹취 파일을 받아쓴 본문 텍스트만 돌려준다. 파일은 보관하지 않는다."""
    if len(data) <= INLINE_LIMIT:
        media = {"inline_data": {"mime_type": mime, "data": base64.b64encode(data).decode("ascii")}}
    else:
        media = {"file_data": {"mime_type": mime, "file_uri": _upload_file(data, mime)}}
    prompt = (
        "이 회의 녹취를 한국어로 받아쓰세요. 들린 말만 그대로 적고 내용을 보태거나 요약하지 마세요. "
        "화자를 구분하지 말고 문장 단위로 줄바꿈하세요. 결과는 받아쓴 본문 텍스트만 출력하세요."
    )
    text = _generate([media, {"text": prompt}])
    if not text:
        raise AiError("받아쓴 내용이 비어 있음")
    return text


_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "summary": {"type": "STRING"},
        "decisions": {"type": "ARRAY", "items": {"type": "STRING"}},
        "todos": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "what": {"type": "STRING"},
                    "assignee": {"type": "STRING"},
                    "due": {"type": "STRING"},
                },
                "required": ["what"],
            },
        },
    },
    "required": ["summary", "decisions", "todos"],
}


def split_meeting(body: str, member_names: list[str]) -> dict:
    """본문을 요약(3~5줄) · 결정사항 · 할 일 세 항목으로 나눈다."""
    prompt = (
        "다음은 회의를 받아쓴 본문입니다. 아래 규칙으로 세 항목을 만드세요.\n"
        "- summary: 회의 전체를 3~5줄로 요약. 줄은 \\n 으로 구분. 본문에 없는 사실을 보태지 않는다.\n"
        "- decisions: 합의가 끝난 것만(하기로 했다, 확정, 승인). 논의만 하고 정하지 않은 것은 넣지 않는다. "
        "합의된 것이 없으면 빈 배열.\n"
        "- todos: 담당자나 기한이 드러난 일만. what 은 할 일 내용, assignee 는 담당자 이름(없으면 빈 문자열), "
        "due 는 본문에 나온 기한 표현 그대로(예: 다음 주 금요일, 이번 주 안, 9월 12일. 없으면 빈 문자열). "
        "없는 담당자나 기한을 지어내지 않는다. 드러난 할 일이 없으면 빈 배열.\n"
        f"팀 멤버 이름: {', '.join(member_names) or '(없음)'}\n\n본문:\n{body}"
    )
    text = _generate(
        [{"text": prompt}],
        {"responseMimeType": "application/json", "responseSchema": _SCHEMA, "temperature": 0.2},
    )
    try:
        data = json.loads(text)
        return {
            "summary": str(data.get("summary", "")).strip(),
            "decisions": [str(x).strip() for x in data.get("decisions", []) if str(x).strip()],
            "todos": [
                {
                    "what": str(t.get("what", "")).strip(),
                    "assignee": str(t.get("assignee", "") or "").strip(),
                    "due": str(t.get("due", "") or "").strip(),
                }
                for t in data.get("todos", [])
                if str(t.get("what", "")).strip()
            ],
        }
    except (ValueError, AttributeError) as e:
        raise AiError("구분 결과를 읽을 수 없음") from e
