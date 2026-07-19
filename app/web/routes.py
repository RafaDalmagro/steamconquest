from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, Path, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.schemas.models import (
    Dica,
    Game,
    GameDetail,
    Include,
    PlayerSummary,
    ResolvedProfile,
)
from app.services.achievements import AchievementsService
from app.errors import (
    AiRateLimitError,
    AiUnavailableError,
    DicaIndisponivel,
    SteamDataUnavailable,
    SteamProfileNotFound,
    SteamRateLimitError,
    SteamUnavailableError,
    SteamVanityNotFound,
)

router = APIRouter(prefix="/api")

# SteamID64 tem 17 dígitos. Valida no path para dar 422 em lixo antes de
# chamar a Steam (o frontend também valida, mas isto é a rede de segurança).
_STEAMID = Path(pattern=r"^\d{17}$")


# O nome do perfil é texto livre — não passa pelo funil de 17 dígitos do steamid.
# A Steam permite 2–32 chars alfanuméricos, `_` e `-`; validar aqui é o que impede
# uma string arbitrária de virar chave de cache ou chamada à Steam.
_VANITY = Query(min_length=2, max_length=32, pattern=r"^[A-Za-z0-9_-]+$")

# O `apiname` vira parte de uma chave de cache (`dica:{appid}:{apiname}`) e de um
# prompt pago. Validar a forma aqui é o que impede uma string arbitrária de
# ocupar espaço no TTLCache — que tem teto de entradas, então lixo despeja dado
# legítimo. 64 chars cobrem com folga os nomes reais da Steam ("ACH_SPA").
_APINAME = Path(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")


def get_service(request: Request) -> AchievementsService:
    return request.app.state.service


@router.get("/resolve", response_model=ResolvedProfile)
async def resolve(vanity: str = _VANITY, service=Depends(get_service)):
    """Nome do perfil (custom URL) → SteamID64.

    Existe porque o usuário não sabe o próprio SteamID64: ele tem o link ou o
    nome do perfil. Só o backend pode resolver — a chamada exige a
    STEAM_API_KEY, e o SPA nunca fala com a Steam.
    """
    return ResolvedProfile(steamid=await service.resolve_vanity(vanity))


@router.get("/users/{steamid}/profile", response_model=PlayerSummary)
async def player_profile(steamid: str = _STEAMID, service=Depends(get_service)):
    return await service.player_summary(steamid)


@router.get("/users/{steamid}/games", response_model=list[Game])
async def list_games(
    steamid: str = _STEAMID,
    # Repetível (`?include=achievements&include=genres`): é a forma nativa do
    # FastAPI, que valida o vocabulário e o publica no OpenAPI sem parser à mão.
    include: Annotated[list[Include], Query()] = [],
    service=Depends(get_service),
):
    # Valor fora do vocabulário não chega aqui: o Literal faz o FastAPI devolver
    # 422 (com o `detail` em pt-BR do handler abaixo) antes de tocar o serviço.
    return await service.list_library(steamid, include=include)


@router.get("/users/{steamid}/games/{appid}", response_model=GameDetail)
async def game_detail(appid: int, steamid: str = _STEAMID, service=Depends(get_service)):
    return await service.game_detail(steamid, appid)


@router.get(
    "/users/{steamid}/games/{appid}/achievements/{apiname}/dica",
    response_model=Dica,
)
async def dica(
    appid: int,
    apiname: str = _APINAME,
    steamid: str = _STEAMID,
    service=Depends(get_service),
):
    """Síntese de IA de como obter uma conquista pendente.

    Único endpoint do app com custo em **dinheiro** por miss. O gate (jogo na
    biblioteca + conquista pendente) e o teto de chamadas vivem no serviço; aqui
    só se valida a forma do input e se orquestra.
    """
    return await service.dica(steamid, appid, apiname)


# Mapeamento de erro tipado → HTTP + mensagem amigável (pt-BR), em JSON.
_ERROR_MAP = {
    SteamProfileNotFound: (404, "Steam ID não encontrado. Confira os 17 dígitos."),
    # Mensagem própria, e não a de cima: quem chegou por aqui digitou um *nome*.
    # Mandá-lo conferir "os 17 dígitos" é apontar para algo que ele não escreveu.
    SteamVanityNotFound: (404, "Perfil não encontrado. Confira o link ou o nome do perfil."),
    SteamDataUnavailable: (404, "Dados indisponíveis. O perfil pode estar privado."),
    SteamRateLimitError: (429, "A Steam limitou as requisições. Tente novamente em instantes."),
    SteamUnavailableError: (502, "A Steam está indisponível no momento."),
    # "NPC" é a persona sob a qual a Dica é apresentada (ver CONTEXT.md). Ela vive
    # aqui, e não só no SPA, porque o contrato do app é `{"detail": "<pt-BR>"}`
    # exibido verbatim — duplicar um mapa erro→texto no frontend só para manter
    # estas mensagens "neutras" seria pior que a persona vazar para a borda.
    #
    # A vagueza é obrigatória, não estilo: os motivos (conquista obtida, jogo fora
    # da biblioteca, apiname inexistente) são indistinguíveis de fora. Detalhar
    # diria a quem sonda a API o que há na biblioteca de outra pessoa (SEC-111).
    DicaIndisponivel: (404, "O NPC não tem o que dizer sobre esta conquista."),
    AiRateLimitError: (429, "O NPC está sobrecarregado. Tente de novo em instantes."),
    AiUnavailableError: (502, "O NPC não respondeu. Tente mais tarde."),
}


def register_error_handlers(app: FastAPI) -> None:
    async def handle(request: Request, exc: Exception):
        status, message = _ERROR_MAP[type(exc)]
        return JSONResponse({"detail": message}, status_code=status)

    for exc_type in _ERROR_MAP:
        app.add_exception_handler(exc_type, handle)

    # O 422 padrão do FastAPI traz `detail` como array de erros de validação, que
    # o frontend não sabe exibir. Aqui ele passa a falar o mesmo contrato dos
    # demais erros — {"detail": "<pt-BR>"} — para steamid, appid e include.
    async def handle_validation(request: Request, exc: Exception):
        return JSONResponse(
            {"detail": "Parâmetro inválido na URL. Confira o endereço e tente de novo."},
            status_code=422,
        )

    app.add_exception_handler(RequestValidationError, handle_validation)
