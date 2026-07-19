from fastapi.testclient import TestClient
import pytest

from app.main import create_app
from app.schemas.models import Achievement, Dica, Fonte, Game, GameDetail, PlayerSummary
from app.errors import (
    AiRateLimitError,
    AiUnavailableError,
    DicaIndisponivel,
    SteamDataUnavailable,
    SteamProfileNotFound,
    SteamRateLimitError,
    SteamUnavailableError,
    SteamVanityNotFound,
)
from app.web.routes import get_service

STEAMID = "76561197960287930"  # SteamID64 de 17 dígitos


class FakeService:
    def __init__(self, games=None, detail=None, profile=None, error=None, dica=None):
        self._games = games or []
        self._detail = detail
        self._profile = profile
        self._dica = dica
        self._error = error
        self.include_recebido = None
        self.steamid_recebido = None

    async def player_summary(self, steamid):
        self.steamid_recebido = steamid
        if self._error:
            raise self._error
        return self._profile

    async def list_library(self, steamid, include=()):
        self.steamid_recebido = steamid
        self.include_recebido = include
        if self._error:
            raise self._error
        return self._games

    async def game_detail(self, steamid, appid):
        self.steamid_recebido = steamid
        if self._error:
            raise self._error
        return self._detail

    async def dica(self, steamid, appid, apiname):
        self.steamid_recebido = steamid
        self.dica_recebida = (appid, apiname)
        if self._error:
            raise self._error
        return self._dica

    async def resolve_vanity(self, nome):
        self.vanity_recebido = nome
        if self._error:
            raise self._error
        return STEAMID


def client_with(service):
    app = create_app()
    app.dependency_overrides[get_service] = lambda: service
    return TestClient(app)


def test_lista_jogos_retorna_json():
    service = FakeService(
        games=[Game(appid=10, name="Portal", playtime_minutes=60, icon_url=None)]
    )
    client = client_with(service)

    resp = client.get(f"/api/users/{STEAMID}/games")

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/json")
    corpo = resp.json()
    assert corpo == [
        {
            "appid": 10,
            "name": "Portal",
            "playtime_minutes": 60,
            "playtime_2weeks_minutes": None,
            "last_played_at": None,
            "icon_url": None,
            "percent": None,
            "achieved_count": None,
            "total_count": None,
            "genres": [],
        }
    ]


def test_lista_repassa_o_include_ao_servico():
    """`include` é repetível: o caller declara cada dado caro que quer."""
    service = FakeService(games=[])
    client = client_with(service)

    client.get(f"/api/users/{STEAMID}/games?include=achievements&include=genres")

    assert service.include_recebido == ["achievements", "genres"]


def test_include_fora_do_vocabulario_retorna_422():
    """O vocabulário de include é publicado no OpenAPI — lixo é erro do caller.

    Ignorar em silêncio esconderia o typo de quem chama e obrigaria a rota a
    manter uma segunda lista de includes válidos, fora do schema.
    """
    service = FakeService(games=[])
    client = client_with(service)

    resp = client.get(f"/api/users/{STEAMID}/games?include=xpto")

    assert resp.status_code == 422
    assert isinstance(resp.json()["detail"], str)  # mesmo contrato de erro dos demais
    assert service.include_recebido is None  # nem chega ao serviço


def test_sem_include_nada_e_buscado_alem_da_biblioteca():
    """O caminho barato é o default: sem `include`, uma chamada à Steam."""
    service = FakeService(games=[])
    client = client_with(service)

    client.get(f"/api/users/{STEAMID}/games")

    assert service.include_recebido == []


def test_lista_repassa_o_steamid_ao_servico():
    service = FakeService(games=[])
    client = client_with(service)

    client.get(f"/api/users/{STEAMID}/games")

    assert service.steamid_recebido == STEAMID


def test_detalhe_repassa_o_steamid_ao_servico():
    detail = GameDetail(
        appid=10,
        name="Portal",
        supports_achievements=False,
        achieved_count=0,
        total_count=0,
        percent=0.0,
        achievements=[],
    )
    service = FakeService(detail=detail)
    client = client_with(service)

    client.get(f"/api/users/{STEAMID}/games/10")

    assert service.steamid_recebido == STEAMID


def test_steamid_fora_do_padrao_retorna_422():
    client = client_with(FakeService(games=[]))

    resp = client.get("/api/users/nao-e-um-id/games")

    assert resp.status_code == 422


def test_param_invalido_retorna_detail_string_em_pt_br():
    # O 422 padrão do FastAPI traz `detail` como array de erros de validação; o
    # frontend só sabe ler string e acabava exibindo "Erro 422" cru. Todo erro
    # da API fala a mesma língua: {"detail": "<mensagem pt-BR>"}.
    client = client_with(FakeService(games=[]))

    resp = client.get(f"/api/users/{STEAMID}/games/nao-e-um-appid")

    assert resp.status_code == 422
    assert isinstance(resp.json()["detail"], str)
    assert "inválido" in resp.json()["detail"]


def test_detalhe_retorna_conquistas_em_json():
    detail = GameDetail(
        appid=10,
        name="Portal",
        supports_achievements=True,
        achieved_count=1,
        total_count=2,
        percent=50.0,
        achievements=[
            Achievement(apiname="A", display_name="Conquista A", achieved=True),
            Achievement(apiname="B", display_name="Conquista B", achieved=False),
        ],
    )
    client = client_with(FakeService(detail=detail))

    resp = client.get(f"/api/users/{STEAMID}/games/10")

    assert resp.status_code == 200
    corpo = resp.json()
    assert corpo["name"] == "Portal"
    assert corpo["percent"] == 50.0
    assert [a["apiname"] for a in corpo["achievements"]] == ["A", "B"]
    assert corpo["achievements"][0]["achieved"] is True


