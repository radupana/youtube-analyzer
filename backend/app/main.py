import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api_v1.endpoints import chat, transcripts, videos
from app.core.config import get_settings

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

settings = get_settings()

app = FastAPI(
    title=settings.project_name,
    openapi_url=f"{settings.api_v1_str}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(
    videos.router, prefix=f"{settings.api_v1_str}/videos", tags=["videos"]
)
app.include_router(
    transcripts.router,
    prefix=f"{settings.api_v1_str}/transcripts",
    tags=["transcripts"],
)
app.include_router(chat.router, prefix=f"{settings.api_v1_str}/chat", tags=["chat"])


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
