"""Chat endpoints with real Gemini integration."""

from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.api_v1.endpoints.videos import loaded_videos
from app.api_v1.schemas import ChatRequest, ChatResponse
from app.services.llm import LLMService

router = APIRouter()

active_connections: list[WebSocket] = []
llm_service = LLMService()


@router.post("/message", response_model=ChatResponse)
async def send_message(request: ChatRequest):
    """Send a chat message and get AI response based on loaded videos."""
    session_id = request.session_id or str(uuid4())

    # Get video context
    video_context = [
        {
            "title": v.title,
            "channel_title": v.channel_title,
            "transcript": v.transcript,
        }
        for v in loaded_videos.values()
    ]

    # Get AI response
    response = llm_service.chat_with_context(request.message, video_context)

    return ChatResponse(
        response=response,
        session_id=session_id,
    )


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time chat."""
    await websocket.accept()
    active_connections.append(websocket)

    try:
        while True:
            data = await websocket.receive_text()

            # Get video context
            video_context = [
                {
                    "title": v.title,
                    "channel_title": v.channel_title,
                    "transcript": v.transcript,
                }
                for v in loaded_videos.values()
            ]

            # Get AI response
            response = llm_service.chat_with_context(data, video_context)

            await websocket.send_text(response)
    except WebSocketDisconnect:
        active_connections.remove(websocket)
