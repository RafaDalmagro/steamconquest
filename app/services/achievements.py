import asyncio
from typing import Any, Callable

from app.core.cache import TTLCache
from app.errors import SteamDataUnavailable, SteamError, SteamProfileNotFound
from app.schemas.models import Achievement, Game, GameDetail, PlayerSummary

_ICON_URL = (
    "https://media.steampowered.com/steamcommunity/public/images/apps/{appid}/{hash}.jpg"
)

# TTLs por natureza do dado (segundos). Ver spec REQ-010/CON-010.
OWNED_TTL = 300
ACH_TTL = 300
PROFILE_TTL = 300
# TTL curto para o "não existe": erra pouco se um perfil novo aparecer, e já
# absorve a rajada de quem marreta o mesmo ID inválido.
NOT_FOUND_TTL = 60
SCHEMA_TTL = 86_400
GENRES_TTL = 604_800  # 7 dias: gênero encontrado é estático
# [] pode ser 429 transitório da loja, não ausência real de gênero. TTL curto:
# não re-martela a loja a cada load (o que perpetuaria o rate limit), mas
# retenta em ~1h para se recuperar sozinho.
GENRES_MISS_TTL = 3_600

# Sentinela de cache negativo: distingue "não existe" (cacheado) de "não está no
# cache" (None), sem precisar guardar a exceção.
_NAO_EXISTE = object()


