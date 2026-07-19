"""Única camada que fala HTTP com provedores de IA — espelho de `steam/`.

A escolha do provedor mora aqui, e não no `lifespan`: `main.py` não deve ter um
`if` de fornecedor, e `services/` não deve saber que existe mais de um.
"""

from anthropic import AsyncAnthropic
from google.genai import Client as GeminiSdk
from google.genai import types as gemini_types

from app.ai.anthropic_client import AnthropicClient
from app.ai.base import ClienteDeIA
from app.ai.gemini_client import GeminiClient

__all__ = ["ClienteDeIA", "criar_cliente_de_ia"]


def criar_cliente_de_ia(settings) -> ClienteDeIA:
    """Monta o cliente do provedor ativo.

    O teto de rajada é compartilhado de propósito (CON-130): ele protege do rate
    limit do fornecedor, não da fatura — quem protege a fatura é o orçamento
    diário, esse sim por provedor.
    """
    comum = {
        "rate_per_minute": settings.ai_rate_per_minute,
        "rate_burst": settings.ai_rate_burst,
    }
    if settings.ai_provider == "gemini":
        return GeminiClient(
            GeminiSdk(
                api_key=settings.gemini_api_key,
                http_options=gemini_types.HttpOptions(timeout=int(settings.http_timeout * 1000)),
            ),
            model=settings.gemini_model,
            **comum,
        )
    return AnthropicClient(
        AsyncAnthropic(api_key=settings.anthropic_api_key),
        model=settings.anthropic_model,
        **comum,
    )