def test_perfil_retorna_nome_e_avatar_em_json():
    profile = PlayerSummary(
        personaname="Fulano",
        avatar_url="https://avatars.steamstatic.com/abc_full.jpg",
    )
    service = FakeService(profile=profile)
    client = client_with(service)

    resp = client.get(f"/api/users/{STEAMID}/profile")

    assert resp.status_code == 200
    assert service.steamid_recebido == STEAMID
    assert resp.json() == {
        "personaname": "Fulano",
        "avatar_url": "https://avatars.steamstatic.com/abc_full.jpg",
    }


def test_perfil_inexistente_retorna_404_com_mensagem_propria():
    client = client_with(FakeService(error=SteamProfileNotFound("não encontrado")))

    resp = client.get(f"/api/users/{STEAMID}/profile")

    assert resp.status_code == 404
    # Mensagem distinta da de perfil privado: o usuário precisa saber que o erro
    # é o ID, não a privacidade da conta.
    assert "não encontrado" in resp.json()["detail"]


def test_perfil_privado_retorna_404_json():
    client = client_with(FakeService(error=SteamDataUnavailable("privado")))

    resp = client.get(f"/api/users/{STEAMID}/games/10")

    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith("application/json")
    assert "detail" in resp.json()


def test_rate_limit_retorna_429_json():
    client = client_with(FakeService(error=SteamRateLimitError("429")))

    resp = client.get(f"/api/users/{STEAMID}/games")

    assert resp.status_code == 429
    assert "detail" in resp.json()


def test_steam_indisponivel_retorna_502_json():
    client = client_with(FakeService(error=SteamUnavailableError("5xx")))

    resp = client.get(f"/api/users/{STEAMID}/games")

    assert resp.status_code == 502
    assert "detail" in resp.json()


def test_cors_permite_origem_configurada(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("STEAM_API_KEY", "teste")
    monkeypatch.setenv("CORS_ORIGINS", "https://app.exemplo.com/")

    client = client_with(FakeService(games=[]))

    resp = client.options(
        f"/api/users/{STEAMID}/games",
        headers={
            "Origin": "https://app.exemplo.com",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "https://app.exemplo.com"


def test_resolve_devolve_o_steamid_do_nome_do_perfil():
    service = FakeService()
    client = client_with(service)

    resp = client.get("/api/resolve", params={"vanity": "gabelogannewell"})

    assert resp.status_code == 200
    # A única rota que ecoa um steamid: descobri-lo é o serviço que ela presta.
    assert resp.json() == {"steamid": STEAMID}
    assert service.vanity_recebido == "gabelogannewell"


def test_nome_inexistente_da_404_sem_falar_em_17_digitos():
    service = FakeService(error=SteamVanityNotFound("nome de perfil não encontrado"))
    client = client_with(service)

    resp = client.get("/api/resolve", params={"vanity": "nao-existe"})

    assert resp.status_code == 404
    detail = resp.json()["detail"]
    # Quem digitou um nome não digitou dígito nenhum: mandá-lo conferir "os 17
    # dígitos" é instruí-lo a corrigir algo que não está no que ele escreveu.
    assert "17 dígitos" not in detail
    assert "perfil" in detail.lower()


def test_vanity_fora_do_formato_da_422_sem_tocar_o_servico():
    service = FakeService()
    client = client_with(service)

    for lixo in ("", "a", "x" * 33, "não-pode", "tem espaço", "ponto.final"):
        resp = client.get("/api/resolve", params={"vanity": lixo})
        assert resp.status_code == 422, lixo
        assert isinstance(resp.json()["detail"], str)  # contrato único de erro

    # Nenhum deles virou chave de cache nem chamada à Steam.
    assert not hasattr(service, "vanity_recebido")


def test_dica_retorna_texto_e_fontes():
    """AC-110 no contrato HTTP — o que o SPA vai consumir."""
    service = FakeService(
        dica=Dica(
            texto="Use a fonte termal.",
            fontes=[Fonte(title="Nioh 100%", url="https://exemplo/guia")],
        )
    )
    client = client_with(service)

    resp = client.get(f"/api/users/{STEAMID}/games/10/achievements/ACH_SPA/dica")

    assert resp.status_code == 200
    assert resp.json() == {
        "texto": "Use a fonte termal.",
        "fontes": [{"title": "Nioh 100%", "url": "https://exemplo/guia"}],
    }
    assert service.dica_recebida == (10, "ACH_SPA")


def test_dica_indisponivel_vira_404_com_mensagem_generica():
    """SEC-111 — a mensagem não conta *por que*.

    Conquista obtida, jogo fora da biblioteca e apiname inexistente devolvem o
    mesmo texto de propósito: distinguir os casos diria a quem sonda a API se um
    jogo está ou não na biblioteca de alguém.
    """
    client = client_with(FakeService(error=DicaIndisponivel("obtida")))

    resp = client.get(f"/api/users/{STEAMID}/games/10/achievements/ACH_SPA/dica")

    assert resp.status_code == 404
    assert "biblioteca" not in resp.json()["detail"].lower()
    assert "obtida" not in resp.json()["detail"].lower()


def test_teto_de_chamadas_pagas_vira_429():
    client = client_with(FakeService(error=AiRateLimitError("teto local")))

    resp = client.get(f"/api/users/{STEAMID}/games/10/achievements/ACH_SPA/dica")

    assert resp.status_code == 429


def test_falha_do_provedor_de_ia_vira_502():
    client = client_with(FakeService(error=AiUnavailableError("fora do ar")))

    resp = client.get(f"/api/users/{STEAMID}/games/10/achievements/ACH_SPA/dica")

    assert resp.status_code == 502
