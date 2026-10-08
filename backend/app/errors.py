"""오류는 항상 {code, msg}. 코드는 프로그램정의 7-2 에 적힌 것만 쓴다."""
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

# 문서의 오류 코드 15종
CODES = {
    "EMAIL_INVALID": 400,
    "PASSWORD_TOO_WEAK": 400,
    "TOKEN_EXPIRED": 401,
    "INVITE_NOT_FOUND": 404,
    "MEETING_NOT_FOUND": 404,
    "EMAIL_DUPLICATED": 409,
    "TEAM_FULL": 409,
    "PAYLOAD_TOO_LARGE": 413,
    "UNSUPPORTED_MEDIA_TYPE": 415,
    "INVALID_CREDENTIALS": 401,
    "FORBIDDEN": 403,
    "OWNER_ONLY": 403,
    "VALIDATION_ERROR": 400,
    "NOT_FOUND": 404,
    "UNAUTHORIZED": 401,
}

# 문서에 없는 코드 하나: 받아쓰기 공급자(Gemini) 호출 실패. 화면은 코드와 관계없이 공통 알림만 띄운다
UPSTREAM_ERROR = "UPSTREAM_ERROR"


class ApiError(Exception):
    def __init__(self, code: str, msg: str, status: int | None = None):
        self.code = code
        self.msg = msg
        self.status = status or CODES.get(code, 400)


def install(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api(_: Request, e: ApiError):
        return JSONResponse({"code": e.code, "msg": e.msg}, status_code=e.status)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, e: RequestValidationError):
        first = e.errors()[0] if e.errors() else {}
        loc = ".".join(str(x) for x in first.get("loc", []) if x != "body")
        return JSONResponse(
            {"code": "VALIDATION_ERROR", "msg": f"{loc}: {first.get('msg', '잘못된 요청')}".strip(": ")},
            status_code=400,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, e: StarletteHTTPException):
        code = "NOT_FOUND" if e.status_code == 404 else "VALIDATION_ERROR"
        return JSONResponse({"code": code, "msg": str(e.detail)}, status_code=e.status_code)
