"""Falhas tipadas de domínio ao obter dados da Steam.

Vivem no domínio (não em `steam/`) para que tanto a infra que as levanta quanto
a web que as mapeia dependam do domínio — nunca a web da infra.
"""


class SteamError(Exception):
    """Base comum: permite tratar qualquer falha da Steam num só `except`
    (usado no fan-out best-effort, onde um jogo que falha não pode quebrar a
    página inteira)."""


class SteamDataUnavailable(SteamError):
    """Dado indisponível: perfil privado ou key inválida (401/403)."""


class SteamRateLimitError(SteamError):
    """Rate limit da Steam (429) após esgotar o retry."""


class SteamUnavailableError(SteamError):
    """Steam indisponível (5xx / falha de rede) após esgotar o retry."""
