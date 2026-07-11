from fastapi.testclient import TestClient
import pytest

from app.main import create_app
from app.schemas.models import Achievement, Game, GameDetail
from app.errors import (
    SteamDataUnavailable,
    SteamRateLimitError,
    SteamUnavailableError,
)
from app.web.routes import get_service

STEAMID = "76561197960287930"  # SteamID64 de 17 dígitos


class FakeService:
    def __init__(self, games=None, detail=None, error=None):
        self._games = games or []
        self._detail = detail
        self._error = error
        self.sort_recebido = None
        self.group_recebido = None
        self.steamid_recebido = None

    async def list_library(self, steamid, sort="playtime", group=None):
        self.steamid_recebido = steamid
        self.sort_recebido = sort
        self.group_recebido = group
        if self._error:
            raise self._error
        return self._games

    async def game_detail(self, steamid, appid):
        self.steamid_recebido = steamid
        if self._error:
            raise self._error
        return self._detail


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
            "icon_url": None,
            "percent": None,
            "achieved_count": None,
            "total_count": None,
            "genres": [],
        }
    ]


def test_lista_repassa_o_parametro_sort_ao_servico():
    service = FakeService(games=[])
    client = client_with(service)

    client.get(f"/api/users/{STEAMID}/games?sort=percent")

    assert service.sort_recebido == "percent"


def test_lista_repassa_o_parametro_group_ao_servico():
    service = FakeService(games=[])
    client = client_with(service)

    client.get(f"/api/users/{STEAMID}/games?group=genre")

    assert service.group_recebido == "genre"


def test_group_invalido_e_ignorado():
    service = FakeService(games=[])
    client = client_with(service)

    client.get(f"/api/users/{STEAMID}/games?group=xpto")

    assert service.group_recebido is None


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
