"""DB 7테이블. 로컬 SQLite 와 배포 Neon Postgres 에서 같은 모델을 쓴다."""
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Team(Base):
    __tablename__ = "teams"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    invite_code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Membership(Base):
    __tablename__ = "memberships"
    # 한 사람은 한 팀에만 속한다
    __table_args__ = (UniqueConstraint("user_id", name="uq_membership_user"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    role: Mapped[str] = mapped_column(String(10))  # owner | member
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Meeting(Base):
    __tablename__ = "meetings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    met_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    attendees: Mapped[str] = mapped_column(Text, default="")
    body: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text, default="")
    decisions: Mapped[str] = mapped_column(Text, default="")  # 줄바꿈 구분 TEXT
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    todos = relationship("Todo", cascade="all, delete-orphan", passive_deletes=False)
    comments = relationship("Comment", cascade="all, delete-orphan", passive_deletes=False)


class Todo(Base):
    __tablename__ = "todos"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    meeting_id: Mapped[int] = mapped_column(ForeignKey("meetings.id"), index=True)
    what: Mapped[str] = mapped_column(Text)
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    due_text: Mapped[str] = mapped_column(String(100), default="미정")
    status: Mapped[str] = mapped_column(String(10), default="OPEN")  # OPEN | DOING | DONE


class Comment(Base):
    __tablename__ = "comments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    meeting_id: Mapped[int] = mapped_column(ForeignKey("meetings.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Activity(Base):
    __tablename__ = "activities"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    target: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
