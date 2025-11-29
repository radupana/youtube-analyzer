from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select

from app.api_v1.schemas import ChatRequest, ChatResponse
from app.db.database import get_session
from app.db.models import Message, SessionVideo, Video, utc_now
from app.db.models import Session as DBSession
from app.services.llm import chat_with_context, chat_with_context_stream

router = APIRouter()


def get_video_context_from_session(db: Session, session_id: str) -> list[dict]:
    session_videos = db.exec(
        select(SessionVideo).where(SessionVideo.session_id == session_id)
    ).all()

    result = []
    for sv in session_videos:
        video = db.get(Video, sv.video_id)
        if video:
            result.append(
                {
                    "video_id": video.id,
                    "title": video.title,
                    "channel_title": video.channel_title,
                    "transcript": video.transcript,
                }
            )
    return result


@router.post("/message", response_model=ChatResponse)
async def send_message(
    request: ChatRequest,
    db: Session = Depends(get_session),
):
    session_id = request.session_id
    session: DBSession

    if not session_id:
        session = DBSession()
        db.add(session)
        db.commit()
        db.refresh(session)
        session_id = session.id
    else:
        existing = db.get(DBSession, session_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Session not found")
        session = existing

    video_context = get_video_context_from_session(db, session_id)
    response = await chat_with_context(request.message, video_context)

    user_msg = Message(session_id=session_id, role="user", content=request.message)
    assistant_msg = Message(session_id=session_id, role="assistant", content=response)
    db.add_all([user_msg, assistant_msg])

    session.updated_at = utc_now()
    db.add(session)
    db.commit()

    return ChatResponse(response=response, session_id=session_id)


@router.post("/message/stream")
async def send_message_stream(
    request: ChatRequest,
    db: Session = Depends(get_session),
):
    """Stream chat response using Server-Sent Events."""
    from app.core.llm_config import get_current_provider

    provider = get_current_provider()
    if not provider:
        raise HTTPException(
            status_code=503,
            detail="No LLM provider configured. Check config.yaml and API keys.",
        )

    session_id = request.session_id
    session: DBSession

    if not session_id:
        session = DBSession()
        db.add(session)
        db.commit()
        db.refresh(session)
        session_id = session.id
    else:
        existing = db.get(DBSession, session_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Session not found")
        session = existing

    video_context = get_video_context_from_session(db, session_id)

    user_msg = Message(session_id=session_id, role="user", content=request.message)
    db.add(user_msg)
    db.commit()

    async def generate():
        full_response = []
        yield f"data: {session_id}\n\n"

        async for chunk in chat_with_context_stream(request.message, video_context):
            full_response.append(chunk)
            escaped = chunk.replace("\n", "\\n")
            yield f"data: {escaped}\n\n"

        yield "data: [DONE]\n\n"

        response_text = "".join(full_response)
        assistant_msg = Message(
            session_id=session_id, role="assistant", content=response_text
        )
        db.add(assistant_msg)
        session.updated_at = utc_now()
        db.add(session)
        db.commit()

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
