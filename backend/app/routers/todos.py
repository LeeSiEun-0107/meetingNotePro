from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import case
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user, membership_of, owner_only, team_member
from ..errors import ApiError
from ..models import Meeting, Membership, Todo, User
from ..util import log_activity, user_name

router = APIRouter(tags=["Todo"])

STATUSES = ("OPEN", "DOING", "DONE")


class TodoUpdate(BaseModel):
    status: str | None = None
    assignee_id: int | None = None
    due_text: str | None = None


def _order():
    return (
        case((Todo.status == "OPEN", 0), (Todo.status == "DOING", 1), else_=2),
        Todo.due_text,
        Todo.id,
    )


def todo_item(t: Todo, meeting: Meeting, db: Session) -> dict:
    return {
        "id": t.id,
        "what": t.what,
        "assignee_id": t.assignee_id,
        "assignee_name": user_name(db, t.assignee_id),
        "due_text": t.due_text,
        "status": t.status,
        "meeting_id": meeting.id,
        "meeting_title": meeting.title,
    }


def _todo_or_404(todo_id: int, db: Session) -> tuple[Todo, Meeting]:
    t = db.get(Todo, todo_id)
    if t is None:
        raise ApiError("NOT_FOUND", "없는 할 일")
    return t, db.get(Meeting, t.meeting_id)


@router.get("/api/teams/{team_id}/todos", summary="팀 전체 할 일 (회의록 제목 포함)")
def team_todos(team_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    team_member(team_id, user, db)
    rows = (
        db.query(Todo, Meeting).join(Meeting, Meeting.id == Todo.meeting_id)
        .filter(Meeting.team_id == team_id).order_by(*_order()).all()
    )
    return [todo_item(t, m, db) for t, m in rows]


@router.get("/api/me/todos", summary="내게 배정된 할 일")
def my_todos(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = (
        db.query(Todo, Meeting).join(Meeting, Meeting.id == Todo.meeting_id)
        .filter(Todo.assignee_id == user.id).order_by(*_order()).all()
    )
    return [todo_item(t, m, db) for t, m in rows]


@router.put("/api/todos/{todo_id}", summary="할 일 상태 · 담당자 · 기한 변경 (팀원 누구나)")
def update_todo(todo_id: int, body: TodoUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    t, meeting = _todo_or_404(todo_id, db)
    team_member(meeting.team_id, user, db)
    sent = body.model_fields_set

    if "status" in sent:
        if body.status not in STATUSES:
            raise ApiError("VALIDATION_ERROR", "상태는 OPEN, DOING, DONE 중 하나")
    if "assignee_id" in sent and body.assignee_id is not None:
        ok = db.query(Membership).filter(Membership.team_id == meeting.team_id,
                                         Membership.user_id == body.assignee_id).first()
        if ok is None:
            raise ApiError("VALIDATION_ERROR", "담당자는 팀 멤버여야 함")
    if "due_text" in sent and not (body.due_text or "").strip():
        raise ApiError("VALIDATION_ERROR", "기한 글자는 비울 수 없음. 없으면 미정")

    if "status" in sent and body.status != t.status:
        t.status = body.status
        if body.status == "DONE":
            log_activity(db, meeting.team_id, user.id, "todo_done", t.what)
    if "assignee_id" in sent and body.assignee_id != t.assignee_id:
        t.assignee_id = body.assignee_id
        log_activity(db, meeting.team_id, user.id, "todo_assign",
                     f"{t.what}\t{user_name(db, body.assignee_id)}")
    if "due_text" in sent:
        t.due_text = body.due_text.strip()
    db.commit()
    return todo_item(t, meeting, db)


@router.delete("/api/todos/{todo_id}", status_code=204, summary="할 일 삭제 (owner)")
def delete_todo(todo_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    t, meeting = _todo_or_404(todo_id, db)
    owner_only(team_member(meeting.team_id, user, db))
    db.delete(t)
    db.commit()
