import asyncio
from collections.abc import Collection
from datetime import UTC, datetime
from typing import Any, Callable, NamedTuple

from app.core.cache import TTLCache
from app.errors import (
    DicaIndisponivel,
    SteamDataUnavailable,
    SteamError,
    SteamProfileNotFound,
    SteamVanityNotFound,
)
from app.schemas.models import (
    Achievement,
    Game,
    GameDetail,
    Include,
    PlayerSummary,
)

_ICON_URL = (
    "https://media.steampowered.com/steamcommunity/public/images/apps/{appid}/{hash}.jpg"
)

# TTLs por natureza do dado (segundos). Ver spec REQ-010/CON-010.
OWNED_TTL = 300
ACH_TTL = 300
PROFILE_TTL = 300
# Mapeamento nome→steamid: muda com a mesma raridade de um perfil, então segue o
# TTL do perfil — literalmente, para não divergirem por descuido.
VANITY_TTL = PROFILE_TTL
# TTL curto para o "não existe": erra pouco se um perfil novo aparecer, e já
# absorve a rajada de quem marreta o mesmo ID inválido.
NOT_FOUND_TTL = 60
SCHEMA_TTL = 86_400
# {} do schema inglês é sempre falha transitória (jogo sem schema já cai no
# branch sem conquistas). TTL curto para não deixar o link "Como conseguir"
# sumido por um dia inteiro por causa de um 429 de dez segundos.
SCHEMA_EN_MISS_TTL = 3_600
# Raridade é por *jogo*, não por jogador: a chave é o appid, então o cache é
# compartilhado por todos os visitantes. O número anda devagar — 24h basta.
GLOBAL_PCT_TTL = 86_400
# {} pode ser jogo sem stats globais (permanente) ou falha transitória. Não dá
# para distinguir, então TTL curto: retenta em ~1h em vez de cachear o vazio por
# um dia inteiro.
GLOBAL_PCT_MISS_TTL = 3_600
# Como obter uma conquista não muda: o método é estático como o gênero. TTL longo
# porque cada miss custa *dinheiro*, não só cota — é o único dado pago do app.
DICA_TTL = 604_800  # 7 dias
GENRES_TTL = 604_800  # 7 dias: gênero encontrado é estático
# [] pode ser 429 transitório da loja, não ausência real de gênero. TTL curto:
# não re-martela a loja a cada load (o que perpetuaria o rate limit), mas
# retenta em ~1h para se recuperar sozinho.
GENRES_MISS_TTL = 3_600

# Sentinela de cache negativo: distingue "não existe" (cacheado) de "não está no
# cache" (None), sem precisar guardar a exceção.
_NAO_EXISTE = object()


class Progresso(NamedTuple):
    """Uma conquista do jogador, normalizada: `achieved` é bool, não o `0/1` da Steam.

    É o que entra no cache — e pesa menos que o dict cru.
    """

    apiname: str
    achieved: bool
    unlocktime: int | None


