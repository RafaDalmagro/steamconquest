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


def test_modelo_e_configurado_por_provedor(monkeypatch: pytest.MonkeyPatch):
    """REQ-131/CON-110 — o modelo é escolhido pelo ambiente, nunca pela URL.

    Por provedor e não genérico: `AI_MODEL=gemini-3.1-flash-lite` com
    `AI_PROVIDER=anthropic` seria uma incoerência silenciosa, e nada no .env
    diria qual valor é o certo. O default barato existe para que esquecer a
    variável não vire conta cara por acidente.
    """
    monkeypatch.setenv("STEAM_API_KEY", "teste")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "teste-ia")
    monkeypatch.setenv("GEMINI_API_KEY", "teste-gemini")
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)

    s = load_settings()
    assert s.anthropic_model == "claude-haiku-4-5"
    assert s.gemini_model == "gemini-3.1-flash-lite"

    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-opus-4-8")

    assert load_settings().anthropic_model == "claude-opus-4-8"


def test_so_a_chave_do_provedor_ativo_e_obrigatoria(monkeypatch: pytest.MonkeyPatch):
    """AC-131/AC-132 — exigir as duas chaves obrigaria a ter conta nos dois
    fornecedores para rodar com um. Exigir nenhuma trocaria falha no boot por
    500 no clique.
    """
    monkeypatch.setenv("STEAM_API_KEY", "teste")
    monkeypatch.setenv("AI_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "teste-gemini")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    assert load_settings().ai_provider == "gemini"  # sobe sem a chave da Anthropic

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        load_settings()


def test_provedor_invalido_falha_no_boot(monkeypatch: pytest.MonkeyPatch):
    """Errar o nome do provedor tem de quebrar no start, não virar um caminho
    silencioso que só falha quando alguém clica.
    """
    monkeypatch.setenv("STEAM_API_KEY", "teste")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "teste")
    monkeypatch.setenv("AI_PROVIDER", "antropic")  # typo comum

    with pytest.raises(ValueError):
        load_settings()


def test_orcamento_vem_do_provedor_ativo(monkeypatch: pytest.MonkeyPatch):
    """AC-138 — trocar de provedor não pode exigir lembrar de reajustar o teto.

    Esquecer é justamente o erro caro: um teto calibrado para a cota gratuita do
    Gemini, aplicado à Anthropic, sairia por centenas de dólares no mês.
    """
    monkeypatch.setenv("STEAM_API_KEY", "teste")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "teste")
    monkeypatch.setenv("GEMINI_API_KEY", "teste")
    for v in ("ANTHROPIC_DAILY_BUDGET", "GEMINI_DAILY_BUDGET",
              "ANTHROPIC_OWNER_DAILY_BUDGET", "GEMINI_OWNER_DAILY_BUDGET"):
        monkeypatch.delenv(v, raising=False)

    monkeypatch.setenv("AI_PROVIDER", "anthropic")
    s = load_settings()
    assert (s.daily_budget, s.owner_daily_budget) == (3, 3)

    monkeypatch.setenv("AI_PROVIDER", "gemini")
    s = load_settings()
    assert (s.daily_budget, s.owner_daily_budget) == (100, 50)


def test_fabrica_monta_o_cliente_do_provedor_ativo(monkeypatch: pytest.MonkeyPatch):
    """REQ-130 — o `lifespan` não deve ter um if de provedor; a escolha mora na
    camada que conhece os provedores.
    """
    from app.ai import criar_cliente_de_ia

    monkeypatch.setenv("STEAM_API_KEY", "teste")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "teste")
    monkeypatch.setenv("GEMINI_API_KEY", "teste")

    monkeypatch.setenv("AI_PROVIDER", "anthropic")
    assert criar_cliente_de_ia(load_settings()).nome == "anthropic"

    monkeypatch.setenv("AI_PROVIDER", "gemini")
    assert criar_cliente_de_ia(load_settings()).nome == "gemini"
