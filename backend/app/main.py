import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api_v1.endpoints import chat, settings, transcripts, videos
from app.core.config import get_settings
from app.core.llm_config import load_config

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

app_settings = get_settings()
load_config()

app = FastAPI(
    title=app_settings.project_name,
    openapi_url=f"{app_settings.api_v1_str}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=app_settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(
    videos.router, prefix=f"{app_settings.api_v1_str}/videos", tags=["videos"]
)
app.include_router(
    transcripts.router,
    prefix=f"{app_settings.api_v1_str}/transcripts",
    tags=["transcripts"],
)
app.include_router(chat.router, prefix=f"{app_settings.api_v1_str}/chat", tags=["chat"])
app.include_router(
    settings.router, prefix=f"{app_settings.api_v1_str}/settings", tags=["settings"]
)


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
