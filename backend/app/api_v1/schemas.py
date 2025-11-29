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
    url: str = Field(
        ...,
        description="YouTube video URL (e.g., https://youtube.com/watch?v=...)",
    )
    session_id: str = Field(..., description="Session ID to add video to")


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


class SessionCreate(BaseModel):
    title: str | None = Field(None, max_length=200)


class SessionUpdate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)


class SessionResponse(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime


class SessionSummary(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    video_count: int
    message_count: int


class SessionListResponse(BaseModel):
    sessions: list[SessionSummary]
    total: int


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    created_at: datetime


class SessionVideoResponse(BaseModel):
    id: str
    video_id: str
    title: str
    channel_title: str
    transcript_source: str | None
    added_at: datetime


class SessionDetailResponse(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    messages: list[MessageResponse]
    videos: list[SessionVideoResponse]


class TranscriptSegmentSchema(BaseModel):
    text: str
    start_time: float
    end_time: float


class TranscriptResponse(BaseModel):
    video_id: str
    video_title: str
    full_text: str
    segments: list[TranscriptSegmentSchema]
    has_timestamps: bool


class PatternSummaryResponse(BaseModel):
    id: str
    name: str
    description: str
    icon: str
    category: str


class PatternListResponse(BaseModel):
    patterns: list[PatternSummaryResponse]


class PatternResultResponse(BaseModel):
    video_id: str
    pattern_id: str
    pattern_name: str
    result: str
    model_used: str
    created_at: datetime
