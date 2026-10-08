import re
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from .models import Activity, User

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def iso(dt: datetime | None) -> str | None:
    """저장은 UTC. 응답은 ISO 8601 UTC 로 낸다. 현지 시간 표시는 화면이 한다."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(value: str) -> datetime:
    """ISO 8601 문자열을 UTC naive datetime 으로. 타임존이 없으면 UTC 로 본다."""
    v = value.strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(v)
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


KINDS = ("meeting_add", "todo_assign", "todo_done", "comment_add", "member_join")


def log_activity(db: Session, team_id: int, actor_id: int, kind: str, target: str = "") -> None:
    assert kind in KINDS
    db.add(Activity(team_id=team_id, actor_id=actor_id, kind=kind, target=target))


def activity_text(kind: str, target: str) -> str:
    """서버가 만든 완성 문장. 화면은 그대로 그린다."""
    if kind == "meeting_add":
        return f"회의록 「{target}」 등록"
    if kind == "todo_assign":
        # target 은 「내용\t담당자 이름」
        what, _, who = target.partition("\t")
        return f"할 일 「{what}」를 {who or '미정'}에게 배정"
    if kind == "todo_done":
        return f"할 일 「{target}」 완료"
    if kind == "comment_add":
        return f"회의록 「{target}」에 댓글 작성"
    if kind == "member_join":
        return f"{target}에 합류" if target else "초대코드로 합류"
    return target


def user_name(db: Session, uid: int | None) -> str:
    if uid is None:
        return "미정"
    u = db.get(User, uid)
    return u.name if u else "미정"
