import asyncio
from datetime import UTC, datetime

import pytest

from app.core.cache import TTLCache
from app.errors import (
    SteamDataUnavailable,
    SteamProfileNotFound,
    SteamUnavailableError,
)
from app.services.achievements import AchievementsService

STEAMID = "76561197960287930"  # SteamID64 de 17 dígitos usado nos testes


class FakeSteamClient:
    """Client falso injetado — substitui a infra HTTP nos testes de domínio.

    Rastreia chamadas e concorrência para permitir asserções de comportamento
    (cache e Semaphore) sem tocar a rede.
    """

    def __init__(
        self,
        owned_games=None,
        achievements=None,
        schemas=None,
        genres=None,
        summary=None,
        global_pct=None,
        delay=0.0,
    ):
        self._owned = owned_games if owned_games is not None else []  # list | Exception
        self._ach = achievements or {}  # appid -> list[dict] | None
        self._schemas = schemas or {}  # appid -> dict
        self._genres = genres or {}  # appid -> list[str] | Exception
        self._summary = summary if summary is not None else {}  # dict | Exception
        self._global = global_pct or {}  # appid -> dict[str, float] | Exception
        self._delay = delay
        self.ach_calls: list[int] = []
        self.genre_calls: list[int] = []
        self.global_calls: list[int] = []
        self.owned_calls: list[str] = []  # steamids que buscaram a biblioteca
        self.summary_calls: list[str] = []
        self._active = 0
        self.max_active = 0

    async def get_owned_games(self, steamid):
        self.owned_calls.append(steamid)
        if isinstance(self._owned, Exception):
            raise self._owned
        return self._owned

    async def get_player_summary(self, steamid):
        self.summary_calls.append(steamid)
        if isinstance(self._summary, Exception):
            raise self._summary
        return self._summary

    async def get_player_achievements(self, steamid, appid):
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

    async def get_app_genres(self, appid):
        # Contrato do client real: best-effort, sempre lista (nunca levanta).
        self.genre_calls.append(appid)
        return self._genres.get(appid, [])

    async def get_global_achievement_percentages(self, appid):
        # Ao contrário dos gêneros, o client real *levanta* aqui (passa pelo
        # _get()): quem absorve a falha é o service.
        self.global_calls.append(appid)
        val = self._global.get(appid, {})
        if isinstance(val, Exception):
            raise val
        return val


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

    games = await service.list_library(STEAMID)

    assert [g.appid for g in games] == [20, 10]
    assert games[0].name == "Half-Life 2"
    assert games[0].playtime_minutes == 7200
    assert (
        games[0].icon_url
        == "https://media.steampowered.com/steamcommunity/public/images/apps/20/def.jpg"
    )


async def test_jogo_sem_icone_nao_gera_url_quebrada():
    client = FakeSteamClient(
        owned_games=[
            {"appid": 30, "name": "Sem Ícone", "playtime_forever": 10, "img_icon_url": ""},
        ]
    )
    service = make_service(client)

    games = await service.list_library(STEAMID)

    assert games[0].icon_url is None


async def test_playtime_recente_so_aparece_em_quem_jogou():
    client = FakeSteamClient(
        owned_games=[
            # A Steam só manda playtime_2weeks quando houve jogo nas 2 semanas;
            # a ausência é o caso normal da maioria da biblioteca.
            {
                "appid": 10,
                "name": "Jogado",
                "playtime_forever": 600,
                "playtime_2weeks": 120,
                "img_icon_url": "a",
            },
            {"appid": 20, "name": "Parado", "playtime_forever": 600, "img_icon_url": "b"},
        ]
    )
    service = make_service(client)

    jogado, parado = await service.list_library(STEAMID, sort="name")

    assert jogado.playtime_2weeks_minutes == 120
    assert parado.playtime_2weeks_minutes is None


async def test_ordena_por_ultima_vez_jogado_com_nunca_jogados_no_fim():
    client = FakeSteamClient(
        owned_games=[
            # rtime_last_played 0 (e ausente) significam "nunca jogado", não 1970:
            # os dois têm de cair no fim, não no topo por serem "mais antigos".
            {"appid": 10, "name": "Antigo", "playtime_forever": 1, "rtime_last_played": 1_600_000_000},
            {"appid": 20, "name": "Zerado", "playtime_forever": 1, "rtime_last_played": 0},
            {"appid": 30, "name": "Recente", "playtime_forever": 1, "rtime_last_played": 1_700_000_000},
            {"appid": 40, "name": "Ausente", "playtime_forever": 1},
        ]
    )
    service = make_service(client)

    games = await service.list_library(STEAMID, sort="last_played")

    assert [g.appid for g in games][:2] == [30, 10]
    assert {g.appid for g in games[2:]} == {20, 40}
    assert games[0].last_played_at == datetime.fromtimestamp(1_700_000_000, UTC)
    assert all(g.last_played_at is None for g in games[2:])
    assert client.ach_calls == []  # custo zero: nenhuma chamada além do GetOwnedGames


