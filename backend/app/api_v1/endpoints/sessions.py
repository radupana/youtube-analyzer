from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, func, select

from app.api_v1.schemas import (
    MessageResponse,
    SessionCreate,
    SessionDetailResponse,
    SessionListResponse,
    SessionResponse,
    SessionSummary,
    SessionUpdate,
    SessionVideoResponse,
)
from app.db.database import get_session
from app.db.models import Message, SessionVideo, Video, utc_now
from app.db.models import Session as DBSession

router = APIRouter()


@router.get("", response_model=SessionListResponse)
def list_sessions(db: Session = Depends(get_session)):
    # Subquery for video counts per session
    video_counts = (
        select(SessionVideo.session_id, func.count().label("count"))
        .group_by(SessionVideo.session_id)
        .subquery()
    )

    # Subquery for message counts per session
    message_counts = (
        select(Message.session_id, func.count().label("count"))
        .group_by(Message.session_id)
        .subquery()
    )

    # Main query with LEFT JOINs to get counts in single query
    query = (
        select(
            DBSession,
            func.coalesce(video_counts.c.count, 0).label("video_count"),
            func.coalesce(message_counts.c.count, 0).label("message_count"),
        )
        .outerjoin(video_counts, DBSession.id == video_counts.c.session_id)  # type: ignore[arg-type]
        .outerjoin(message_counts, DBSession.id == message_counts.c.session_id)  # type: ignore[arg-type]
        .order_by(DBSession.updated_at.desc())
    )

    results = db.exec(query).all()

    summaries = [
        SessionSummary(
            id=row[0].id,
            title=row[0].title,
            created_at=row[0].created_at,
            updated_at=row[0].updated_at,
            video_count=row[1],
            message_count=row[2],
        )
        for row in results
    ]

    return SessionListResponse(sessions=summaries, total=len(summaries))


@router.post("", response_model=SessionResponse)
def create_session(
    request: SessionCreate | None = None,
    db: Session = Depends(get_session),
):
    title = request.title if request and request.title else "Untitled Session"
    session = DBSession(title=title)
    db.add(session)
    db.commit()
    db.refresh(session)
    return SessionResponse(
        id=session.id,
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


@router.get("/{session_id}", response_model=SessionDetailResponse)
def get_session_detail(session_id: str, db: Session = Depends(get_session)):
    session = db.get(DBSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    messages = db.exec(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at)  # type: ignore[arg-type]
    ).all()

    session_videos = db.exec(
        select(SessionVideo)
        .where(SessionVideo.session_id == session_id)
        .order_by(SessionVideo.added_at)  # type: ignore[arg-type]
    ).all()

    video_responses = []
    for sv in session_videos:
        video = db.get(Video, sv.video_id)
        if video:
            video_responses.append(
                SessionVideoResponse(
                    id=sv.id,
                    video_id=video.id,
                    title=video.title,
                    channel_title=video.channel_title,
                    transcript_source=video.transcript_source,
                    added_at=sv.added_at,
                )
            )

    return SessionDetailResponse(
        id=session.id,
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
        messages=[
            MessageResponse(
                id=m.id,
                role=m.role,
                content=m.content,
                created_at=m.created_at,
            )
            for m in messages
        ],
        videos=video_responses,
    )


@router.put("/{session_id}", response_model=SessionResponse)
def update_session(
    session_id: str,
    request: SessionUpdate,
    db: Session = Depends(get_session),
):
    session = db.get(DBSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session.title = request.title
    session.updated_at = utc_now()
    db.add(session)
    db.commit()
    db.refresh(session)

    return SessionResponse(
        id=session.id,
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


@router.delete("/{session_id}")
def delete_session(session_id: str, db: Session = Depends(get_session)):
    session = db.get(DBSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    db.delete(session)
    db.commit()

    return {"success": True}
