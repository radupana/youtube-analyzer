from datetime import UTC, datetime
from uuid import uuid4

from sqlmodel import Field, Relationship, SQLModel


def utc_now() -> datetime:
    return datetime.now(UTC)


class Session(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    title: str = Field(default="Untitled Session")
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    messages: list["Message"] = Relationship(
        back_populates="session",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    videos: list["SessionVideo"] = Relationship(
        back_populates="session",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class Message(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    session_id: str = Field(foreign_key="session.id", index=True)
    role: str
    content: str
    created_at: datetime = Field(default_factory=utc_now)

    session: Session = Relationship(back_populates="messages")


class SessionVideo(SQLModel, table=True):
    __tablename__ = "session_video"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    session_id: str = Field(foreign_key="session.id", index=True)
    video_id: str
    title: str
    channel_title: str
    transcript: str | None = None
    transcript_source: str | None = None
    added_at: datetime = Field(default_factory=utc_now)

    session: Session = Relationship(back_populates="videos")
