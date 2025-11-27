from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.llm_config import (
    get_current_provider,
    get_provider_by_id,
    get_providers,
    set_current_provider,
)

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
