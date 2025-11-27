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
from app.db.models import Message, SessionVideo, utc_now
from app.db.models import Session as DBSession

router = APIRouter()


@router.get("", response_model=SessionListResponse)
def list_sessions(db: Session = Depends(get_session)):
    sessions = db.exec(select(DBSession).order_by(DBSession.updated_at.desc())).all()

    summaries = []
    for s in sessions:
        video_count = db.exec(
            select(func.count()).where(SessionVideo.session_id == s.id)
        ).one()
        message_count = db.exec(
            select(func.count()).where(Message.session_id == s.id)
        ).one()
        summaries.append(
            SessionSummary(
                id=s.id,
                title=s.title,
                created_at=s.created_at,
                updated_at=s.updated_at,
                video_count=video_count,
                message_count=message_count,
            )
        )

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
        .order_by(Message.created_at)  # type: ignore
    ).all()

    videos = db.exec(
        select(SessionVideo)
        .where(SessionVideo.session_id == session_id)
        .order_by(SessionVideo.added_at)  # type: ignore
    ).all()

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
        videos=[
            SessionVideoResponse(
                id=v.id,
                video_id=v.video_id,
                title=v.title,
                channel_title=v.channel_title,
                transcript_source=v.transcript_source,
                added_at=v.added_at,
            )
            for v in videos
        ],
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
