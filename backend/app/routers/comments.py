from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..config import MAX_COMMENT_LEN
from ..db import get_db
from ..deps import current_user, team_member
from ..errors import ApiError
from ..models import Comment, Meeting, Membership, User
from ..util import iso, log_activity

router = APIRouter(tags=["Comment"])


class CommentIn(BaseModel):
    content: str


def _meeting_or_404(meeting_id: int, db: Session) -> Meeting:
    m = db.get(Meeting, meeting_id)
    if m is None:
        raise ApiError("MEETING_NOT_FOUND", "없는 회의록")
    return m


def _item(c: Comment, user: User, membership: Membership, db: Session) -> dict:
    author = db.get(User, c.user_id)
    return {
        "id": c.id,
        "user_id": c.user_id,
        "user_name": author.name if author else "알 수 없음",
        "content": c.content,
        "created_at": iso(c.created_at),
        # 쓴 사람과 owner 만 지울 수 있으므로 서버가 판정한다
        "can_delete": c.user_id == user.id or membership.role == "owner",
    }


@router.post("/api/meetings/{meeting_id}/comments", status_code=201, summary="댓글 작성 (500자 이내)")
def add_comment(meeting_id: int, body: CommentIn, user: User = Depends(current_user),
                db: Session = Depends(get_db)):
    meeting = _meeting_or_404(meeting_id, db)
    membership = team_member(meeting.team_id, user, db)
    content = body.content.strip()
    if not content:
        raise ApiError("VALIDATION_ERROR", "댓글 내용을 입력해야 함")
    if len(content) > MAX_COMMENT_LEN:
        raise ApiError("VALIDATION_ERROR", f"댓글은 {MAX_COMMENT_LEN}자 이내")
    c = Comment(meeting_id=meeting_id, user_id=user.id, content=content)
    db.add(c)
    log_activity(db, meeting.team_id, user.id, "comment_add", meeting.title)
    db.commit()
    return _item(c, user, membership, db)


@router.get("/api/meetings/{meeting_id}/comments", summary="댓글 목록 (오래된 순)")
def list_comments(meeting_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    meeting = _meeting_or_404(meeting_id, db)
    membership = team_member(meeting.team_id, user, db)
    rows = (
        db.query(Comment).filter(Comment.meeting_id == meeting_id)
        .order_by(Comment.created_at, Comment.id).all()
    )
    return [_item(c, user, membership, db) for c in rows]


@router.delete("/api/comments/{comment_id}", status_code=204, summary="댓글 삭제 (쓴 사람과 owner)")
def delete_comment(comment_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    c = db.get(Comment, comment_id)
    if c is None:
        raise ApiError("NOT_FOUND", "없는 댓글")
    meeting = db.get(Meeting, c.meeting_id)
    membership = team_member(meeting.team_id, user, db)
    if c.user_id != user.id and membership.role != "owner":
        raise ApiError("FORBIDDEN", "쓴 사람과 owner 만 지울 수 있음")
    db.delete(c)
    db.commit()