async def test_ordenacao_por_nome_e_alfabetica():
    client = FakeSteamClient(
        owned_games=[
            {"appid": 20, "name": "Half-Life 2", "playtime_forever": 7200, "img_icon_url": "d"},
            {"appid": 10, "name": "Antichamber", "playtime_forever": 60, "img_icon_url": "a"},
            {"appid": 30, "name": "Portal", "playtime_forever": 480, "img_icon_url": "p"},
        ]
    )
    service = make_service(client)

    games = await service.list_library(STEAMID, sort="name")

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

    games = await service.list_library(STEAMID, sort="percent")

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

    games = await service.list_library(STEAMID, sort="ach_count")

    assert [g.appid for g in games] == [20, 10]


async def test_fanout_respeita_o_limite_do_semaphore():
    owned = [
        {"appid": i, "name": str(i), "playtime_forever": 1, "img_icon_url": "i"}
        for i in range(6)
    ]
    achievements = {i: [{"apiname": "x", "achieved": 1}] for i in range(6)}
    client = FakeSteamClient(owned_games=owned, achievements=achievements, delay=0.01)
    service = make_service(client, concurrency=2)

    await service.list_library(STEAMID, sort="percent")

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

    games = await service.list_library(STEAMID, sort="percent")

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

    await service.list_library(STEAMID, sort="percent")
    await service.list_library(STEAMID, sort="percent")

    assert sorted(client.ach_calls) == [10, 20]  # cada jogo buscado uma única vez


async def test_cache_da_biblioteca_nao_vaza_entre_steamids():
    client = FakeSteamClient(
        owned_games=[{"appid": 10, "name": "A", "playtime_forever": 1, "img_icon_url": "a"}]
    )
    service = make_service(client)

    await service.list_library("11111111111111111")
    await service.list_library("11111111111111111")  # cache hit para o mesmo id
    await service.list_library("22222222222222222")  # id diferente: nova busca

    assert client.owned_calls == ["11111111111111111", "22222222222222222"]


async def test_agrupar_por_genero_preenche_generos():
    client = FakeSteamClient(
        owned_games=[
            {"appid": 10, "name": "A", "playtime_forever": 1, "img_icon_url": "a"},
            {"appid": 20, "name": "B", "playtime_forever": 1, "img_icon_url": "b"},
        ],
        genres={10: ["Ação", "Aventura"], 20: ["RPG"]},
    )
    service = make_service(client)

    games = await service.list_library(STEAMID, group="genre")

    por_appid = {g.appid: g.genres for g in games}
    assert por_appid == {10: ["Ação", "Aventura"], 20: ["RPG"]}


async def test_sem_grupo_nao_busca_generos():
    client = FakeSteamClient(
        owned_games=[{"appid": 10, "name": "A", "playtime_forever": 1, "img_icon_url": "a"}],
        genres={10: ["Ação"]},
    )
    service = make_service(client)

    games = await service.list_library(STEAMID)  # sem group

    assert client.genre_calls == []  # lazy: só busca gênero quando pedido
    assert games[0].genres == []


async def test_jogo_sem_genero_fica_vazio_sem_quebrar():
    client = FakeSteamClient(
        owned_games=[
            {"appid": 10, "name": "A", "playtime_forever": 1, "img_icon_url": "a"},
            {"appid": 20, "name": "B", "playtime_forever": 1, "img_icon_url": "b"},
        ],
        genres={10: ["Ação"]},  # 20 não tem gênero → []
    )
    service = make_service(client)

    games = await service.list_library(STEAMID, group="genre")

    por_appid = {g.appid: g.genres for g in games}
    assert por_appid == {10: ["Ação"], 20: []}  # página não quebra


async def test_genero_vazio_e_cacheado_para_nao_re_martelar_a_loja():
    # [] entra no cache (TTL curto): loads seguidos não re-martelam a loja, o
    # que só perpetuaria o rate limit. O retry vem quando o TTL curto expira.
    client = FakeSteamClient(
        owned_games=[{"appid": 10, "name": "A", "playtime_forever": 1, "img_icon_url": "a"}],
        genres={10: []},
    )
    service = make_service(client)

    await service.list_library(STEAMID, group="genre")
    await service.list_library(STEAMID, group="genre")

    assert client.genre_calls == [10]  # segundo load usa o cache, não re-bate


