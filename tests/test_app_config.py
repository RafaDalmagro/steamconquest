import pytest
from fastapi.testclient import TestClient

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
