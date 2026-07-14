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


class SteamProfileNotFound(SteamError):
    """A conta não existe: SteamID bem formado, mas sem perfil na Steam.

    Irmã de `SteamDataUnavailable`, não filha: "não existe" e "existe mas está
    privado" são causas diferentes e rendem mensagens diferentes ao usuário.
    """


class SteamVanityNotFound(SteamError):
    """O nome do perfil (custom URL) não existe na Steam.

    Irmã de `SteamProfileNotFound`, não filha: as duas dizem "não existe", mas
    para entradas diferentes — e a mensagem ao usuário precisa falar da entrada
    que ele *de fato* digitou. Mandar quem escreveu um nome "conferir os 17
    dígitos" é instruí-lo a corrigir algo que ele não digitou.
    """


class SteamRateLimitError(SteamError):
    """Rate limit da Steam (429) após esgotar o retry."""


class SteamUnavailableError(SteamError):
    """Steam indisponível (5xx / falha de rede) após esgotar o retry."""
