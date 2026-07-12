import asyncio

import httpx

from app.errors import (
    SteamDataUnavailable,
    SteamProfileNotFound,
    SteamRateLimitError,
    SteamUnavailableError,
)

_BASE = "https://api.steampowered.com"
# Loja (não-oficial): única fonte de gênero. Sem key, best-effort.
_STORE_APPDETAILS = "https://store.steampowered.com/api/appdetails"


class SteamClient:
    """Única camada que fala HTTP com a Steam.

    Métodos devolvem dados já desembrulhados ou levantam exceção tipada.
    Aplica retry com backoff exponencial para 429/5xx e falhas de rede.
    """

    def __init__(
        self,
        http: httpx.AsyncClient,
        api_key: str,
        *,
        max_retries: int = 3,
        backoff: float = 0.5,
        language: str = "brazilian",
    ):
        self._http = http
        self._key = api_key
        self._max_retries = max_retries
        self._backoff = backoff
        self._lang = language

    async def get_owned_games(self, steamid: str) -> list[dict]:
        data = await self._get(
            "/IPlayerService/GetOwnedGames/v1/",
            {"steamid": steamid, "include_appinfo": 1, "include_played_free_games": 1},
        )
        response = data.get("response", {})
        if "games" not in response:
            raise SteamDataUnavailable("biblioteca indisponível (perfil privado?)")
        return response["games"]

    async def get_player_summary(self, steamid: str) -> dict:
        """Perfil público (nome e avatar). Funciona mesmo com perfil privado."""
        data = await self._get(
            "/ISteamUser/GetPlayerSummaries/v2/",
            {"steamids": steamid},
        )
        players = data.get("response", {}).get("players", [])
        if not players:
            # players: [] só acontece com SteamID inexistente — perfil privado
            # continua devolvendo o player (nome e avatar são públicos).
            raise SteamProfileNotFound("perfil não encontrado")
        return players[0]

    async def get_player_achievements(self, steamid: str, appid: int) -> list[dict] | None:
        data = await self._get(
            "/ISteamUserStats/GetPlayerAchievements/v1/",
            {"steamid": steamid, "appid": appid, "l": self._lang},
        )
        stats = data.get("playerstats", {})
        if not stats.get("success") or "achievements" not in stats:
            return None
        return stats["achievements"]

    async def get_schema(self, appid: int) -> dict:
        data = await self._get(
            "/ISteamUserStats/GetSchemaForGame/v2/",
            {"appid": appid, "l": self._lang},
        )
        game = data.get("game", {})
        return {
            "gameName": game.get("gameName", ""),
            "achievements": game.get("availableGameStats", {}).get("achievements", []),
        }

    async def get_app_genres(self, appid: int) -> list[str]:
        """Gêneros de um jogo via storefront (endpoint não-oficial da Steam).

        NÃO passa por _get(): a STEAM_API_KEY nunca vai para a loja (nem é
        exigida). 100% best-effort — qualquer falha (429/5xx/rede/formato)
        devolve [] em vez de levantar, pois o endpoint é instável e não pode
        derrubar a biblioteca.
        """
        try:
            resp = await self._http.get(
                _STORE_APPDETAILS,
                params={"appids": appid, "filters": "genres", "l": self._lang},
            )
        except httpx.HTTPError:
            return []
        if resp.status_code != 200:
            return []
        try:
            entry = resp.json().get(str(appid), {})
            # Jogo sem dados vem como success:true, data:[] (lista, não dict).
            data = entry.get("data")
            if not entry.get("success") or not isinstance(data, dict):
                return []
            genres = data.get("genres", [])
            return [g["description"] for g in genres if g.get("description")]
        except (ValueError, AttributeError, TypeError):
            # 200 com corpo não-JSON ou formato inesperado: best-effort → [].
            return []

    async def _get(self, path: str, params: dict) -> dict:
        params = {**params, "key": self._key}
        last_error: Exception | None = None

        for attempt in range(self._max_retries + 1):
            try:
                resp = await self._http.get(_BASE + path, params=params)
            except httpx.HTTPError as exc:
                last_error = SteamUnavailableError(str(exc))
                await self._sleep(attempt)
                continue

            if resp.status_code in (401, 403):
                raise SteamDataUnavailable("acesso negado (perfil privado ou key inválida)")
            if resp.status_code == 429:
                last_error = SteamRateLimitError("rate limit da Steam")
                await self._sleep(attempt)
                continue
            if resp.status_code >= 500:
                last_error = SteamUnavailableError("Steam indisponível")
                await self._sleep(attempt)
                continue

            return resp.json()

        raise last_error or SteamUnavailableError("falha ao consultar a Steam")

    async def _sleep(self, attempt: int) -> None:
        # Última tentativa: vamos desistir a seguir, dormir só atrasaria o erro.
        if attempt >= self._max_retries:
            return
        if self._backoff:
            await asyncio.sleep(self._backoff * (2**attempt))
