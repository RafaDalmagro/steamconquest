import httpx
import pytest

from app.steam.client import SteamClient
from app.errors import (
    SteamDataUnavailable,
    SteamProfileNotFound,
    SteamRateLimitError,
    SteamUnavailableError,
)


def make_client(handler):
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = SteamClient(http, "KEY", backoff=0, language="brazilian")
    return client, http


async def test_get_owned_games_desembrulha_a_lista():
    def handler(request):
        return httpx.Response(
            200,
            json={"response": {"game_count": 1, "games": [{"appid": 10, "name": "Portal"}]}},
        )

    client, http = make_client(handler)
    try:
        games = await client.get_owned_games("SID")
    finally:
        await http.aclose()

    assert games == [{"appid": 10, "name": "Portal"}]


async def test_get_owned_games_sem_jogos_levanta_data_unavailable():
    def handler(request):
        return httpx.Response(200, json={"response": {}})

    client, http = make_client(handler)
    try:
        with pytest.raises(SteamDataUnavailable):
            await client.get_owned_games("SID")
    finally:
        await http.aclose()


async def test_status_403_levanta_data_unavailable():
    def handler(request):
        return httpx.Response(403, json={})

    client, http = make_client(handler)
    try:
        with pytest.raises(SteamDataUnavailable):
            await client.get_owned_games("SID")
    finally:
        await http.aclose()


async def test_player_achievements_success_false_retorna_none():
    def handler(request):
        return httpx.Response(200, json={"playerstats": {"success": False}})

    client, http = make_client(handler)
    try:
        result = await client.get_player_achievements("SID", 10)
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


async def test_get_player_summary_desembrulha_o_primeiro_player():
    def handler(request):
        return httpx.Response(
            200,
            json={
                "response": {
                    "players": [
                        {
                            "steamid": "SID",
                            "personaname": "Fulano",
                            "avatarfull": "https://avatars.steamstatic.com/abc_full.jpg",
                        }
                    ]
                }
            },
        )

    client, http = make_client(handler)
    try:
        player = await client.get_player_summary("SID")
    finally:
        await http.aclose()

    assert player["personaname"] == "Fulano"
    assert player["avatarfull"] == "https://avatars.steamstatic.com/abc_full.jpg"


async def test_get_player_summary_sem_players_levanta_profile_not_found():
    # SteamID de 17 dígitos que não existe: a Steam devolve players: [].
    # Erro próprio, distinto de perfil privado (que devolve o player normalmente).
    def handler(request):
        return httpx.Response(200, json={"response": {"players": []}})

    client, http = make_client(handler)
    try:
        with pytest.raises(SteamProfileNotFound):
            await client.get_player_summary("SID")
    finally:
        await http.aclose()


async def test_teto_local_barra_a_chamada_antes_de_sair_para_a_steam():
    # Protege a quota da STEAM_API_KEY: estourado o teto, a requisição nem sai.
    chamadas = {"n": 0}

    def handler(request):
        chamadas["n"] += 1
        return httpx.Response(200, json={"response": {"games": []}})

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = SteamClient(http, "KEY", backoff=0, rate_burst=2, rate_per_minute=0)
    try:
        await client.get_owned_games("SID")
        await client.get_owned_games("SID")
        with pytest.raises(SteamRateLimitError):
            await client.get_owned_games("SID")
    finally:
        await http.aclose()

    assert chamadas["n"] == 2  # a 3ª não chegou à Steam


async def test_teto_local_repoe_tokens_com_o_tempo():
    relogio = {"agora": 0.0}

    def handler(request):
        return httpx.Response(200, json={"response": {"games": []}})

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = SteamClient(
        http,
        "KEY",
        backoff=0,
        rate_burst=1,
        rate_per_minute=60,  # 1 token por segundo
        now=lambda: relogio["agora"],
    )
    try:
        await client.get_owned_games("SID")  # gasta o único token
        with pytest.raises(SteamRateLimitError):
            await client.get_owned_games("SID")

        relogio["agora"] = 1.0  # passou 1s: 1 token reposto

        await client.get_owned_games("SID")  # volta a passar
    finally:
        await http.aclose()


async def test_429_persistente_levanta_rate_limit_apos_retry():
    chamadas = {"n": 0}

    def handler(request):
        chamadas["n"] += 1
        return httpx.Response(429, json={})

    client, http = make_client(handler)
    try:
        with pytest.raises(SteamRateLimitError):
            await client.get_owned_games("SID")
    finally:
        await http.aclose()

    assert chamadas["n"] > 1  # houve retry


async def test_5xx_persistente_levanta_unavailable():
    def handler(request):
        return httpx.Response(503, json={})

    client, http = make_client(handler)
    try:
        with pytest.raises(SteamUnavailableError):
            await client.get_owned_games("SID")
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
        games = await client.get_owned_games("SID")
    finally:
        await http.aclose()

    assert games == [{"appid": 1}]
    assert chamadas["n"] == 2


