import asyncio

from app.core.cache import TTLCache
from app.errors import SteamUnavailableError
from app.services.achievements import AchievementsService


class FakeSteamClient:
    """Client falso injetado — substitui a infra HTTP nos testes de domínio.

    Rastreia chamadas e concorrência para permitir asserções de comportamento
    (cache e Semaphore) sem tocar a rede.
    """

    def __init__(self, owned_games=None, achievements=None, schemas=None, delay=0.0):
        self._owned = owned_games or []
        self._ach = achievements or {}  # appid -> list[dict] | None
        self._schemas = schemas or {}  # appid -> dict
        self._delay = delay
        self.ach_calls: list[int] = []
        self._active = 0
        self.max_active = 0

    async def get_owned_games(self):
        return self._owned

    async def get_player_achievements(self, appid):
        self.ach_calls.append(appid)
        self._active += 1
        self.max_active = max(self.max_active, self._active)
        try:
            if self._delay:
                await asyncio.sleep(self._delay)
            val = self._ach.get(appid)
            if isinstance(val, Exception):
                raise val
            return val
        finally:
            self._active -= 1

    async def get_schema(self, appid):
        return self._schemas.get(appid, {})


def make_service(client, concurrency=5):
    return AchievementsService(client, TTLCache(), concurrency)


async def test_biblioteca_parseada_e_ordenada_por_playtime_decrescente():
    client = FakeSteamClient(
        owned_games=[
            {"appid": 10, "name": "Portal", "playtime_forever": 480, "img_icon_url": "abc"},
            {"appid": 20, "name": "Half-Life 2", "playtime_forever": 7200, "img_icon_url": "def"},
        ]
    )
    service = make_service(client)

    games = await service.list_library()

    assert [g.appid for g in games] == [20, 10]
    assert games[0].name == "Half-Life 2"
    assert games[0].playtime_minutes == 7200
    assert (
        games[0].icon_url
        == "https://media.steampowered.com/steamcommunity/public/images/apps/20/def.jpg"
    )


async def test_ordenacao_por_nome_e_alfabetica():
    client = FakeSteamClient(
        owned_games=[
            {"appid": 20, "name": "Half-Life 2", "playtime_forever": 7200, "img_icon_url": "d"},
            {"appid": 10, "name": "Antichamber", "playtime_forever": 60, "img_icon_url": "a"},
            {"appid": 30, "name": "Portal", "playtime_forever": 480, "img_icon_url": "p"},
        ]
    )
    service = make_service(client)

    games = await service.list_library(sort="name")

    assert [g.name for g in games] == ["Antichamber", "Half-Life 2", "Portal"]


async def test_ordenacao_por_percent_faz_fanout_e_preenche_progresso():
    client = FakeSteamClient(
        owned_games=[
            {"appid": 10, "name": "A", "playtime_forever": 999, "img_icon_url": "a"},
            {"appid": 20, "name": "B", "playtime_forever": 1, "img_icon_url": "b"},
        ],
        achievements={
            10: [{"apiname": "x", "achieved": 1}, {"apiname": "y", "achieved": 0}],  # 50%
            20: [
                {"apiname": "x", "achieved": 1},
                {"apiname": "y", "achieved": 1},
                {"apiname": "z", "achieved": 0},
            ],  # 66.6%
        },
    )
    service = make_service(client)

    games = await service.list_library(sort="percent")

    assert [g.appid for g in games] == [20, 10]
    assert round(games[0].percent, 1) == 66.7
    assert games[1].percent == 50.0
    assert games[1].achieved_count == 1
    assert games[1].total_count == 2


async def test_ordenacao_por_numero_de_conquistas_obtidas():
    client = FakeSteamClient(
        owned_games=[
            {"appid": 10, "name": "A", "playtime_forever": 1, "img_icon_url": "a"},
            {"appid": 20, "name": "B", "playtime_forever": 1, "img_icon_url": "b"},
        ],
        achievements={
            10: [{"apiname": "x", "achieved": 1}],  # 1 obtida
            20: [{"apiname": "x", "achieved": 1}, {"apiname": "y", "achieved": 1}],  # 2 obtidas
        },
    )
    service = make_service(client)

    games = await service.list_library(sort="ach_count")

    assert [g.appid for g in games] == [20, 10]


async def test_fanout_respeita_o_limite_do_semaphore():
    owned = [
        {"appid": i, "name": str(i), "playtime_forever": 1, "img_icon_url": "i"}
        for i in range(6)
    ]
    achievements = {i: [{"apiname": "x", "achieved": 1}] for i in range(6)}
    client = FakeSteamClient(owned_games=owned, achievements=achievements, delay=0.01)
    service = make_service(client, concurrency=2)

    await service.list_library(sort="percent")

    assert client.max_active <= 2


async def test_fanout_tolera_falha_em_um_jogo_sem_quebrar():
    client = FakeSteamClient(
        owned_games=[
            {"appid": 10, "name": "A", "playtime_forever": 1, "img_icon_url": "a"},
            {"appid": 20, "name": "B", "playtime_forever": 1, "img_icon_url": "b"},
        ],
        achievements={
            10: [{"apiname": "x", "achieved": 1}],
            20: SteamUnavailableError("falha transitória"),
        },
    )
    service = make_service(client)

    games = await service.list_library(sort="percent")

    assert {g.appid for g in games} == {10, 20}  # página não quebra
    falho = next(g for g in games if g.appid == 20)
    assert falho.percent is None  # jogo que falhou fica sem %


async def test_repeticao_usa_cache_e_nao_refaz_fanout():
    client = FakeSteamClient(
        owned_games=[
            {"appid": 10, "name": "A", "playtime_forever": 1, "img_icon_url": "a"},
            {"appid": 20, "name": "B", "playtime_forever": 1, "img_icon_url": "b"},
        ],
        achievements={
            10: [{"apiname": "x", "achieved": 1}],
            20: [{"apiname": "x", "achieved": 0}],
        },
    )
    service = make_service(client)

    await service.list_library(sort="percent")
    await service.list_library(sort="percent")

    assert sorted(client.ach_calls) == [10, 20]  # cada jogo buscado uma única vez


async def test_detalhe_junta_achievements_com_schema():
    client = FakeSteamClient(
        achievements={
            10: [{"apiname": "A", "achieved": 1}, {"apiname": "B", "achieved": 0}],
        },
        schemas={
            10: {
                "gameName": "Portal",
                "achievements": [
                    {
                        "name": "A",
                        "displayName": "Conquista A",
                        "description": "desc A",
                        "icon": "iconA",
                        "icongray": "grayA",
                    },
                    {"name": "B", "displayName": "Conquista B", "icon": "iconB", "icongray": "grayB"},
                ],
            }
        },
    )
    service = make_service(client)

    detail = await service.game_detail(10)

    assert detail.name == "Portal"
    assert detail.supports_achievements is True
    assert detail.achieved_count == 1
    assert detail.total_count == 2
    assert detail.percent == 50.0
    obtida = detail.achievements[0]
    assert obtida.display_name == "Conquista A"
    assert obtida.achieved is True
    assert obtida.icon_url == "iconA"
    pendente = detail.achievements[1]
    assert pendente.achieved is False
    assert pendente.icon_url == "grayB"


async def test_detalhe_de_jogo_sem_stats_nao_quebra():
    client = FakeSteamClient(achievements={99: None}, schemas={99: {"gameName": "Sem Stats"}})
    service = make_service(client)

    detail = await service.game_detail(99)

    assert detail.supports_achievements is False
    assert detail.name == "Sem Stats"
    assert detail.achievements == []
