import httpx
import pytest

from app.steam.client import SteamClient
from app.errors import (
    SteamDataUnavailable,
    SteamRateLimitError,
    SteamUnavailableError,
)


def make_client(handler):
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = SteamClient(http, "KEY", "SID", backoff=0, language="brazilian")
    return client, http


async def test_get_owned_games_desembrulha_a_lista():
    def handler(request):
        return httpx.Response(
            200,
            json={"response": {"game_count": 1, "games": [{"appid": 10, "name": "Portal"}]}},
        )

    client, http = make_client(handler)
    try:
        games = await client.get_owned_games()
    finally:
        await http.aclose()

    assert games == [{"appid": 10, "name": "Portal"}]


async def test_get_owned_games_sem_jogos_levanta_data_unavailable():
    def handler(request):
        return httpx.Response(200, json={"response": {}})

    client, http = make_client(handler)
    try:
        with pytest.raises(SteamDataUnavailable):
            await client.get_owned_games()
    finally:
        await http.aclose()


async def test_status_403_levanta_data_unavailable():
    def handler(request):
        return httpx.Response(403, json={})

    client, http = make_client(handler)
    try:
        with pytest.raises(SteamDataUnavailable):
            await client.get_owned_games()
    finally:
        await http.aclose()


async def test_player_achievements_success_false_retorna_none():
    def handler(request):
        return httpx.Response(200, json={"playerstats": {"success": False}})

    client, http = make_client(handler)
    try:
        result = await client.get_player_achievements(10)
    finally:
        await http.aclose()

    assert result is None


async def test_get_schema_desembrulha_available_game_stats():
    def handler(request):
        return httpx.Response(
            200,
            json={
                "game": {
                    "gameName": "Portal",
                    "availableGameStats": {"achievements": [{"name": "A", "displayName": "Aa"}]},
                }
            },
        )

    client, http = make_client(handler)
    try:
        schema = await client.get_schema(10)
    finally:
        await http.aclose()

    assert schema["gameName"] == "Portal"
    assert schema["achievements"] == [{"name": "A", "displayName": "Aa"}]


async def test_429_persistente_levanta_rate_limit_apos_retry():
    chamadas = {"n": 0}

    def handler(request):
        chamadas["n"] += 1
        return httpx.Response(429, json={})

    client, http = make_client(handler)
    try:
        with pytest.raises(SteamRateLimitError):
            await client.get_owned_games()
    finally:
        await http.aclose()

    assert chamadas["n"] > 1  # houve retry


async def test_5xx_persistente_levanta_unavailable():
    def handler(request):
        return httpx.Response(503, json={})

    client, http = make_client(handler)
    try:
        with pytest.raises(SteamUnavailableError):
            await client.get_owned_games()
    finally:
        await http.aclose()


async def test_retry_apos_5xx_e_depois_sucesso():
    chamadas = {"n": 0}

    def handler(request):
        chamadas["n"] += 1
        if chamadas["n"] == 1:
            return httpx.Response(500, json={})
        return httpx.Response(200, json={"response": {"games": [{"appid": 1}]}})

    client, http = make_client(handler)
    try:
        games = await client.get_owned_games()
    finally:
        await http.aclose()

    assert games == [{"appid": 1}]
    assert chamadas["n"] == 2


async def test_key_trafega_na_querystring():
    capturado = {}

    def handler(request):
        capturado["key"] = request.url.params.get("key")
        return httpx.Response(200, json={"response": {"games": []}})

    client, http = make_client(handler)
    try:
        await client.get_owned_games()
    finally:
        await http.aclose()

    assert capturado["key"] == "KEY"
