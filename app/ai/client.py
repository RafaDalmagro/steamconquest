import time
from typing import Callable

from anthropic import AsyncAnthropic

from app.core.rate_limit import TokenBucket
from app.errors import AiRateLimitError
from app.schemas.models import Dica, Fonte


def _fontes(blocos) -> list[Fonte]:
    """Fontes citadas, na ordem em que a busca as trouxe e sem repetição.

    O guia 100% costuma casar com várias queries, então a mesma URL volta em mais
    de um bloco de resultado — exibi-la duas vezes é ruído. `dict` em vez de
    `set` porque a ordem importa: o primeiro resultado é o mais relevante.
    """
    vistas: dict[str, Fonte] = {}
    for bloco in blocos:
        if bloco.type != "web_search_tool_result":
            continue
        # Contrato da ferramenta: no sucesso `content` é *lista* de resultados;
        # no erro é um *objeto* com `error_code`. Iterar sem checar quebraria o
        # detalhe numa falha de busca — que não deveria custar a resposta.
        conteudo = bloco.content
        if not isinstance(conteudo, list):
            continue
        for r in conteudo:
            url = getattr(r, "url", None)
            if url and url not in vistas:
                vistas[url] = Fonte(title=getattr(r, "title", "") or url, url=url)
    return list(vistas.values())


def _prompt(nome_do_jogo: str, name_en: str) -> str:
    """Os dois únicos insumos: o jogo e o nome da conquista em inglês.

    Nada do jogador entra aqui — nem `steamid`, nem progresso, nem playtime. É o
    que torna a Dica função de (jogo, conquista) e permite o cache compartilhado
    (CON-111). A assinatura desta função é a garantia estrutural do AC-118.
    """
    return (
        f"Busque na web e explique, em português do Brasil, como obter a conquista "
        f'"{name_en}" do jogo "{nome_do_jogo}" no Steam.\n\n'
        "Escreva no máximo 10 linhas, em passos práticos numerados.\n"
        # Texto puro, não Markdown: o painel renderiza a string como está, então
        # `**negrito**` e `## título` aparecem crus na tela. Pedir texto puro é
        # mais barato que embarcar um renderizador de Markdown por causa disso.
        "Use texto puro, sem marcação Markdown: nada de asteriscos para negrito, "
        "nada de # para títulos, nada de hífens para listas.\n"
        "Não escreva preâmbulo — comece direto pelo primeiro passo.\n"
        "Se não encontrar material confiável sobre esta conquista específica, "
        "diga isso claramente em vez de supor."
    )


class AiClient:
    """Única camada que fala HTTP com a Anthropic — espelho do `SteamClient`.

    Devolve modelo de domínio (`Dica`) ou levanta exceção tipada. Nenhuma outra
    parte do app conhece o SDK: `services/` recebe esta classe por construtor e
    `web/` não a importa.
    """

    def __init__(
        self,
        sdk: AsyncAnthropic,
        *,
        model: str,
        rate_per_minute: float,
        rate_burst: int,
        now: Callable[[], float] = time.monotonic,
    ):
        self._sdk = sdk
        self._model = model
        # Bucket próprio, separado do da Steam: aqui o que se protege não é cota,
        # é fatura. `appid`/`apiname` vêm da URL, então sem teto qualquer um
        # converte input público em gasto (SEC-111).
        self._bucket = TokenBucket(rate_per_minute, rate_burst, now)

    async def sintetizar(self, nome_do_jogo: str, name_en: str) -> Dica:
        # Antes do request, não depois: se o teto fosse checado na volta, o
        # dinheiro já teria saído quando a exceção subisse.
        if not self._bucket.consume():
            raise AiRateLimitError("teto local de chamadas pagas atingido")

        resposta = await self._sdk.messages.create(
            model=self._model,
            max_tokens=1024,
            # ponytail: payload mínimo — sem `thinking` e sem `output_config.effort`
            # de propósito. Ambos erram em Haiku 4.5, e a variante de busca com
            # filtragem dinâmica (web_search_20260209) exige modelo mais novo.
            # Este shape vale em haiku-4-5 / sonnet-5 / opus-4-8, então AI_MODEL
            # troca por string sem branch. Teto conhecido: em modelo novo, deixa
            # filtragem dinâmica e adaptive thinking na mesa. Upgrade quando
            # AI_MODEL apontar para um modelo novo de forma permanente.
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": _prompt(nome_do_jogo, name_en)}],
        )
        # TODOS os blocos, não o primeiro: com busca web a resposta vem citada, e
        # citação **quebra o texto em vários blocos**. Pegar só o primeiro entrega
        # o preâmbulo e descarta a resposta — bug pego no /verify, não pelos
        # testes, porque o fake tinha um bloco só.
        texto = "".join(b.text for b in resposta.content if b.type == "text")
        return Dica(texto=texto, fontes=_fontes(resposta.content))
