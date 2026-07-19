import anthropic
from anthropic import AsyncAnthropic

from app.ai.base import ClienteDeIA, sem_repetir
from app.errors import AiRateLimitError, AiUnavailableError
from app.schemas.models import Dica, Fonte


class AnthropicClient(ClienteDeIA):
    """Camada que fala HTTP com a Anthropic — espelho do `SteamClient`.

    Devolve modelo de domínio (`Dica`) ou levanta exceção tipada. Nenhuma outra
    parte do app conhece o SDK: `services/` recebe esta classe por construtor e
    `web/` não a importa.
    """

    nome = "anthropic"

    def __init__(self, sdk: AsyncAnthropic, **kwargs):
        super().__init__(**kwargs)
        self._sdk = sdk

    async def _gerar(self, prompt: str) -> Dica:
        try:
            resposta = await self._chamar(prompt)
        except anthropic.RateLimitError as exc:
            # Traduzir aqui, e não deixar subir: `services/` não conhece exceção
            # de SDK, e o `_ERROR_MAP` da rota mapeia por *tipo*. Exceção crua do
            # SDK não está no mapa e vira 500 sem `detail` — que o frontend não
            # sabe exibir.
            raise AiRateLimitError(str(exc)) from exc
        except anthropic.AnthropicError as exc:
            # Base de *todas* as falhas do SDK — inclui erro de conexão, que não
            # é `APIStatusError`. Vem depois do rate limit porque é mais larga.
            raise AiUnavailableError(str(exc)) from exc

        # TODOS os blocos, não o primeiro: com busca web a resposta vem citada, e
        # citação **quebra o texto em vários blocos**. Pegar só o primeiro entrega
        # o preâmbulo e descarta a resposta — bug pego no /verify, não pelos
        # testes, porque o fake tinha um bloco só.
        texto = "".join(b.text for b in resposta.content if b.type == "text")
        return Dica(texto=texto, fontes=sem_repetir(_fontes(resposta.content)))

    async def _chamar(self, prompt: str):
        """Só o request. Separado para o `try` acima cercar a rede e nada mais —
        `except` largo demais engoliria erro de parsing como se fosse de rede.
        """
        return await self._sdk.messages.create(
            model=self._model,
            max_tokens=1024,
            # ponytail: payload mínimo — sem `thinking` e sem `output_config.effort`
            # de propósito. Ambos erram em Haiku 4.5, e a variante de busca com
            # filtragem dinâmica (web_search_20260209) exige modelo mais novo.
            # Este shape vale em haiku-4-5 / sonnet-5 / opus-4-8, então
            # ANTHROPIC_MODEL troca por string sem branch. Teto conhecido: em
            # modelo novo, deixa filtragem dinâmica e adaptive thinking na mesa.
            #
            # `max_uses` é o multiplicador de custo mais direto aqui: a busca é
            # 61% do custo por dica, e sem teto o modelo decide quantas rodadas
            # fazer. Três cobre o caso normal (medido: 9-10 fontes por dica).
            tools=[
                {"type": "web_search_20250305", "name": "web_search", "max_uses": 3}
            ],
            messages=[{"role": "user", "content": prompt}],
        )


def _fontes(blocos) -> list[Fonte]:
    """Fontes citadas pelos blocos de resultado de busca da Anthropic."""
    fontes: list[Fonte] = []
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
            if url:
                fontes.append(Fonte(title=getattr(r, "title", "") or url, url=url))
    return fontes
