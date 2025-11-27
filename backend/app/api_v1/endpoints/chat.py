from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.api_v1.endpoints.videos import loaded_videos
from app.api_v1.schemas import ChatRequest, ChatResponse
from app.services.llm import chat_with_context

router = APIRouter()

active_connections: list[WebSocket] = []


def get_video_context() -> list[dict]:
    return [
        {
            "title": v.title,
            "channel_title": v.channel_title,
            "transcript": v.transcript,
        }
        for v in loaded_videos.values()
    ]


@router.post("/message", response_model=ChatResponse)
async def send_message(request: ChatRequest):
    session_id = request.session_id or str(uuid4())
    response = await chat_with_context(request.message, get_video_context())
    return ChatResponse(response=response, session_id=session_id)


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)

    try:
        while True:
            data = await websocket.receive_text()
            response = await chat_with_context(data, get_video_context())
            await websocket.send_text(response)
    except WebSocketDisconnect:
        active_connections.remove(websocket)
