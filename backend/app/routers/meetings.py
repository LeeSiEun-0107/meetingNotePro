from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session

from .. import ai
from ..db import get_db
from ..deps import current_user, team_member
from ..errors import ApiError
from ..models import Meeting, Membership, Todo, User
from ..util import iso, log_activity, parse_iso

router = APIRouter(tags=["Meeting"])


class MeetingCreate(BaseModel):
    title: str
    met_at: str
    attendees: str = ""
    body: str


class MeetingUpdate(BaseModel):
    title: str | None = None
    met_at: str | None = None
    attendees: str | None = None
    body: str | None = None


def _lines(text: str) -> list[str]:
    return [ln for ln in (text or "").split("\n") if ln.strip()]


def _counts(db: Session, ids: list[int]) -> dict[int, tuple[int, int]]:
    if not ids:
        return {}
    rows = (
        db.query(Todo.meeting_id, func.count(Todo.id), func.sum(case((Todo.status == "DONE", 1), else_=0)))
        .filter(Todo.meeting_id.in_(ids))
        .group_by(Todo.meeting_id)
        .all()
    )
    return {mid: (int(total), int(done or 0)) for mid, total, done in rows}


def list_item(m: Meeting, counts: dict) -> dict:
    total, done = counts.get(m.id, (0, 0))
    return {
        "id": m.id,
        "title": m.title,
        "met_at": iso(m.met_at),
        "attendees": m.attendees,
        "summary": m.summary,
        "created_at": iso(m.created_at),
        "author_id": m.author_id,
        "todo_done_count": done,
        "todo_total_count": total,
        "decision_count": len(_lines(m.decisions)),
    }


def detail_item(m: Meeting, db: Session) -> dict:
    d = list_item(m, _counts(db, [m.id]))
    d["decisions"] = m.decisions
    d["body"] = m.body  # 단건 조회에만 본문을 싣는다
    return d


def _meeting_or_404(meeting_id: int, db: Session) -> Meeting:
    m = db.get(Meeting, meeting_id)
    if m is None:
        raise ApiError("MEETING_NOT_FOUND", "없는 회의록")
    return m


def _can_edit(m: Meeting, user: User, membership: Membership) -> bool:
    return m.author_id == user.id or membership.role == "owner"


@router.post("/api/teams/{team_id}/meetings", status_code=201,
             summary="회의록 저장 (본문을 요약 · 결정사항 · 할 일로 나눠 함께 저장)")
def create_meeting(team_id: int, body: MeetingCreate, user: User = Depends(current_user),
                   db: Session = Depends(get_db)):
    team_member(team_id, user, db)
    title, text = body.title.strip(), body.body.strip()
    if not title or not text or not body.met_at.strip():
        raise ApiError("VALIDATION_ERROR", "제목, 회의 시각, 본문은 필수")
    try:
        met_at = parse_iso(body.met_at)
    except ValueError:
        raise ApiError("VALIDATION_ERROR", "회의 시각은 ISO 8601 형식이어야 함")

    members = (
        db.query(User).join(Membership, Membership.user_id == User.id)
        .filter(Membership.team_id == team_id).all()
    )
    names = {u.name: u.id for u in members}

    summary, decisions, todos = "", [], []
    try:
        parts = ai.split_meeting(text, list(names))
        summary, decisions, todos = parts["summary"], parts["decisions"], parts["todos"]
    except ai.AiError:
        # 구분에 실패해도 본문은 남긴다. 세 항목은 비워 둔다
        pass

    m = Meeting(team_id=team_id, title=title, met_at=met_at, attendees=body.attendees.strip(),
                body=text, summary=summary, decisions="\n".join(decisions), author_id=user.id)
    db.add(m)
    db.flush()
    for t in todos:
        db.add(Todo(meeting_id=m.id, what=t["what"], assignee_id=names.get(t["assignee"]),
                    due_text=t["due"] or "미정", status="OPEN"))
    log_activity(db, team_id, user.id, "meeting_add", title)
    db.commit()
    return detail_item(m, db)


@router.get("/api/teams/{team_id}/meetings", summary="회의록 목록 (본문 없음). ?q= 제목·참석자, ?from=&to= 기간")
def list_meetings(team_id: int, q: str | None = None, from_: str | None = Query(None, alias="from"),
                  to: str | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    team_member(team_id, user, db)
    query = db.query(Meeting).filter(Meeting.team_id == team_id)
    if q and q.strip():
        like = f"%{q.strip()}%"
        query = query.filter(or_(Meeting.title.like(like), Meeting.attendees.like(like)))
    try:
        if from_:
            query = query.filter(Meeting.met_at >= parse_iso(from_))
        if to:
            end = parse_iso(to)
            if len(to.strip()) <= 10:  # 날짜만 오면 그날 끝까지
                end = end.replace(hour=23, minute=59, second=59)
            query = query.filter(Meeting.met_at <= end)
    except ValueError:
        raise ApiError("VALIDATION_ERROR", "기간은 ISO 날짜여야 함")
    rows = query.order_by(Meeting.met_at.desc(), Meeting.id.desc()).all()
    counts = _counts(db, [m.id for m in rows])
    return [list_item(m, counts) for m in rows]


@router.get("/api/meetings/{meeting_id}", summary="회의록 한 건 (본문 포함)")
def get_meeting(meeting_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    m = _meeting_or_404(meeting_id, db)
    team_member(m.team_id, user, db)
    return detail_item(m, db)


@router.put("/api/meetings/{meeting_id}", summary="회의록 수정 (올린 사람과 owner). 요약 · 결정 · 할 일은 다시 뽑지 않음")
def update_meeting(meeting_id: int, body: MeetingUpdate, user: User = Depends(current_user),
                   db: Session = Depends(get_db)):
    m = _meeting_or_404(meeting_id, db)
    membership = team_member(m.team_id, user, db)
    if not _can_edit(m, user, membership):
        raise ApiError("FORBIDDEN", "올린 사람과 owner 만 고칠 수 있음")
    if body.title is not None:
        if not body.title.strip():
            raise ApiError("VALIDATION_ERROR", "제목은 비울 수 없음")
        m.title = body.title.strip()
    if body.met_at is not None:
        try:
            m.met_at = parse_iso(body.met_at)
        except ValueError:
            raise ApiError("VALIDATION_ERROR", "회의 시각은 ISO 8601 형식이어야 함")
    if body.attendees is not None:
        m.attendees = body.attendees.strip()
    if body.body is not None:
        if not body.body.strip():
            raise ApiError("VALIDATION_ERROR", "본문은 비울 수 없음")
        m.body = body.body.strip()
    db.commit()
    return detail_item(m, db)


@router.delete("/api/meetings/{meeting_id}", status_code=204,
               summary="회의록 삭제 (올린 사람과 owner). 딸린 할 일도 함께 삭제")
def delete_meeting(meeting_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    m = _meeting_or_404(meeting_id, db)
    membership = team_member(m.team_id, user, db)
    if not _can_edit(m, user, membership):
        raise ApiError("FORBIDDEN", "올린 사람과 owner 만 지울 수 있음")
    db.delete(m)
    db.commit()
