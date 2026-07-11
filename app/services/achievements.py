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


class AchievementsService:
    """Regra de negócio: monta biblioteca e detalhe a partir do client Steam.

    Não conhece FastAPI nem httpx — depende apenas da interface do client, o que
    o torna testável com um client falso (sem rede).
    """

    def __init__(self, client, cache: TTLCache, concurrency: int = 5):
        self._client = client
        self._cache = cache
        self._concurrency = concurrency

    async def list_library(self, sort: str = "playtime") -> list[Game]:
        raw = await self._owned_games()
        games = [
            Game(
                appid=g["appid"],
                name=g["name"],
                playtime_minutes=g["playtime_forever"],
                icon_url=_ICON_URL.format(appid=g["appid"], hash=g["img_icon_url"]),
            )
            for g in raw
        ]
        if sort in ("percent", "ach_count"):
            await self._fill_counts(games)
        _sort(games, sort)
        return games

    async def game_detail(self, appid: int) -> GameDetail:
        player = await self._client.get_player_achievements(appid)
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

    async def _owned_games(self) -> list[dict]:
        cached = self._cache.get("owned_games")
        if cached is not None:
            return cached
        raw = await self._client.get_owned_games()
        self._cache.set("owned_games", raw, OWNED_TTL)
        return raw

    async def _fill_counts(self, games: list[Game]) -> None:
        sem = asyncio.Semaphore(self._concurrency)

        async def fill(game: Game) -> None:
            async with sem:
                try:
                    counts = await self._ach_counts(game.appid)
                except SteamError:
                    return  # best-effort: um jogo que falha fica sem %, não quebra a página
            if counts is None:
                return
            achieved, total = counts
            game.achieved_count = achieved
            game.total_count = total
            game.percent = _percent(achieved, total)

        await asyncio.gather(*(fill(g) for g in games))

    async def _ach_counts(self, appid: int) -> tuple[int, int] | None:
        key = f"ach_counts:{appid}"
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        achievements = await self._client.get_player_achievements(appid)
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
