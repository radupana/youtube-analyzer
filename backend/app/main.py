import logging
from contextlib import asynccontextmanager

import psutil
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api_v1.endpoints import (
    chat,
    patterns,
    sessions,
    settings,
    transcripts,
    videos,
)
from app.core.config import get_settings
from app.core.llm_config import load_config
from app.db.database import init_db
from app.services.embeddings import is_model_loaded as is_embeddings_loaded
from app.services.patterns import load_patterns
from app.services.whisper import get_model_info as get_whisper_info
from app.services.whisper import unload_model as unload_whisper

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

app_settings = get_settings()
load_config()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    load_patterns()
    yield
    unload_whisper()


app = FastAPI(
    title=app_settings.project_name,
    openapi_url=f"{app_settings.api_v1_str}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
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
app.include_router(
    sessions.router, prefix=f"{app_settings.api_v1_str}/sessions", tags=["sessions"]
)
app.include_router(
    patterns.router, prefix=f"{app_settings.api_v1_str}/patterns", tags=["patterns"]
)


@app.get("/health")
async def health_check():
    process = psutil.Process()
    memory_info = process.memory_info()

    return {
        "status": "healthy",
        "memory": {
            "rss_mb": round(memory_info.rss / 1024 / 1024, 1),
            "vms_mb": round(memory_info.vms / 1024 / 1024, 1),
        },
        "models": {
            "whisper": get_whisper_info(),
            "embeddings": {"loaded": is_embeddings_loaded()},
        },
    }
