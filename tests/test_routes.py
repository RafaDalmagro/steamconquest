from fastapi.testclient import TestClient

from app.main import create_app
from app.schemas.models import Achievement, Game, GameDetail
from app.errors import (
    SteamDataUnavailable,
    SteamRateLimitError,
    SteamUnavailableError,
)
from app.web.routes import get_service


class FakeService:
    def __init__(self, games=None, detail=None, error=None):
        self._games = games or []
        self._detail = detail
        self._error = error
        self.sort_recebido = None

    async def list_library(self, sort="playtime"):
        self.sort_recebido = sort
        if self._error:
            raise self._error
        return self._games

    async def game_detail(self, appid):
        if self._error:
            raise self._error
        return self._detail


def client_with(service):
    app = create_app()
    app.dependency_overrides[get_service] = lambda: service
    return TestClient(app)


def test_index_lista_os_jogos():
    service = FakeService(
        games=[Game(appid=10, name="Portal", playtime_minutes=60, icon_url=None)]
    )
    client = client_with(service)

    resp = client.get("/")

    assert resp.status_code == 200
    assert "Portal" in resp.text


def test_index_repassa_o_parametro_sort_ao_servico():
    service = FakeService(games=[])
    client = client_with(service)

    client.get("/?sort=percent")

    assert service.sort_recebido == "percent"


def test_detalhe_renderiza_conquistas():
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

    resp = client.get("/game/10")

    assert resp.status_code == 200
    assert "Conquista A" in resp.text
    assert "Conquista B" in resp.text


def test_perfil_privado_retorna_404():
    client = client_with(FakeService(error=SteamDataUnavailable("privado")))

    resp = client.get("/game/10")

    assert resp.status_code == 404


def test_rate_limit_retorna_429():
    client = client_with(FakeService(error=SteamRateLimitError("429")))

    resp = client.get("/")

    assert resp.status_code == 429


def test_steam_indisponivel_retorna_502():
    client = client_with(FakeService(error=SteamUnavailableError("5xx")))

    resp = client.get("/")

    assert resp.status_code == 502
