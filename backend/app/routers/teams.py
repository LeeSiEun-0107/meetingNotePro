import secrets

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import MAX_TEAM_MEMBERS
from ..db import get_db
from ..deps import current_user, get_team, membership_of, owner_only, team_member
from ..errors import ApiError
from ..models import Meeting, Membership, Team, Todo, User
from ..util import log_activity

router = APIRouter(prefix="/api/teams", tags=["Team"])

_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


class TeamCreate(BaseModel):
    name: str


class JoinIn(BaseModel):
    invite_code: str


class TeamRename(BaseModel):
    name: str


def new_invite_code(db: Session) -> str:
    while True:
        code = "MN-" + "".join(secrets.choice(_ALPHABET) for _ in range(4))
        if not db.query(Team).filter(Team.invite_code == code).first():
            return code


def team_dict(db: Session, team: Team, role: str) -> dict:
    count = db.query(Membership).filter(Membership.team_id == team.id).count()
    return {
        "id": team.id,
        "name": team.name,
        "invite_code": team.invite_code,
        "owner_id": team.owner_id,
        "role": role,
        "member_count": count,
    }


@router.post("", status_code=201, summary="팀 만들기 (만든 사람이 owner)")
def create_team(body: TeamCreate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    name = body.name.strip()
    if not name:
        raise ApiError("VALIDATION_ERROR", "팀 이름을 입력해야 함")
    if membership_of(db, user.id):
        raise ApiError("VALIDATION_ERROR", "이미 소속 팀이 있음")
    team = Team(name=name, invite_code=new_invite_code(db), owner_id=user.id)
    db.add(team)
    db.flush()
    db.add(Membership(team_id=team.id, user_id=user.id, role="owner"))
    db.commit()
    return team_dict(db, team, "owner")


@router.get("", summary="내 팀 목록 (한 사람은 한 팀만 속하므로 0개 또는 1개)")
def my_teams(user: User = Depends(current_user), db: Session = Depends(get_db)):
    m = membership_of(db, user.id)
    if m is None:
        return []
    return [team_dict(db, db.get(Team, m.team_id), m.role)]


@router.post("/join", summary="초대코드로 합류")
def join_team(body: JoinIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if membership_of(db, user.id):
        raise ApiError("VALIDATION_ERROR", "이미 소속 팀이 있음")
    team = db.query(Team).filter(Team.invite_code == body.invite_code.strip().upper()).first()
    if team is None:
        raise ApiError("INVITE_NOT_FOUND", "없는 초대코드")
    if db.query(Membership).filter(Membership.team_id == team.id).count() >= MAX_TEAM_MEMBERS:
        raise ApiError("TEAM_FULL", "팀 정원이 찼음")
    db.add(Membership(team_id=team.id, user_id=user.id, role="member"))
    log_activity(db, team.id, user.id, "member_join", team.name)
    db.commit()
    return team_dict(db, team, "member")


@router.get("/{team_id}/members", summary="멤버 목록 (1인당 할 일 수 포함)")
def members(team_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    team_member(team_id, user, db)
    rows = (
        db.query(Membership, User)
        .join(User, User.id == Membership.user_id)
        .filter(Membership.team_id == team_id)
        .order_by(Membership.joined_at, Membership.id)
        .all()
    )
    counts = dict(
        db.query(Todo.assignee_id, func.count(Todo.id))
        .join(Meeting, Meeting.id == Todo.meeting_id)
        .filter(Meeting.team_id == team_id, Todo.assignee_id.isnot(None))
        .group_by(Todo.assignee_id)
        .all()
    )
    return [
        {"id": u.id, "name": u.name, "email": u.email, "role": m.role, "todo_count": counts.get(u.id, 0)}
        for m, u in rows
    ]


@router.put("/{team_id}/code", summary="초대코드 재발급 (owner). 앞의 코드는 못 씀")
def reissue_code(team_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    owner_only(team_member(team_id, user, db))
    team = get_team(team_id, db)
    team.invite_code = new_invite_code(db)
    db.commit()
    return {"invite_code": team.invite_code}


@router.put("/{team_id}", summary="팀 이름 변경 (owner)")
def rename_team(team_id: int, body: TeamRename, user: User = Depends(current_user), db: Session = Depends(get_db)):
    owner_only(team_member(team_id, user, db))
    name = body.name.strip()
    if not name:
        raise ApiError("VALIDATION_ERROR", "팀 이름을 입력해야 함")
    team = get_team(team_id, db)
    team.name = name
    db.commit()
    return team_dict(db, team, "owner")
