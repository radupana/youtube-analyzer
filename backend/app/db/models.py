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
    session_videos: list["SessionVideo"] = Relationship(
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


class Video(SQLModel, table=True):
    """Global video storage - one record per YouTube video."""

    id: str = Field(primary_key=True)
    title: str
    channel_id: str
    channel_title: str
    description: str | None = None
    duration: str
    published_at: datetime
    view_count: int = 0
    like_count: int = 0
    transcript: str | None = None
    transcript_source: str | None = None
    created_at: datetime = Field(default_factory=utc_now)

    chunks: list["Chunk"] = Relationship(
        back_populates="video",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class Chunk(SQLModel, table=True):
    """Transcript chunk with embedding for RAG retrieval."""

    id: str = Field(primary_key=True)
    video_id: str = Field(foreign_key="video.id", index=True)
    text: str
    start_time: float
    end_time: float
    token_count: int
    embedding: bytes

    video: Video = Relationship(back_populates="chunks")


class SessionVideo(SQLModel, table=True):
    """Links sessions to videos (many-to-many)."""

    __tablename__ = "session_video"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    session_id: str = Field(foreign_key="session.id", index=True)
    video_id: str = Field(foreign_key="video.id", index=True)
    added_at: datetime = Field(default_factory=utc_now)

    session: Session = Relationship(back_populates="session_videos")
    video: Video = Relationship()


class VideoAnalysis(SQLModel, table=True):
    """Cached video analysis result."""

    __tablename__ = "video_analysis"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    video_id: str = Field(foreign_key="video.id", index=True, unique=True)
    summary: str
    key_takeaways: str
    main_topics: str
    notable_quotes: str
    model_used: str
    created_at: datetime = Field(default_factory=utc_now)
