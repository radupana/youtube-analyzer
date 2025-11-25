from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class VideoStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    ERROR = "error"  # No transcript available


class VideoBase(BaseModel):
    id: str = Field(..., description="YouTube video ID")
    title: str = Field(..., description="Video title")
    channel_id: str = Field(..., description="Channel ID")
    channel_title: str = Field(..., description="Channel name")
    duration: str = Field(..., description="ISO 8601 duration")
    published_at: datetime = Field(..., description="Publication date")


class VideoCreate(BaseModel):
    url: str = Field(..., description="YouTube video/channel/playlist URL")
    max_videos: int = Field(50, ge=1, le=500, description="Max videos for channels")
    load_transcripts: bool = Field(
        True, description="Whether to load transcripts (slower but needed for chat)"
    )


class Video(VideoBase):
    status: VideoStatus = Field(VideoStatus.PENDING)
    transcript: str | None = None
    transcript_source: str | None = Field(
        None, description="Source of transcript: 'youtube' or 'whisper'"
    )
    description: str | None = None
    view_count: int | None = None
    like_count: int | None = None
    created_at: datetime = Field(default_factory=datetime.now)


class VideoList(BaseModel):
    videos: list[Video]
    total: int


class ChatMessage(BaseModel):
    content: str = Field(..., min_length=1, max_length=10000)
    role: str = Field("user", pattern="^(user|assistant)$")
    timestamp: datetime = Field(default_factory=datetime.now)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=10000)
    session_id: str | None = None


class ChatResponse(BaseModel):
    response: str
    session_id: str
    timestamp: datetime = Field(default_factory=datetime.now)


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskResponse(BaseModel):
    task_id: str
    status: TaskStatus
    progress: float = Field(0.0, ge=0.0, le=100.0)
    result: dict | None = None
    error: str | None = None


class ApiResponse(BaseModel):
    success: bool
    data: dict | None = None
    error: dict | None = None


class ErrorResponse(BaseModel):
    code: str
    message: str
    details: dict | None = None