async def test_generos_sao_cacheados():
    client = FakeSteamClient(
        owned_games=[{"appid": 10, "name": "A", "playtime_forever": 1, "img_icon_url": "a"}],
        genres={10: ["Ação"]},
    )
    service = make_service(client)

    await service.list_library(STEAMID, group="genre")
    await service.list_library(STEAMID, group="genre")

    assert client.genre_calls == [10]  # gênero é estático: buscado uma única vez


async def test_perfil_expoe_nome_e_avatar():
    client = FakeSteamClient(
        summary={
            "steamid": STEAMID,
            "personaname": "Fulano",
            "avatarfull": "https://avatars.steamstatic.com/abc_full.jpg",
        }
    )
    service = make_service(client)

    profile = await service.player_summary(STEAMID)

    assert profile.personaname == "Fulano"
    assert profile.avatar_url == "https://avatars.steamstatic.com/abc_full.jpg"


async def test_perfil_e_cacheado_por_steamid():
    client = FakeSteamClient(summary={"personaname": "Fulano"})
    service = make_service(client)

    await service.player_summary("11111111111111111")
    await service.player_summary("11111111111111111")  # cache hit
    await service.player_summary("22222222222222222")  # id diferente: nova busca

    assert client.summary_calls == ["11111111111111111", "22222222222222222"]


async def test_perfil_inexistente_nao_remartela_a_steam():
    # /profile é dirigido por input público: sem cachear o "não existe", marretar
    # o mesmo ID inválido queima a quota da STEAM_API_KEY sem teto.
    client = FakeSteamClient(summary=SteamProfileNotFound("não encontrado"))
    service = make_service(client)

    for _ in range(3):
        with pytest.raises(SteamProfileNotFound):
            await service.player_summary(STEAMID)

    assert client.summary_calls == [STEAMID]  # só a primeira foi à Steam


async def test_biblioteca_de_conta_inexistente_distingue_de_perfil_privado():
    # A Steam responde igual nos dois casos (biblioteca indisponível); só o
    # perfil desempata. Sem isso, quem abre /u/{id-inexistente} direto pela URL
    # lê "o perfil pode estar privado" — mensagem errada.
    client = FakeSteamClient(
        owned_games=SteamDataUnavailable("biblioteca indisponível"),
        summary=SteamProfileNotFound("perfil não encontrado"),
    )
    service = make_service(client)

    with pytest.raises(SteamProfileNotFound):
        await service.list_library(STEAMID)


async def test_biblioteca_de_perfil_privado_continua_data_unavailable():
    # Conta existe (o perfil responde), mas a biblioteca é privada.
    client = FakeSteamClient(
        owned_games=SteamDataUnavailable("biblioteca indisponível"),
        summary={"personaname": "Fulano"},
    )
    service = make_service(client)

    with pytest.raises(SteamDataUnavailable):
        await service.list_library(STEAMID)


async def test_detalhe_de_conta_inexistente_distingue_de_perfil_privado():
    # Mesmo caso da biblioteca, na rota do detalhe: link compartilhado com um id
    # inexistente não pode acusar "perfil privado".
    client = FakeSteamClient(
        achievements={220: SteamDataUnavailable("acesso negado")},
        summary=SteamProfileNotFound("perfil não encontrado"),
    )
    service = make_service(client)

    with pytest.raises(SteamProfileNotFound):
        await service.game_detail(STEAMID, 220)


async def test_biblioteca_ok_nao_consulta_o_perfil():
    # A desambiguação é só no caminho de erro: caminho feliz não paga chamada extra.
    client = FakeSteamClient(
        owned_games=[{"appid": 10, "name": "Portal", "playtime_forever": 60}]
    )
    service = make_service(client)

    await service.list_library(STEAMID)

    assert client.summary_calls == []


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

    detail = await service.game_detail(STEAMID, 10)

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


async def test_detalhe_expoe_a_data_de_desbloqueio_das_obtidas():
    client = FakeSteamClient(
        achievements={
            10: [
                {"apiname": "A", "achieved": 1, "unlocktime": 1_312_345_678},
                # Desbloqueio antigo demais: a Steam devolve 0 mesmo com achieved=1.
                {"apiname": "B", "achieved": 1, "unlocktime": 0},
                {"apiname": "C", "achieved": 0, "unlocktime": 0},
            ]
        },
    )
    service = make_service(client)

    detail = await service.game_detail(STEAMID, 10)

    obtida, sem_data, pendente = detail.achievements
    assert obtida.unlocked_at == datetime(2011, 8, 3, 4, 27, 58, tzinfo=UTC)
    assert sem_data.unlocked_at is None
    assert pendente.unlocked_at is None


