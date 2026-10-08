from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user, membership_of
from ..errors import ApiError
from ..models import Membership, Team, User
from ..security import hash_password, make_token, verify_password
from ..util import EMAIL_RE, log_activity
from ..config import MAX_TEAM_MEMBERS

router = APIRouter(prefix="/api/auth", tags=["Auth"])


class SignupIn(BaseModel):
    email: str
    password: str
    name: str
    invite_code: str | None = None


class LoginIn(BaseModel):
    email: str
    password: str


class MeUpdate(BaseModel):
    name: str | None = None
    current_password: str | None = None
    password: str | None = None


def me_payload(db: Session, user: User) -> dict:
    m = membership_of(db, user.id)
    team = db.get(Team, m.team_id) if m else None
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": m.role if m else None,
        "team_id": team.id if team else None,
        "team_name": team.name if team else None,
    }


@router.post("/signup", status_code=201, summary="회원가입 (201 + JWT)")
def signup(body: SignupIn, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    if not EMAIL_RE.match(email):
        raise ApiError("EMAIL_INVALID", "이메일 형식이 올바르지 않음")
    if len(body.password) < 8:
        raise ApiError("PASSWORD_TOO_WEAK", "비밀번호는 8자 이상")
    name = body.name.strip()
    if not name:
        raise ApiError("VALIDATION_ERROR", "이름을 입력해야 함")
    if db.query(User).filter(User.email == email).first():
        raise ApiError("EMAIL_DUPLICATED", "이미 가입된 이메일")

    user = User(email=email, password_hash=hash_password(body.password), name=name)
    db.add(user)
    db.flush()

    code = (body.invite_code or "").strip().upper()
    if code:
        team = db.query(Team).filter(Team.invite_code == code).first()
        if team is None:
            db.commit()  # 가입은 되고 합류만 실패
            raise ApiError("INVITE_NOT_FOUND", "없는 초대코드")
        if db.query(Membership).filter(Membership.team_id == team.id).count() >= MAX_TEAM_MEMBERS:
            db.commit()
            raise ApiError("TEAM_FULL", "팀 정원이 찼음")
        db.add(Membership(team_id=team.id, user_id=user.id, role="member"))
        log_activity(db, team.id, user.id, "member_join", team.name)
    db.commit()
    return {"token": make_token(user.id), "token_type": "bearer", "user": me_payload(db, user)}


@router.post("/login", summary="로그인 (200 + JWT, 24시간)")
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email.strip().lower()).first()
    # 이메일이 있는지 알리지 않으려고 같은 오류로 통일
    if user is None or not verify_password(body.password, user.password_hash):
        raise ApiError("INVALID_CREDENTIALS", "이메일 또는 비밀번호가 올바르지 않음")
    return {"token": make_token(user.id), "token_type": "bearer", "user": me_payload(db, user)}


@router.get("/me", summary="내 정보 (소속 팀 id · 팀 이름 포함)")
def me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return me_payload(db, user)


@router.put("/me", summary="내 이름 · 비밀번호 수정 (비밀번호는 현재 비밀번호 필요)")
def update_me(body: MeUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if body.name is not None:
        name = body.name.strip()
        if not name:
            raise ApiError("VALIDATION_ERROR", "이름을 입력해야 함")
        user.name = name
    if body.password:
        if not body.current_password:
            raise ApiError("VALIDATION_ERROR", "현재 비밀번호가 필요함")
        if not verify_password(body.current_password, user.password_hash):
            raise ApiError("UNAUTHORIZED", "현재 비밀번호가 틀림")
        if len(body.password) < 8:
            raise ApiError("PASSWORD_TOO_WEAK", "비밀번호는 8자 이상")
        user.password_hash = hash_password(body.password)
    db.commit()
    return me_payload(db, user)


@router.post("/logout", summary="로그아웃 (200). 토큰은 화면이 지운다")
def logout(_: User = Depends(current_user)):
    return {"ok": True}
