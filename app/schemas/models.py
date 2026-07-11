from pydantic import BaseModel


class Game(BaseModel):
    """Jogo da biblioteca para exibição na index.

    `percent`/`achieved_count`/`total_count` só são preenchidos quando a
    ordenação exige conquistas (sort=percent/ach_count).
    """

    appid: int
    name: str
    playtime_minutes: int
    icon_url: str | None = None
    percent: float | None = None
    achieved_count: int | None = None
    total_count: int | None = None


class Achievement(BaseModel):
    """Conquista no detalhe do jogo."""

    apiname: str
    display_name: str
    description: str | None = None
    icon_url: str | None = None
    achieved: bool


class GameDetail(BaseModel):
    """Detalhe de um jogo: conquistas obtidas/pendentes e progresso."""

    appid: int
    name: str
    supports_achievements: bool
    achieved_count: int
    total_count: int
    percent: float
    achievements: list[Achievement]