async def test_detalhe_sem_schema_usa_o_nome_da_biblioteca():
    client = FakeSteamClient(
        owned_games=[
            {"appid": 77, "name": "Jogo Sem Schema", "playtime_forever": 10, "img_icon_url": "x"}
        ],
        achievements={77: [{"apiname": "A", "achieved": 1}]},
        schemas={},  # jogo sem schema publicado: sem gameName
    )
    service = make_service(client)
    await service.list_library(STEAMID)  # semeia o cache da biblioteca

    detail = await service.game_detail(STEAMID, 77)

    assert detail.name == "Jogo Sem Schema"


async def test_detalhe_sem_schema_e_sem_biblioteca_cai_no_nome_generico():
    # Acesso direto pela URL: nada em cache e o jogo não publica schema.
    client = FakeSteamClient(achievements={77: [{"apiname": "A", "achieved": 1}]}, schemas={})
    service = make_service(client)

    detail = await service.game_detail(STEAMID, 77)

    assert detail.name == "App 77"
    assert client.owned_calls == []  # não paga uma chamada à Steam só pelo título


async def test_detalhe_de_jogo_sem_stats_nao_quebra():
    client = FakeSteamClient(achievements={99: None}, schemas={99: {"gameName": "Sem Stats"}})
    service = make_service(client)

    detail = await service.game_detail(STEAMID, 99)

    assert detail.supports_achievements is False
    assert detail.name == "Sem Stats"
    assert detail.achievements == []


async def test_detalhe_expoe_a_raridade_global_de_cada_conquista():
    client = FakeSteamClient(
        achievements={10: [{"apiname": "A", "achieved": 1}, {"apiname": "B", "achieved": 0}]},
        schemas={10: {"gameName": "Portal", "achievements": []}},
        global_pct={10: {"A": 42.7, "B": 4.1}},
    )
    service = make_service(client)

    detail = await service.game_detail(STEAMID, 10)

    assert {a.apiname: a.global_percent for a in detail.achievements} == {"A": 42.7, "B": 4.1}


async def test_conquista_sem_raridade_no_payload_fica_sem_raridade():
    client = FakeSteamClient(
        achievements={10: [{"apiname": "A", "achieved": 1}, {"apiname": "SECRETA", "achieved": 0}]},
        schemas={10: {"gameName": "Portal", "achievements": []}},
        global_pct={10: {"A": 42.7}},  # a Steam não devolve todas
    )
    service = make_service(client)

    detail = await service.game_detail(STEAMID, 10)

    secreta = next(a for a in detail.achievements if a.apiname == "SECRETA")
    assert secreta.global_percent is None


async def test_detalhe_sobrevive_a_raridade_indisponivel():
    # Jogo sem stats globais devolve 403 → SteamDataUnavailable. Raridade é
    # decoração: some da tela, mas não pode derrubar o detalhe.
    client = FakeSteamClient(
        achievements={10: [{"apiname": "A", "achieved": 1}]},
        schemas={10: {"gameName": "Portal", "achievements": []}},
        global_pct={10: SteamDataUnavailable("sem stats globais")},
    )
    service = make_service(client)

    detail = await service.game_detail(STEAMID, 10)

    assert detail.supports_achievements is True
    assert detail.achieved_count == 1
    assert detail.achievements[0].global_percent is None


async def test_raridade_e_cacheada_por_jogo_e_nao_por_jogador():
    # A chave é global_pct:{appid}: dois jogadores diferentes no mesmo jogo
    # pagam uma única chamada.
    client = FakeSteamClient(
        achievements={10: [{"apiname": "A", "achieved": 1}]},
        schemas={10: {"gameName": "Portal", "achievements": []}},
        global_pct={10: {"A": 42.7}},
    )
    service = make_service(client)

    await service.game_detail(STEAMID, 10)
    await service.game_detail("76561197960287931", 10)

    assert client.global_calls == [10]


async def test_jogo_sem_conquistas_nao_paga_a_chamada_de_raridade():
    # Não haveria onde exibir a raridade: buscá-la só queimaria quota (e um
    # token do bucket) num dado que o branch descarta.
    client = FakeSteamClient(achievements={10: None}, schemas={10: {"gameName": "Sem Stats"}})
    service = make_service(client)

    detail = await service.game_detail(STEAMID, 10)

    assert detail.supports_achievements is False
    assert client.global_calls == []
