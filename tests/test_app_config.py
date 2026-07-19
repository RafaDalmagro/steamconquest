import pytest
from fastapi.testclient import TestClient

from app.config import load_settings
from app.main import create_app


def test_prod_nao_expoe_schema_nem_swagger(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("STEAM_API_KEY", "teste")
    monkeypatch.setenv("ENVIRONMENT", "prod")

    client = TestClient(create_app())

    assert client.get("/openapi.json").status_code == 404
    # /docs pode cair no fallback do SPA (index.html) quando o dist está
    # embarcado; o que importa é que o Swagger não é servido.
    assert "swagger-ui" not in client.get("/docs").text


def test_dev_expoe_schema_para_gerar_tipos(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("STEAM_API_KEY", "teste")
    monkeypatch.delenv("ENVIRONMENT", raising=False)

    client = TestClient(create_app())

    # `npm run generate:api` depende deste schema.
    assert client.get("/openapi.json").status_code == 200
    assert "swagger-ui" in client.get("/docs").text


def test_modelo_de_ia_tem_default_e_e_trocavel_por_env(monkeypatch: pytest.MonkeyPatch):
    """REQ-118/CON-110 — o modelo é escolhido pelo ambiente, nunca pela URL.

    O default barato existe para que esquecer a env var não vire uma conta cara
    por acidente. E não há parâmetro de query equivalente de propósito: input
    público não decide onde o dinheiro é gasto.
    """
    monkeypatch.setenv("STEAM_API_KEY", "teste")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "teste-ia")
    monkeypatch.delenv("AI_MODEL", raising=False)

    assert load_settings().ai_model == "claude-haiku-4-5"

    monkeypatch.setenv("AI_MODEL", "claude-opus-4-8")

    assert load_settings().ai_model == "claude-opus-4-8"
