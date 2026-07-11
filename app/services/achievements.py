import asyncio

from app.core.cache import TTLCache
from app.errors import SteamError
from app.schemas.models import Achievement, Game, GameDetail

_ICON_URL = (
    "https://media.steampowered.com/steamcommunity/public/images/apps/{appid}/{hash}.jpg"
)

# TTLs por natureza do dado (segundos). Ver spec REQ-010/CON-010.
OWNED_TTL = 300
ACH_TTL = 300
SCHEMA_TTL = 86_400
GENRES_TTL = 604_800  # 7 dias: gênero encontrado é estático
# [] pode ser 429 transitório da loja, não ausência real de gênero. TTL curto:
# não re-martela a loja a cada load (o que perpetuaria o rate limit), mas
# retenta em ~1h para se recuperar sozinho.
GENRES_MISS_TTL = 3_600


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
        raw = await self._owned_games(steamid)
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

    async def game_detail(self, steamid: str, appid: int) -> GameDetail:
        player = await self._client.get_player_achievements(steamid, appid)
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

    async def _owned_games(self, steamid: str) -> list[dict]:
        key = f"owned_games:{steamid}"
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        raw = await self._client.get_owned_games(steamid)
        self._cache.set(key, raw, OWNED_TTL)
        return raw

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
        key = f"genres:{appid}"
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        genres = await self._client.get_app_genres(appid)
        self._cache.set(key, genres, GENRES_TTL if genres else GENRES_MISS_TTL)
        return genres

    async def _ach_counts(self, steamid: str, appid: int) -> tuple[int, int] | None:
        key = f"ach_counts:{steamid}:{appid}"
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        achievements = await self._client.get_player_achievements(steamid, appid)
        if not achievements:
            return None
        achieved = sum(1 for a in achievements if a.get("achieved") == 1)
        counts = (achieved, len(achievements))
        self._cache.set(key, counts, ACH_TTL)
        return counts

    async def _schema(self, appid: int) -> dict:
        key = f"schema:{appid}"
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        schema = await self._client.get_schema(appid)
        self._cache.set(key, schema, SCHEMA_TTL)
        return schema


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
