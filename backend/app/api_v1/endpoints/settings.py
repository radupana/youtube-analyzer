from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.llm_config import (
    get_current_provider,
    get_provider_by_id,
    get_providers,
    set_current_provider,
)
from app.services.embeddings import clear_model as clear_embeddings
from app.services.embeddings import is_model_loaded as is_embeddings_loaded
from app.services.whisper import get_model_info as get_whisper_info
from app.services.whisper import unload_model as unload_whisper

router = APIRouter()


class ProviderResponse(BaseModel):
    id: str
    name: str
    model: str


class SetProviderRequest(BaseModel):
    id: str


@router.get("/llm-providers", response_model=list[ProviderResponse])
async def list_providers() -> list[ProviderResponse]:
    return [
        ProviderResponse(id=p.id, name=p.name, model=p.model) for p in get_providers()
    ]


@router.get("/llm-provider", response_model=ProviderResponse | None)
async def get_provider() -> ProviderResponse | None:
    provider = get_current_provider()
    if not provider:
        return None
    return ProviderResponse(id=provider.id, name=provider.name, model=provider.model)


@router.post("/llm-provider", response_model=ProviderResponse)
async def set_provider(request: SetProviderRequest) -> ProviderResponse:
    provider = get_provider_by_id(request.id)
    if not provider:
        raise HTTPException(
            status_code=404, detail=f"Provider '{request.id}' not found"
        )
    set_current_provider(request.id)
    return ProviderResponse(id=provider.id, name=provider.name, model=provider.model)


@router.get("/models/status")
async def get_models_status() -> dict[str, Any]:
    """Get status of loaded AI models."""
    return {
        "whisper": get_whisper_info(),
        "embeddings": {"loaded": is_embeddings_loaded()},
    }


@router.post("/models/unload")
async def unload_models(
    whisper: bool = True,
    embeddings: bool = True,
) -> dict[str, Any]:
    """Manually unload AI models to free memory."""
    unloaded = []

    if whisper:
        unload_whisper()
        unloaded.append("whisper")

    if embeddings:
        clear_embeddings()
        unloaded.append("embeddings")

    return {"unloaded": unloaded}