class AchievementsService:
    """Regra de negócio: monta biblioteca e detalhe a partir do client Steam.

    Não conhece FastAPI nem httpx — depende apenas da interface do client, o que
    o torna testável com um client falso (sem rede).
    """

    def __init__(self, client, cache: TTLCache, concurrency: int = 5):
        self._client = client
        self._cache = cache
        self._concurrency = concurrency

    async def list_library(
        self, steamid: str, sort: str = "playtime", group: str | None = None
    ) -> list[Game]:
        try:
            raw = await self._owned_games(steamid)
        except SteamDataUnavailable:
            # A Steam devolve "biblioteca indisponível" tanto para conta que não
            # existe quanto para perfil privado. Só o perfil desempata — e só
            # pagamos essa chamada aqui, no caminho de erro.
            await self._assert_exists(steamid)
            raise
        games = [
            Game(
                appid=g["appid"],
                name=g["name"],
                playtime_minutes=g["playtime_forever"],
                icon_url=(
                    _ICON_URL.format(appid=g["appid"], hash=g["img_icon_url"])
                    if g.get("img_icon_url")
                    else None
                ),
            )
            for g in raw
        ]
        if sort in ("percent", "ach_count"):
            await self._fill_counts(steamid, games)
        if group == "genre":
            await self._fill_genres(games)
        _sort(games, sort)
        return games

    async def player_summary(self, steamid: str) -> PlayerSummary:
        key = f"player_summary:{steamid}"
        cached = self._cache.get(key)
        if cached is _NAO_EXISTE:
            raise SteamProfileNotFound("perfil não encontrado")
        if cached is not None:
            return cached
        try:
            raw = await self._client.get_player_summary(steamid)
        except SteamProfileNotFound:
            # Conta inexistente não passa a existir: cacheia o "não" para que
            # marretar o mesmo ID inválido não queime a quota da STEAM_API_KEY.
            self._cache.set(key, _NAO_EXISTE, NOT_FOUND_TTL)
            raise
        profile = PlayerSummary(
            personaname=raw.get("personaname", ""),
            avatar_url=raw.get("avatarfull") or None,
        )
        self._cache.set(key, profile, PROFILE_TTL)
        return profile

    async def game_detail(self, steamid: str, appid: int) -> GameDetail:
        try:
            player = await self._client.get_player_achievements(steamid, appid)
        except SteamDataUnavailable:
            # Mesma ambiguidade da biblioteca: só o perfil desempata conta
            # inexistente de conta privada. Pago só no caminho de erro.
            await self._assert_exists(steamid)
            raise
        schema = await self._schema(appid)
        name = schema.get("gameName", "")

        if not player:
            return GameDetail(
                appid=appid,
                name=name,
                supports_achievements=False,
                achieved_count=0,
                total_count=0,
                percent=0.0,
                achievements=[],
            )

        meta = {a["name"]: a for a in schema.get("achievements", [])}
        achievements: list[Achievement] = []
        achieved_count = 0
        for entry in player:
            is_achieved = entry.get("achieved") == 1
            if is_achieved:
                achieved_count += 1
            m = meta.get(entry["apiname"], {})
            achievements.append(
                Achievement(
                    apiname=entry["apiname"],
                    display_name=m.get("displayName") or entry["apiname"],
                    description=m.get("description"),
                    icon_url=m.get("icon") if is_achieved else m.get("icongray"),
                    achieved=is_achieved,
                )
            )

        total = len(player)
        return GameDetail(
            appid=appid,
            name=name,
            supports_achievements=True,
            achieved_count=achieved_count,
            total_count=total,
            percent=_percent(achieved_count, total),
            achievements=achievements,
        )

    async def _assert_exists(self, steamid: str) -> None:
        """Levanta SteamProfileNotFound se a conta não existe; volta calado se existe."""
        await self.player_summary(steamid)

    async def _cached(self, key: str, ttl: int | Callable[[Any], int], fetch):
        """Busca no cache; no miss, chama `fetch` e guarda o resultado.

        `ttl` pode depender do valor (gênero encontrado dura mais que gênero
        ausente). `None` nunca é cacheado: é o próprio sinal de miss do TTLCache.
        """
        hit = self._cache.get(key)
        if hit is not None:
            return hit
        value = await fetch()
        if value is not None:
            self._cache.set(key, value, ttl(value) if callable(ttl) else ttl)
        return value

    async def _owned_games(self, steamid: str) -> list[dict]:
        return await self._cached(
            f"owned_games:{steamid}",
            OWNED_TTL,
            lambda: self._client.get_owned_games(steamid),
        )

    async def _fill_counts(self, steamid: str, games: list[Game]) -> None:
        sem = asyncio.Semaphore(self._concurrency)

        async def fill(game: Game) -> None:
            async with sem:
                try:
                    counts = await self._ach_counts(steamid, game.appid)
                except SteamError:
                    return  # best-effort: um jogo que falha fica sem %, não quebra a página
            if counts is None:
                return
            achieved, total = counts
            game.achieved_count = achieved
            game.total_count = total
            game.percent = _percent(achieved, total)

        await asyncio.gather(*(fill(g) for g in games))

    async def _fill_genres(self, games: list[Game]) -> None:
        # ponytail: cache volátil; cache persistente por appid se o cold-start
        # em biblioteca grande incomodar (ver plano).
        sem = asyncio.Semaphore(self._concurrency)

        async def fill(game: Game) -> None:
            async with sem:
                game.genres = await self._app_genres(game.appid)

        await asyncio.gather(*(fill(g) for g in games))

    async def _app_genres(self, appid: int) -> list[str]:
        return await self._cached(
            f"genres:{appid}",
            lambda genres: GENRES_TTL if genres else GENRES_MISS_TTL,
            lambda: self._client.get_app_genres(appid),
        )

    async def _ach_counts(self, steamid: str, appid: int) -> tuple[int, int] | None:
        async def contar() -> tuple[int, int] | None:
            achievements = await self._client.get_player_achievements(steamid, appid)
            if not achievements:
                return None  # jogo sem conquistas: nada a cachear
            achieved = sum(1 for a in achievements if a.get("achieved") == 1)
            return achieved, len(achievements)

        return await self._cached(f"ach_counts:{steamid}:{appid}", ACH_TTL, contar)

    async def _schema(self, appid: int) -> dict:
        return await self._cached(
            f"schema:{appid}", SCHEMA_TTL, lambda: self._client.get_schema(appid)
        )


def _percent(achieved: int, total: int) -> float:
    return achieved / total * 100 if total else 0.0


def _sort(games: list[Game], sort: str) -> None:
    if sort == "name":
        games.sort(key=lambda g: g.name.lower())
    elif sort == "percent":
        games.sort(key=lambda g: g.percent or 0, reverse=True)
    elif sort == "ach_count":
        games.sort(key=lambda g: g.achieved_count or 0, reverse=True)
    else:  # playtime (default)
        games.sort(key=lambda g: g.playtime_minutes, reverse=True)
