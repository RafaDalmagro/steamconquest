from datetime import datetime
from typing import Literal

from pydantic import BaseModel

# Vocabulário da biblioteca. Declarado aqui (contrato de domínio) e usado tanto na
# assinatura da rota quanto na do service — é o que faz o OpenAPI publicá-lo e o
# SPA gerar seus tipos daqui, em vez de redeclarar a união à mão.
#
# `include` é o único eixo da rota, e é o que decide o que buscar. Ordenar não é:
# a ordem sai dos campos que já vêm no payload, então quem ordena é o cliente —
# reordenar não muda o dado e não pode custar uma ida à Steam.
Include = Literal["achievements", "genres"]


class Game(BaseModel):
    """Jogo da biblioteca para exibição na index.

    `percent`/`achieved_count`/`total_count` só são preenchidos com
    `include=achievements`; `genres`, com `include=genres`. Sem `include`, a
    biblioteca custa uma única chamada à Steam e esses campos vêm vazios.
    """

    appid: int
    name: str
    playtime_minutes: int
    # Ausente na maioria: a Steam só manda `playtime_2weeks` para quem jogou nas
    # últimas duas semanas.
    playtime_2weeks_minutes: int | None = None
    # None = nunca jogado (a Steam manda `rtime_last_played` 0, não uma data).
    last_played_at: datetime | None = None
    icon_url: str | None = None
    percent: float | None = None
    achieved_count: int | None = None
    total_count: int | None = None
    genres: list[str] = []


class PlayerSummary(BaseModel):
    """Identidade pública do perfil. Nunca ecoa steamid nem dados sensíveis.

    Sem steamid **de propósito**: quem chama `/profile` já o tem no path, e um
    modelo que o carrega acaba o espalhando por componentes que não deviam
    conhecê-lo. Quem *descobre* um steamid é o `ResolvedProfile`.
    """

    personaname: str
    avatar_url: str | None = None


class ResolvedProfile(BaseModel):
    """Nome do perfil resolvido para SteamID64 (REQ-061).

    O único modelo que ecoa um steamid — descobri-lo é o serviço que a rota
    presta. Não é vazamento: o steamid já vive na URL pública `/u/{steamid}` do
    SPA. O segredo é a STEAM_API_KEY, e ela nunca sai do backend.
    """

    steamid: str


class Achievement(BaseModel):
    """Conquista no detalhe do jogo."""

    apiname: str
    display_name: str
    description: str | None = None
    icon_url: str | None = None
    achieved: bool
    # Só nas obtidas — e nem sempre: a Steam devolve unlocktime 0 em desbloqueios
    # muito antigos. Serializa como ISO-8601 UTC; quem formata é o browser.
    unlocked_at: datetime | None = None
    # % global de jogadores que obteve a conquista. None = a Steam não devolveu
    # raridade para este jogo (é decoração, não quebra o detalhe).
    global_percent: float | None = None


class GameDetail(BaseModel):
    """Detalhe de um jogo: conquistas obtidas/pendentes e progresso."""

    appid: int
    name: str
    supports_achievements: bool
    achieved_count: int
    total_count: int
    percent: float
    achievements: list[Achievement]
