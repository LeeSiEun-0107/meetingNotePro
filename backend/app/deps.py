from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .db import get_db
from .errors import ApiError
from .models import Membership, Team, User
from .security import read_token

# auto_error=False: 토큰이 없을 때 {code, msg} 형식으로 직접 답하기 위함.
# 이 스킴 덕분에 Swagger UI(/docs)에 Authorize 버튼이 생긴다.
bearer = HTTPBearer(auto_error=False, description="로그인 응답의 token 값을 그대로 넣는다")


def current_user(
    cred: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if cred is None or not cred.credentials:
        raise ApiError("UNAUTHORIZED", "로그인이 필요함")
    user = db.get(User, read_token(cred.credentials))
    if user is None:
        raise ApiError("UNAUTHORIZED", "로그인이 필요함")
    return user


def membership_of(db: Session, user_id: int) -> Membership | None:
    return db.query(Membership).filter(Membership.user_id == user_id).first()


def team_member(team_id: int, user: User, db: Session) -> Membership:
    """호출자가 그 팀의 멤버인지 본다. 팀이 없거나 멤버가 아니면 FORBIDDEN."""
    m = db.query(Membership).filter(Membership.team_id == team_id, Membership.user_id == user.id).first()
    if m is None:
        raise ApiError("FORBIDDEN", "이 팀의 멤버가 아님")
    return m


def owner_only(m: Membership) -> None:
    if m.role != "owner":
        raise ApiError("OWNER_ONLY", "owner 만 할 수 있음")


def get_team(team_id: int, db: Session) -> Team:
    team = db.get(Team, team_id)
    if team is None:
        raise ApiError("NOT_FOUND", "없는 팀")
    return team
