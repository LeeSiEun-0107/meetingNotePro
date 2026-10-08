from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..config import ACTIVITY_LIMIT
from ..db import get_db
from ..deps import current_user, team_member
from ..models import Activity, User
from ..util import activity_text, iso

router = APIRouter(tags=["Activity"])


def _items(rows, db: Session) -> list[dict]:
    names = {u.id: u.name for u in db.query(User).filter(User.id.in_({a.actor_id for a in rows})).all()} if rows else {}
    return [
        {
            "id": a.id,
            "kind": a.kind,
            "actor_name": names.get(a.actor_id, "알 수 없음"),
            "text": activity_text(a.kind, a.target),
            "created_at": iso(a.created_at),
        }
        for a in rows
    ]


@router.get("/api/teams/{team_id}/activities", summary="팀 활동 (최근 순, 최근 50건)")
def team_activities(team_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    team_member(team_id, user, db)
    rows = (
        db.query(Activity).filter(Activity.team_id == team_id)
        .order_by(Activity.created_at.desc(), Activity.id.desc()).limit(ACTIVITY_LIMIT).all()
    )
    return _items(rows, db)


@router.get("/api/me/activities", summary="내 활동 (최근 순, 최근 50건)")
def my_activities(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = (
        db.query(Activity).filter(Activity.actor_id == user.id)
        .order_by(Activity.created_at.desc(), Activity.id.desc()).limit(ACTIVITY_LIMIT).all()
    )
    return _items(rows, db)
