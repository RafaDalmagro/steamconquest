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


class AiError(Exception):
    """Base comum das falhas do provedor de IA.

    Hierarquia própria, separada de `SteamError`: são fornecedores diferentes,
    com regimes de custo diferentes. Falha da Steam gasta cota; falha da IA gasta
    dinheiro — e nenhum `except` best-effort deve varrer as duas juntas por
    descuido.
    """


class AiRateLimitError(AiError):
    """Teto local de chamadas pagas atingido, ou 429 do provedor."""


class AiUnavailableError(AiError):
    """Provedor de IA indisponível ou falhou (5xx, rede, resposta inutilizável)."""


class DicaSemOrcamento(AiError):
    """Orçamento diário de chamadas pagas esgotado.

    Irmã de `AiRateLimitError`, não filha: as duas viram 429, mas dizem coisas
    diferentes ao usuário. "Tente em instantes" é verdade para rajada e mentira
    para orçamento — este só volta amanhã.
    """


class DicaIndisponivel(Exception):
    """Não há dica a gerar para esta conquista — e não se paga para descobrir.

    Um tipo só para todos os motivos (conquista obtida, fora da biblioteca,
    inexistente, sem `name_en`) porque o `_ERROR_MAP` mapeia *tipo* → mensagem:
    tipos distintos renderiam mensagens distintas, e mensagens distintas contam a
    quem sondar a API se um jogo está ou não na biblioteca de alguém. Uma
    mensagem genérica não vaza nada e é menos código.

    Fora da hierarquia `SteamError` de propósito: a falha não é da Steam, e
    varrê-la num `except SteamError` best-effort seria errado — aqui a ausência é
    a resposta, não um contratempo a engolir.
    """


class SteamUnavailableError(SteamError):
    """Steam indisponível (5xx / falha de rede) após esgotar o retry."""
