import asyncio
from datetime import UTC, datetime

import pytest

from app.core.cache import TTLCache
from app.errors import (
    SteamDataUnavailable,
    SteamProfileNotFound,
    SteamUnavailableError,
    SteamVanityNotFound,
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
        schemas_en=None,
        genres=None,
        summary=None,
        global_pct=None,
        vanity=None,
        delay=0.0,
    ):
        self._vanity = vanity or {}  # nome -> steamid | Exception
        self.vanity_calls: list[str] = []
        self._owned = owned_games if owned_games is not None else []  # list | Exception
        self._ach = achievements or {}  # appid -> list[dict] | None
        self._schemas = schemas or {}  # appid -> dict | Exception
        self._schemas_en = schemas_en or {}  # appid -> dict | Exception
        self._genres = genres or {}  # appid -> list[str] | Exception
        self._summary = summary if summary is not None else {}  # dict | Exception
        self._global = global_pct or {}  # appid -> dict[str, float] | Exception
        self._delay = delay
        self.ach_calls: list[int] = []
        self.schema_calls: list[tuple[int, str | None]] = []  # (appid, lang)
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

    async def resolve_vanity_url(self, nome):
        self.vanity_calls.append(nome)
        val = self._vanity.get(nome)
        if val is None:
            raise SteamVanityNotFound("nome de perfil não encontrado")
        return val

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

    async def get_schema(self, appid, lang=None):
        # Contrato do client real: `lang=None` significa "o idioma configurado"
        # (pt-BR). Só o schema do `name_en` pede idioma explícito.
        self.schema_calls.append((appid, lang))
        origem = self._schemas_en if lang == "english" else self._schemas
        val = origem.get(appid, {})
        if isinstance(val, Exception):
            raise val
        return val

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


