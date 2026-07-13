from datetime import datetime

from pydantic import BaseModel


class Game(BaseModel):
    """Jogo da biblioteca para exibição na index.

    `percent`/`achieved_count`/`total_count` só são preenchidos quando a
    ordenação exige conquistas (sort=percent/ach_count). `genres` só é
    preenchido quando `group=genre`.
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
    """Identidade pública do perfil. Nunca ecoa steamid nem dados sensíveis."""

    personaname: str
    avatar_url: str | None = None


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
