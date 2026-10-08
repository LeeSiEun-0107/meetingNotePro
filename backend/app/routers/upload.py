from fastapi import APIRouter, Depends, UploadFile
from fastapi import File as FormFile

from .. import ai
from ..config import MAX_UPLOAD_BYTES
from ..deps import current_user
from ..errors import UPSTREAM_ERROR, ApiError
from ..models import User

router = APIRouter(prefix="/api", tags=["Meeting"])


def sniff_audio(head: bytes) -> str | None:
    """확장자가 아니라 내용 형식으로 판정한다. mp3 또는 wav 만 받는다."""
    if head[:4] == b"RIFF" and head[8:12] == b"WAVE":
        return "audio/wav"
    if head[:3] == b"ID3":
        return "audio/mpeg"
    if len(head) >= 2 and head[0] == 0xFF and (head[1] & 0xE0) == 0xE0:  # MPEG 프레임 동기
        return "audio/mpeg"
    return None


@router.post("/upload", summary="녹취 파일(mp3 · wav, 4.5MB 이하)을 받아쓴 본문 텍스트만 돌려준다. 파일은 보관하지 않음")
async def upload(file: UploadFile = FormFile(...), user: User = Depends(current_user)):
    data = bytearray()
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        data += chunk
        if len(data) > MAX_UPLOAD_BYTES:
            raise ApiError("PAYLOAD_TOO_LARGE", "4.5MB 를 넘는 파일")
    mime = sniff_audio(bytes(data[:16]))
    if mime is None:
        raise ApiError("UNSUPPORTED_MEDIA_TYPE", "mp3 또는 wav 만 올릴 수 있음")
    try:
        text = ai.transcribe(bytes(data), mime)
    except ai.AiError as e:
        raise ApiError(UPSTREAM_ERROR, f"받아쓰기에 실패함: {e}", status=502)
    return {"body": text}