class AchievementsService:
    """Regra de negócio: monta biblioteca e detalhe a partir do client Steam.

    Não conhece FastAPI nem httpx — depende apenas da interface do client, o que
    o torna testável com um client falso (sem rede).
    """

    def __init__(self, client, cache: TTLCache, concurrency: int = 5, ai=None):
        self._client = client
        self._cache = cache
        self._concurrency = concurrency
        # Sem default defensivo: o lifespan sempre injeta. Se `dica()` for
        # chamada com `ai=None`, é bug de wiring e tem de estourar alto — não
        # virar um caminho degradado silencioso.
        self._ai = ai

    async def list_library(
        self,
        steamid: str,
        include: Collection[Include] = (),
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
                playtime_2weeks_minutes=g.get("playtime_2weeks"),
                last_played_at=_epoch(g.get("rtime_last_played")),
                icon_url=(
                    _ICON_URL.format(appid=g["appid"], hash=g["img_icon_url"])
                    if g.get("img_icon_url")
                    else None
                ),
            )
            for g in raw
        ]
        # O caller declara os dados caros que quer — nada aqui os deduz. Sem
        # `include`, a biblioteca custa uma única chamada à Steam.
        #
        # Os dois fan-outs são independentes e batem em hosts diferentes (Web API ×
        # loja), cada um com seu Semaphore: em paralelo, pedir os dois custa o mais
        # lento, não a soma.
        trabalhos = []
        if "achievements" in include:
            trabalhos.append(self._fill_counts(steamid, games))
        if "genres" in include:
            trabalhos.append(self._fill_genres(games))
        if trabalhos:
            await asyncio.gather(*trabalhos)
        # Sai na ordem que a Steam devolveu: ordenar é trabalho do cliente, que já
        # tem todos os campos em mãos e não precisa de uma requisição para reordenar.
        return games

    async def resolve_vanity(self, nome: str) -> str:
        """Nome do perfil (custom URL) → SteamID64.

        TTL curto no "não" (e não longo) porque um nome livre hoje **pode ser
        registrado amanhã** — ao contrário de um appid, que é imutável.
        """
        return await self._cached_ou_ausente(
            f"vanity:{nome}",
            VANITY_TTL,
            lambda: self._client.resolve_vanity_url(nome),
            SteamVanityNotFound,
        )

    async def player_summary(self, steamid: str) -> PlayerSummary:
        async def buscar() -> PlayerSummary:
            raw = await self._client.get_player_summary(steamid)
            return PlayerSummary(
                personaname=raw.get("personaname", ""),
                avatar_url=raw.get("avatarfull") or None,
            )

        return await self._cached_ou_ausente(
            f"player_summary:{steamid}",
            PROFILE_TTL,
            buscar,
            SteamProfileNotFound,
        )

    async def game_detail(self, steamid: str, appid: int) -> GameDetail:
        try:
            player = await self._player_achievements(steamid, appid)
        except SteamDataUnavailable:
            # Mesma ambiguidade da biblioteca: só o perfil desempata conta
            # inexistente de conta privada. Pago só no caminho de erro.
            await self._assert_exists(steamid)
            raise
        if not player:
            # Jogo sem conquistas não paga a chamada de raridade: não haveria
            # onde exibi-la.
            schema = await self._schema(appid)
            return GameDetail(
                appid=appid,
                name=self._name(schema, steamid, appid),
                supports_achievements=False,
                achieved_count=0,
                total_count=0,
                percent=0.0,
                achievements=[],
            )

        # Independentes entre si: em paralelo o cold-start do detalhe custa uma
        # ida à Steam, não duas.
        schema, schema_en, raridade, _ = await asyncio.gather(
            self._schema(appid),
            self._schema_en(appid),
            self._global_percentages(appid),
            # Semeia owned_games: para o `_name` achar o nome de *loja* mesmo em
            # deep-link/cache frio. No gather, não custa latência de parede; quem
            # veio da biblioteca lê do cache e nem chama.
            self._ensure_library(steamid),
        )
        name = self._name(schema, steamid, appid)

        meta = {a["name"]: a for a in schema.get("achievements", [])}
        meta_en = {a["name"]: a for a in schema_en.get("achievements", [])}
        achievements: list[Achievement] = []
        achieved_count = 0
        for entry in player:
            if entry.achieved:
                achieved_count += 1
            m = meta.get(entry.apiname, {})
            achievements.append(
                Achievement(
                    apiname=entry.apiname,
                    display_name=m.get("displayName") or entry.apiname,
                    # Sem fallback para `apiname` — ao contrário do display_name
                    # acima. Ali o fallback existe para *mostrar* algo; aqui,
                    # para *buscar*, e buscar "ACH_SPA" não acha nada. Link
                    # ausente é honesto; link que não acha nada é ruído.
                    name_en=meta_en.get(entry.apiname, {}).get("displayName"),
                    description=m.get("description"),
                    icon_url=m.get("icon") if entry.achieved else m.get("icongray"),
                    achieved=entry.achieved,
                    unlocked_at=_epoch(entry.unlocktime) if entry.achieved else None,
                    global_percent=raridade.get(entry.apiname),
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

    async def dica(self, steamid: str, appid: int, apiname: str):
        """Síntese de IA sobre como obter uma conquista pendente.

        Espelha `game_detail(steamid, appid)`: recebe identificadores da URL e
        resolve tudo internamente, para a rota só orquestrar.
        """
        # Gate mais externo: o jogo é *desta* biblioteca? Vem primeiro porque é o
        # único que limita o espaço de `appid` — sem ele, todo gate abaixo já
        # teria pago uma ida à Steam para descobrir que a resposta é não.
        owned = await self._owned_games(steamid)
        jogo = next((g for g in owned if g["appid"] == appid), None)
        if jogo is None:
            raise DicaIndisponivel(f"jogo {appid} fora da biblioteca de {steamid}")

        # O estado da conquista vem *antes* do schema: `_schema_en()` pode
        # disparar uma chamada à Steam, e `appid` é input público. Barrar primeiro
        # mantém quem sonda longe de qualquer I/O — de graça, porque esta entrada
        # de cache já foi paga para renderizar o detalhe.
        player = await self._player_achievements(steamid, appid)
        entry = next((p for p in player or [] if p.apiname == apiname), None)
        if entry is not None and entry.achieved:
            raise DicaIndisponivel(f"conquista {apiname} já obtida")

        schema_en = await self._schema_en(appid)
        meta_en = {a["name"]: a for a in schema_en.get("achievements", [])}
        name_en = meta_en.get(apiname, {}).get("displayName")
        if name_en is None:
            # Mesma regra do link "Como conseguir" (REQ-094): sem nome buscável
            # não há pergunta a fazer. Aqui pesa mais — ali o custo era um link
            # inútil, aqui seria uma chamada paga sem chance de acertar.
            raise DicaIndisponivel(f"conquista {apiname} sem nome em inglês")

        # O nome vem do `GetOwnedGames` — nome de *loja*, já em inglês ("Nioh:
        # Complete Edition"). O `gameName` do schema é o interno do estúdio
        # ("GFREMP2") e envenenaria a busca. Aqui não há fallback: o gate acima
        # garante que o jogo está na biblioteca, então o nome existe.
        #
        # `_cached()` e não `_cached_ou_ausente()`: aqui erro é erro. Cachear um
        # 429 transitório da Anthropic congelaria o painel quebrado por 7 dias.
        # Chave sem `steamid` de propósito — a Dica é função de (jogo, conquista),
        # então o primeiro visitante paga e todos os outros leem (CON-111).
        return await self._cached(
            f"dica:{appid}:{apiname}",
            DICA_TTL,
            lambda: self._ai.sintetizar(jogo["name"], name_en),
        )

    def _name(self, schema: dict, steamid: str, appid: int) -> str:
        """Nome do jogo, da fonte mais confiável para a menos.

        A biblioteca vem primeiro porque traz o nome da **loja** — o que o
        usuário reconhece. O `game_detail` garante que ela esteja em cache antes
        de chamar aqui (`_ensure_library`), então o deep-link também acha o nome.
        O `gameName` do schema é plano B só para jogo fora da biblioteca
        (delistado): é o nome interno do estúdio, às vezes um codinome
        ("GFREMP2" para Remnant II). `App {appid}` é o último recurso.
        """
        owned = self._cache.get(f"owned_games:{steamid}") or []
        nome = next((g["name"] for g in owned if g["appid"] == appid), "")
        return nome or schema.get("gameName") or f"App {appid}"

    async def _assert_exists(self, steamid: str) -> None:
        """Levanta SteamProfileNotFound se a conta não existe; volta calado se existe."""
        await self.player_summary(steamid)

    async def _cached_ou_ausente(
        self,
        key: str,
        ttl: int,
        fetch,
        ausente: type[SteamError],
    ):
        """Como `_cached()`, mas o "não existe" também é cacheado.

        Irmão do `_cached()` e não um parâmetro dele: aqui o *erro* é resposta e
        vira valor no cache (a sentinela `_NAO_EXISTE`), o que o `_cached()` não
        sabe fazer — para ele, erro propaga e nada é guardado.

        Existe porque perfil e nome de perfil vêm de **input público**: sem cachear
        o "não", marretar o mesmo ID/nome inexistente queima a quota da chave a
        cada tentativa.
        """
        cached = self._cache.get(key)
        if cached is _NAO_EXISTE:
            raise ausente("não encontrado")
        if cached is not None:
            return cached
        try:
            value = await fetch()
        except ausente:
            self._cache.set(key, _NAO_EXISTE, NOT_FOUND_TTL)
            raise
        self._cache.set(key, value, ttl)
        return value

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

    async def _ensure_library(self, steamid: str) -> None:
        """Best-effort: garante owned_games: em cache para o `_name`.

        Nome errado no título (e na busca de vídeo que o usa) é ruim, mas não
        pode derrubar um detalhe que já tem tudo — mesma postura da raridade.
        Falhou → `_name` cai no fallback antigo (`App {appid}`).
        """
        try:
            await self._owned_games(steamid)
        except SteamError:
            pass

    async def _fill_counts(self, steamid: str, games: list[Game]) -> None:
        sem = asyncio.Semaphore(self._concurrency)

        async def fill(game: Game) -> None:
            async with sem:
                try:
                    achievements = await self._player_achievements(steamid, game.appid)
                except SteamError:
                    return  # best-effort: um jogo que falha fica sem %, não quebra a página
            if not achievements:
                return  # jogo sem conquistas segue sem %, sem 0/0 na tela
            game.achieved_count = sum(1 for a in achievements if a.achieved)
            game.total_count = len(achievements)
            game.percent = _percent(game.achieved_count, game.total_count)

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

    async def _player_achievements(self, steamid: str, appid: int) -> list[Progresso]:
        """Progresso do jogador no jogo. `[]` = jogo sem conquistas.

        Único ponto que busca `GetPlayerAchievements`: a contagem da biblioteca e a
        lista do detalhe são duas leituras deste cache, não duas idas à Steam.

        Conquista sem `apiname` é descartada: sem nome não há como casar com o
        schema nem com a raridade, e o `KeyError` derrubaria o fan-out inteiro (que
        só engole `SteamError`).

        `[]` em vez de `None` porque `None` é o sinal de miss do `_cached()`:
        devolvê-lo faria "este jogo não tem conquistas" nunca ser cacheado, e cada
        load com `include=achievements` re-consultaria a Steam para *todos* esses
        jogos. Mesmo cache negativo já usado em `genres` e `global_pct`.
        """

        async def buscar() -> list[Progresso]:
            entries = await self._client.get_player_achievements(steamid, appid) or []
            return [
                Progresso(
                    apiname=e["apiname"],
                    achieved=e.get("achieved") == 1,
                    unlocktime=e.get("unlocktime"),
                )
                for e in entries
                if e.get("apiname")
            ]

        return await self._cached(f"player_ach:{steamid}:{appid}", ACH_TTL, buscar)

    async def _global_percentages(self, appid: int) -> dict[str, float]:
        """Raridade por `apiname`. Best-effort: falha vira {}, nunca propaga.

        Jogo sem stats globais devolve 403 (⇒ `SteamDataUnavailable`), e um 429
        ou 5xx aqui não pode derrubar um detalhe que já tem tudo que importa. A
        raridade é decoração — mesma postura do fan-out em `_fill_counts`.
        """

        async def buscar() -> dict[str, float]:
            try:
                return await self._client.get_global_achievement_percentages(appid)
            except SteamError:
                return {}

        return await self._cached(
            f"global_pct:{appid}",
            lambda pct: GLOBAL_PCT_TTL if pct else GLOBAL_PCT_MISS_TTL,
            buscar,
        )

    async def _schema(self, appid: int) -> dict:
        return await self._cached(
            f"schema:{appid}", SCHEMA_TTL, lambda: self._client.get_schema(appid)
        )

    async def _schema_en(self, appid: int) -> dict:
        """Schema em inglês — só o `name_en`. Chave por *jogo*, compartilhada.

        Irmão do `_schema()`, e não um parâmetro dele: são duas entradas de cache
        distintas, e só esta é best-effort.

        Best-effort como a raridade, e pelo mesmo motivo: `name_en` é decoração —
        sem ele o link "Como conseguir" some, mas o detalhe tem tudo que importa.
        O `{}` é cacheado com TTL curto (e não devolvido fora do cache) para que
        uma Steam em 429 não leve uma re-tentativa por request.
        """

        async def buscar() -> dict:
            try:
                return await self._client.get_schema(appid, "english")
            except SteamError:
                return {}

        return await self._cached(
            f"schema_en:{appid}",
            lambda s: SCHEMA_TTL if s else SCHEMA_EN_MISS_TTL,
            buscar,
        )


def _epoch(ts: int | None) -> datetime | None:
    """Epoch da Steam → datetime UTC. `0` significa "sem data", não 1970.

    Vale para `unlocktime` (conquista antiga demais) e `rtime_last_played`
    (nunca jogado): a Steam usa `0` como ausência nos dois.
    """
    return datetime.fromtimestamp(ts, UTC) if ts else None


def _percent(achieved: int, total: int) -> float:
    return achieved / total * 100 if total else 0.0