async def test_biblioteca_parseada_na_ordem_que_a_steam_devolveu():
    """Ordenar é trabalho do cliente: aqui só se parseia, sem reordenar.

    A ordem de saída é a de entrada — o serviço não tem opinião sobre ela.
    """
    client = FakeSteamClient(
        owned_games=[
            {"appid": 10, "name": "Portal", "playtime_forever": 480, "img_icon_url": "abc"},
            {"appid": 20, "name": "Half-Life 2", "playtime_forever": 7200, "img_icon_url": "def"},
        ]
    )
    service = make_service(client)

    games = await service.list_library(STEAMID)

    assert [g.appid for g in games] == [10, 20]
    assert games[1].name == "Half-Life 2"
    assert games[1].playtime_minutes == 7200
    assert (
        games[1].icon_url
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

    jogado, parado = await service.list_library(STEAMID)

    assert jogado.playtime_2weeks_minutes == 120
    assert parado.playtime_2weeks_minutes is None


async def test_nunca_jogado_nao_vira_1970():
    """`rtime_last_played` 0 (e ausente) significam "nunca jogado", não a epoch.

    Traduzir o 0 para 1970 daria ao jogo uma data que ele não tem, e o cliente
    ordenaria por ela.
    """
    client = FakeSteamClient(
        owned_games=[
            {"appid": 10, "name": "Jogado", "playtime_forever": 1, "rtime_last_played": 1_700_000_000},
            {"appid": 20, "name": "Zerado", "playtime_forever": 1, "rtime_last_played": 0},
            {"appid": 30, "name": "Ausente", "playtime_forever": 1},
        ]
    )
    service = make_service(client)

    jogado, zerado, ausente = await service.list_library(STEAMID)

    assert jogado.last_played_at == datetime.fromtimestamp(1_700_000_000, UTC)
    assert zerado.last_played_at is None
    assert ausente.last_played_at is None
    assert client.ach_calls == []  # custo zero: nenhuma chamada além do GetOwnedGames


async def test_include_achievements_faz_fanout_e_preenche_progresso():
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

    a, b = await service.list_library(STEAMID, include=["achievements"])

    assert a.percent == 50.0
    assert a.achieved_count == 1
    assert a.total_count == 2
    assert round(b.percent, 1) == 66.7
    assert b.achieved_count == 2
    assert b.total_count == 3


async def test_fanout_respeita_o_limite_do_semaphore():
    owned = [
        {"appid": i, "name": str(i), "playtime_forever": 1, "img_icon_url": "i"}
        for i in range(6)
    ]
    achievements = {i: [{"apiname": "x", "achieved": 1}] for i in range(6)}
    client = FakeSteamClient(owned_games=owned, achievements=achievements, delay=0.01)
    service = make_service(client, concurrency=2)

    await service.list_library(STEAMID, include=["achievements"])

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

    games = await service.list_library(STEAMID, include=["achievements"])

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

    await service.list_library(STEAMID, include=["achievements"])
    await service.list_library(STEAMID, include=["achievements"])

    assert sorted(client.ach_calls) == [10, 20]  # cada jogo buscado uma única vez


async def test_sem_include_a_lista_vem_sem_progresso_e_sem_fanout():
    """Quem decide o que buscar é `include`, e só ele.

    A biblioteca sem `include` é o caminho barato — uma chamada à Steam, no total.
    Deixar qualquer outro parâmetro disparar o fan-out esconderia N chamadas que
    o caller nunca pediu.
    """
    client = FakeSteamClient(
        owned_games=[{"appid": 10, "name": "A", "playtime_forever": 1, "img_icon_url": "a"}],
        achievements={10: [{"apiname": "x", "achieved": 1}]},
    )
    service = make_service(client)

    games = await service.list_library(STEAMID)

    assert client.ach_calls == []  # nenhum fan-out sem include
    assert games[0].percent is None  # e a lista não quebra: só vem sem %


async def test_detalhe_reaproveita_as_conquistas_ja_buscadas_pelo_fanout():
    """Biblioteca e detalhe leem o mesmo dado da Steam — logo, o mesmo cache.

    Quem ordena por % e clica num jogo já tem as conquistas dele em mãos: pagar a
    chamada de novo é queimar quota por nada.
    """
    client = FakeSteamClient(
        owned_games=[
            {"appid": 10, "name": "A", "playtime_forever": 1, "img_icon_url": "a"},
        ],
        achievements={10: [{"apiname": "x", "achieved": 1}]},
        schemas={10: {"gameName": "A", "achievements": []}},
    )
    service = make_service(client)

    await service.list_library(STEAMID, include=["achievements"])
    detail = await service.game_detail(STEAMID, 10)

    assert client.ach_calls == [10]  # o detalhe não re-consulta a Steam
    # Nem re-busca a biblioteca só pelo título: o _ensure_library lê o cache que
    # o list_library já semeou. A única chamada é a do fan-out.
    assert client.owned_calls == [STEAMID]
    assert detail.achieved_count == 1


async def test_fanout_reaproveita_as_conquistas_ja_buscadas_pelo_detalhe():
    """A recíproca: quem chega pelo deep-link do detalhe já semeia o cache do %."""
    client = FakeSteamClient(
        owned_games=[
            {"appid": 10, "name": "A", "playtime_forever": 1, "img_icon_url": "a"},
        ],
        achievements={10: [{"apiname": "x", "achieved": 1}]},
        schemas={10: {"gameName": "A", "achievements": []}},
    )
    service = make_service(client)

    await service.game_detail(STEAMID, 10)
    games = await service.list_library(STEAMID, include=["achievements"])

    assert client.ach_calls == [10]  # o fan-out não re-consulta a Steam
    assert games[0].percent == 100.0


async def test_conquista_malformada_nao_derruba_a_biblioteca():
    """Entry sem `apiname` é lixo da Steam, não motivo para 500.

    O fan-out é best-effort por jogo (REQ-004), mas ele só engole `SteamError` —
    um KeyError aqui escaparia do `except` e derrubaria o `gather` inteiro, isto é,
    a biblioteca toda por causa de uma conquista de um jogo.
    """
    client = FakeSteamClient(
        owned_games=[{"appid": 10, "name": "A", "playtime_forever": 1, "img_icon_url": "a"}],
        achievements={
            10: [
                {"achieved": 1},  # sem apiname: a Steam às vezes manda lixo
                {"apiname": "x", "achieved": 1},
            ]
        },
    )
    service = make_service(client)

    games = await service.list_library(STEAMID, include=["achievements"])

    assert games[0].percent == 100.0  # a entrada sem nome é descartada, não conta
    assert games[0].total_count == 1


async def test_cache_de_conquistas_nao_guarda_o_payload_gordo_da_steam():
    """O teto do TTLCache conta entradas, não bytes — e o steamid vem da URL.

    A Steam manda `name` e `description` (o client pede `l=brazilian`) em cada
    conquista, e o app os descarta: o texto exibido vem do `schema:{appid}`, que é
    cacheado por jogo e compartilhado. Guardar o payload cru por `steamid × appid`
    faria o cache inchar sem que o teto percebesse.
    """
    cache = TTLCache()
    client = FakeSteamClient(
        owned_games=[{"appid": 10, "name": "A", "playtime_forever": 1, "img_icon_url": "a"}],
        achievements={
            10: [
                {
                    "apiname": "x",
                    "achieved": 1,
                    "unlocktime": 1_600_000_000,
                    "name": "Nome longo vindo da Steam",
                    "description": "Descrição longa vinda da Steam",
                }
            ]
        },
    )
    service = AchievementsService(client, cache)

    await service.list_library(STEAMID, include=["achievements"])

    (entrada,) = cache.get(f"player_ach:{STEAMID}:10")
    assert entrada._fields == ("apiname", "achieved", "unlocktime")
    assert entrada.achieved is True  # normalizado na fronteira: bool, não o 0/1 da Steam


async def test_jogo_sem_conquistas_tambem_e_cacheado():
    """Cache negativo: "este jogo não tem conquistas" é uma resposta, não um miss.

    Sem isso, todo load com include=achievements re-consulta a Steam para cada jogo sem
    conquistas — uma sangria de quota que se repete para sempre, não uma vez.
    """
    client = FakeSteamClient(
        owned_games=[
            {"appid": 10, "name": "A", "playtime_forever": 1, "img_icon_url": "a"},
            {"appid": 20, "name": "Sem conquistas", "playtime_forever": 1, "img_icon_url": "b"},
        ],
        achievements={10: [{"apiname": "x", "achieved": 1}], 20: None},
    )
    service = make_service(client)

    await service.list_library(STEAMID, include=["achievements"])
    games = await service.list_library(STEAMID, include=["achievements"])

    assert sorted(client.ach_calls) == [10, 20]  # o segundo load não re-bate no 20
    sem_conquistas = next(g for g in games if g.appid == 20)
    assert sem_conquistas.percent is None  # segue sem %, como antes


async def test_cache_da_biblioteca_nao_vaza_entre_steamids():
    client = FakeSteamClient(
        owned_games=[{"appid": 10, "name": "A", "playtime_forever": 1, "img_icon_url": "a"}]
    )
    service = make_service(client)

    await service.list_library("11111111111111111")
    await service.list_library("11111111111111111")  # cache hit para o mesmo id
    await service.list_library("22222222222222222")  # id diferente: nova busca

    assert client.owned_calls == ["11111111111111111", "22222222222222222"]


async def test_include_genres_preenche_os_generos():
    client = FakeSteamClient(
        owned_games=[
            {"appid": 10, "name": "A", "playtime_forever": 1, "img_icon_url": "a"},
            {"appid": 20, "name": "B", "playtime_forever": 1, "img_icon_url": "b"},
        ],
        genres={10: ["Ação", "Aventura"], 20: ["RPG"]},
    )
    service = make_service(client)

    games = await service.list_library(STEAMID, include=["genres"])

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

    games = await service.list_library(STEAMID, include=["genres"])

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

    await service.list_library(STEAMID, include=["genres"])
    await service.list_library(STEAMID, include=["genres"])

    assert client.genre_calls == [10]  # segundo load usa o cache, não re-bate


async def test_generos_sao_cacheados():
    client = FakeSteamClient(
        owned_games=[{"appid": 10, "name": "A", "playtime_forever": 1, "img_icon_url": "a"}],
        genres={10: ["Ação"]},
    )
    service = make_service(client)

    await service.list_library(STEAMID, include=["genres"])
    await service.list_library(STEAMID, include=["genres"])

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


async def test_detalhe_de_jogo_fora_da_biblioteca_cai_no_nome_generico():
    # Jogo que não consta na biblioteca (delistado/removido) e não publica
    # schema. O detalhe busca a biblioteca (para o título de loja), não acha o
    # appid lá, e só então cai no genérico — pior fallback, caso raro.
    client = FakeSteamClient(achievements={77: [{"apiname": "A", "achieved": 1}]}, schemas={})
    service = make_service(client)

    detail = await service.game_detail(STEAMID, 77)

    assert detail.name == "App 77"


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


async def test_detalhe_prefere_o_nome_da_biblioteca_ao_codinome_do_schema():
    # Caso real (appid 1282100): a biblioteca diz "Remnant II", mas o gameName do
    # schema é "GFREMP2" — o codinome interno do estúdio. Quem manda é a loja.
    client = FakeSteamClient(
        owned_games=[
            {"appid": 10, "name": "Remnant II", "playtime_forever": 60, "img_icon_url": "a"}
        ],
        achievements={10: [{"apiname": "x", "achieved": 1}]},
        schemas={10: {"gameName": "GFREMP2", "achievements": []}},
    )
    service = make_service(client)
    await service.list_library(STEAMID)  # semeia o cache da biblioteca

    detail = await service.game_detail(STEAMID, 10)

    assert detail.name == "Remnant II"


async def test_vanity_resolvido_e_cacheado():
    client = FakeSteamClient(vanity={"gabelogannewell": STEAMID})
    service = AchievementsService(client, TTLCache())

    primeiro = await service.resolve_vanity("gabelogannewell")
    segundo = await service.resolve_vanity("gabelogannewell")

    assert primeiro == segundo == STEAMID
    # Uma única ida à Steam: o segundo pedido sai do cache.
    assert client.vanity_calls == ["gabelogannewell"]


async def test_nome_inexistente_e_cacheado_e_nao_queima_a_quota():
    client = FakeSteamClient(vanity={})
    service = AchievementsService(client, TTLCache())

    for _ in range(3):
        with pytest.raises(SteamVanityNotFound):
            await service.resolve_vanity("nao-existe")

    # O "não" também é resposta: marretar o mesmo nome três vezes gasta uma única
    # chamada da chave, não três.
    assert client.vanity_calls == ["nao-existe"]


async def test_detalhe_expoe_o_nome_em_ingles_ao_lado_do_nome_traduzido():
    """AC-090: o card mostra pt-BR; quem busca guia precisa do inglês.

    Os dois nomes convivem porque não são derivável um do outro — a Steam devolve
    textos diferentes, não traduções ("Descanso no Spa" × "Spa Healer").
    """
    client = FakeSteamClient(
        achievements={485510: [{"apiname": "ACH_SPA", "achieved": 0}]},
        schemas={
            485510: {
                "gameName": "Nioh",
                "achievements": [{"name": "ACH_SPA", "displayName": "Descanso no Spa"}],
            }
        },
        schemas_en={
            485510: {
                "gameName": "Nioh",
                "achievements": [{"name": "ACH_SPA", "displayName": "Spa Healer"}],
            }
        },
    )
    service = make_service(client)

    detail = await service.game_detail(STEAMID, 485510)

    spa = next(a for a in detail.achievements if a.apiname == "ACH_SPA")
    assert spa.display_name == "Descanso no Spa"
    assert spa.name_en == "Spa Healer"


async def test_conquista_fora_do_schema_ingles_fica_sem_nome_em_ingles():
    """AC-091: conquista oculta/nova que o schema inglês não trouxe.

    O `display_name` cai para o `apiname` (comportamento antigo); o `name_en`,
    não — sem nome buscável, o link não deve existir.
    """
    client = FakeSteamClient(
        achievements={10: [{"apiname": "A", "achieved": 0}, {"apiname": "SECRETA", "achieved": 0}]},
        schemas={10: {"gameName": "Portal", "achievements": [{"name": "A", "displayName": "Bolo"}]}},
        schemas_en={10: {"gameName": "Portal", "achievements": [{"name": "A", "displayName": "Cake"}]}},
    )
    service = make_service(client)

    detail = await service.game_detail(STEAMID, 10)

    nomes = {a.apiname: a.name_en for a in detail.achievements}
    assert nomes == {"A": "Cake", "SECRETA": None}
    # A ausência é só do inglês: o resto da conquista continua de pé.
    secreta = next(a for a in detail.achievements if a.apiname == "SECRETA")
    assert secreta.display_name == "SECRETA"


async def test_detalhe_sobrevive_ao_schema_ingles_indisponivel():
    """AC-092: o nome em inglês é decoração — some da tela, não derruba a tela.

    Mesma regra que a raridade já segue. Só o link "Como conseguir" desaparece;
    conquista, progresso e raridade continuam servidos.
    """
    client = FakeSteamClient(
        achievements={10: [{"apiname": "A", "achieved": 1}]},
        schemas={10: {"gameName": "Portal", "achievements": [{"name": "A", "displayName": "Bolo"}]}},
        schemas_en={10: SteamUnavailableError("boom")},
        global_pct={10: {"A": 42.7}},
    )
    service = make_service(client)

    detail = await service.game_detail(STEAMID, 10)

    assert [a.name_en for a in detail.achievements] == [None]
    assert detail.achievements[0].display_name == "Bolo"
    assert detail.achievements[0].global_percent == 42.7
    assert detail.percent == 100.0


async def test_jogo_sem_conquistas_nao_paga_a_chamada_do_schema_ingles():
    """AC-093: sem conquista não há link, e sem link não há o que buscar.

    Irmão do teste da raridade: o branch sem conquistas não paga decoração.
    """
    client = FakeSteamClient(
        achievements={10: None},  # a Steam disse: jogo sem stats
        schemas={10: {"gameName": "Portal", "achievements": []}},
    )
    service = make_service(client)

    detail = await service.game_detail(STEAMID, 10)

    assert detail.supports_achievements is False
    assert ("english" not in [lang for _, lang in client.schema_calls])
    assert client.schema_calls == [(10, None)]  # só o schema pt-BR, do título


async def test_schema_ingles_e_buscado_uma_vez_por_jogo():
    """AC-094: a chave é por *jogo* — o segundo visitante não paga de novo.

    É o que torna a chamada extra aceitável: ela é amortizada entre todos os
    jogadores que abrirem o detalhe do mesmo jogo dentro do TTL.
    """
    client = FakeSteamClient(
        achievements={10: [{"apiname": "A", "achieved": 0}]},
        schemas={10: {"gameName": "Portal", "achievements": [{"name": "A", "displayName": "Bolo"}]}},
        schemas_en={10: {"gameName": "Portal", "achievements": [{"name": "A", "displayName": "Cake"}]}},
    )
    service = make_service(client)

    await service.game_detail(STEAMID, 10)
    detail = await service.game_detail("76561197960287931", 10)  # outro jogador

    assert client.schema_calls.count((10, "english")) == 1
    assert detail.achievements[0].name_en == "Cake"


async def test_detalhe_busca_o_nome_de_loja_quando_a_biblioteca_esta_fria():
    """Deep-link ou cache expirado (OWNED_TTL): sem a biblioteca em cache, o
    detalhe ainda mostra 'Tails of Iron', não 'App 1283410'.

    Importa porque esse nome vai na busca de vídeo — 'App 1283410' como token
    envenena a query. O `gameName` do schema não salva: vem vazio neste jogo.
    """
    client = FakeSteamClient(
        owned_games=[
            {"appid": 1283410, "name": "Tails of Iron", "playtime_forever": 60, "img_icon_url": ""}
        ],
        achievements={1283410: [{"apiname": "A", "achieved": 0}]},
        schemas={1283410: {"gameName": "", "achievements": [{"name": "A", "displayName": "X"}]}},
    )
    service = make_service(client)

    detail = await service.game_detail(STEAMID, 1283410)  # sem passar pela biblioteca

    assert detail.name == "Tails of Iron"


async def test_falha_ao_buscar_o_nome_de_loja_nao_derruba_o_detalhe():
    """A busca do título é best-effort: 429 na biblioteca degrada o nome para o
    genérico, mas o detalhe (que já tem conquistas e progresso) continua de pé.
    """
    client = FakeSteamClient(
        owned_games=SteamUnavailableError("boom"),
        achievements={1283410: [{"apiname": "A", "achieved": 1}]},
        schemas={1283410: {"gameName": "", "achievements": [{"name": "A", "displayName": "X"}]}},
    )
    service = make_service(client)

    detail = await service.game_detail(STEAMID, 1283410)

    assert detail.name == "App 1283410"  # caiu no fallback, mas não levantou
    assert detail.achieved_count == 1
    assert detail.percent == 100.0