async def test_get_app_genres_parseia_descricoes():
    def handler(request):
        return httpx.Response(
            200,
            json={
                "10": {
                    "success": True,
                    "data": {
                        "genres": [
                            {"id": "1", "description": "Ação"},
                            {"id": "25", "description": "Aventura"},
                        ]
                    },
                }
            },
        )

    client, http = make_client(handler)
    try:
        genres = await client.get_app_genres(10)
    finally:
        await http.aclose()

    assert genres == ["Ação", "Aventura"]


async def test_get_app_genres_success_false_retorna_vazio():
    def handler(request):
        return httpx.Response(200, json={"10": {"success": False}})

    client, http = make_client(handler)
    try:
        genres = await client.get_app_genres(10)
    finally:
        await http.aclose()

    assert genres == []


async def test_get_app_genres_data_como_lista_vazia_retorna_vazio():
    # Caso real: jogo sem dados na loja vem como success:true, data:[] (lista!).
    def handler(request):
        return httpx.Response(200, json={"10": {"success": True, "data": []}})

    client, http = make_client(handler)
    try:
        genres = await client.get_app_genres(10)
    finally:
        await http.aclose()

    assert genres == []


async def test_get_app_genres_429_retorna_vazio_sem_levantar():
    def handler(request):
        return httpx.Response(429, json={})

    client, http = make_client(handler)
    try:
        genres = await client.get_app_genres(10)
    finally:
        await http.aclose()

    assert genres == []  # best-effort: endpoint da loja é instável, nunca quebra


async def test_get_app_genres_200_nao_json_retorna_vazio():
    # Endpoint instável pode devolver 200 com HTML (manutenção) em vez de JSON.
    def handler(request):
        return httpx.Response(200, text="<html>manutenção</html>")

    client, http = make_client(handler)
    try:
        genres = await client.get_app_genres(10)
    finally:
        await http.aclose()

    assert genres == []


async def test_get_app_genres_erro_de_rede_retorna_vazio():
    def handler(request):
        raise httpx.ConnectError("sem rede")

    client, http = make_client(handler)
    try:
        genres = await client.get_app_genres(10)
    finally:
        await http.aclose()

    assert genres == []


async def test_get_app_genres_nao_envia_a_key_para_a_loja():
    capturado = {}

    def handler(request):
        capturado["host"] = request.url.host
        capturado["key"] = request.url.params.get("key")
        capturado["appids"] = request.url.params.get("appids")
        return httpx.Response(200, json={"10": {"success": True, "data": {"genres": []}}})

    client, http = make_client(handler)
    try:
        await client.get_app_genres(10)
    finally:
        await http.aclose()

    assert capturado["host"] == "store.steampowered.com"
    assert capturado["key"] is None  # a STEAM_API_KEY nunca vai para a loja
    assert capturado["appids"] == "10"


async def test_key_trafega_na_querystring():
    capturado = {}

    def handler(request):
        capturado["key"] = request.url.params.get("key")
        capturado["steamid"] = request.url.params.get("steamid")
        return httpx.Response(200, json={"response": {"games": []}})

    client, http = make_client(handler)
    try:
        await client.get_owned_games("SID")
    finally:
        await http.aclose()

    assert capturado["key"] == "KEY"
    assert capturado["steamid"] == "SID"


async def test_raridade_global_sai_com_gameid_e_vira_mapa_por_apiname():
    capturado = {}

    def handler(request):
        # A armadilha real deste endpoint: o parâmetro é `gameid`, não `appid`.
        # Errar o nome devolve resposta vazia, não erro — daí a asserção.
        capturado["gameid"] = request.url.params.get("gameid")
        capturado["appid"] = request.url.params.get("appid")
        return httpx.Response(
            200,
            json={
                "achievementpercentages": {
                    "achievements": [
                        # A Steam manda o percentual como *string* ("49.9"), não
                        # como número — confirmado no payload real do appid 440.
                        {"name": "ACH_A", "percent": "42.7"},
                        {"name": "ACH_B", "percent": 4.1},
                        # Malformadas: entram no mapa nenhuma delas, e nenhuma
                        # levanta — raridade é decoração, não pode dar 500.
                        {"name": "ACH_SEM_PCT"},
                        {"name": "ACH_LIXO", "percent": "n/a"},
                        {"percent": "10.0"},
                    ]
                }
            },
        )

    client, http = make_client(handler)
    try:
        percentuais = await client.get_global_achievement_percentages(10)
    finally:
        await http.aclose()

    assert capturado["gameid"] == "10"
    assert capturado["appid"] is None
    # Sempre float, venha string ou número da Steam.
    assert percentuais == {"ACH_A": 42.7, "ACH_B": 4.1}
