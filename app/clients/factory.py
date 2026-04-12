from fastapi import Depends, HTTPException, status

from app.clients.base import AIClientBase
from app.clients.fake import FakeClient
from app.clients.anthropic.client import AnthropicClient
from app.config import AIProvider, Settings, get_settings


def get_ai_client(settings: Settings = Depends(get_settings)) -> AIClientBase:
    if settings.ai_provider == AIProvider.TEST:
        return FakeClient()
    if settings.ai_provider == AIProvider.ANTHROPIC:
        if not settings.anthropic_api_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Anthropic API key is not configured",
            )
        return AnthropicClient(
            api_key=settings.anthropic_api_key,
            model=settings.anthropic_model,
        )
