from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from . import config
from .errors import ApiError

ALGO = "HS256"


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode("utf-8"), hashed.encode("ascii"))
    except ValueError:
        return False


def make_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "iat": now, "exp": now + timedelta(hours=config.TOKEN_HOURS)}
    return jwt.encode(payload, config.jwt_secret(), algorithm=ALGO)


def read_token(token: str) -> int:
    try:
        data = jwt.decode(token, config.jwt_secret(), algorithms=[ALGO])
        return int(data["sub"])
    except jwt.ExpiredSignatureError:
        raise ApiError("TOKEN_EXPIRED", "세션이 만료됨. 다시 로그인 필요")
    except (jwt.PyJWTError, KeyError, ValueError):
        raise ApiError("UNAUTHORIZED", "로그인이 필요함")
