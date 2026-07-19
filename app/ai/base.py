import time
from abc import ABC, abstractmethod
from typing import Callable

from app.core.rate_limit import TokenBucket
from app.errors import AiRateLimitError
from app.schemas.models import Dica, Fonte


def montar_prompt(nome_do_jogo: str, name_en: str) -> str:
    """Os dois únicos insumos: o jogo e o nome da conquista em inglês.

    Nada do jogador entra aqui — nem `steamid`, nem progresso, nem playtime. É o
    que torna a Dica função de (jogo, conquista) e permite o cache compartilhado
    (CON-111). A assinatura desta função é a garantia estrutural do AC-118.

    **Idêntico entre provedores, de propósito** (CON-132): o que muda de um para
    outro é como a busca web é declarada e como as fontes voltam, nunca o que se
    pede ao modelo. Prompt afinado por provedor faria a comparação de qualidade
    comparar *prompts* em vez de provedores — e a conclusão não serviria para
    decidir qual manter.
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


def sem_repetir(fontes: list[Fonte]) -> list[Fonte]:
    """Remove URL repetida preservando a ordem — a primeira é a mais relevante.

    Todo provedor repete: o guia 100% casa com várias queries e volta em mais de
    um resultado. `dict` e não `set` porque a ordem importa.
    """
    vistas: dict[str, Fonte] = {}
    for f in fontes:
        if f.url and f.url not in vistas:
            vistas[f.url] = f
    return list(vistas.values())


class ClienteDeIA(ABC):
    """Contrato que o serviço enxerga: um provedor de síntese, qualquer que seja.

    O que é **igual** em todo provedor mora aqui — teto de rajada, prompt e
    contrato de erro. O que muda de verdade (declarar a busca web e ler as fontes
    de volta) é o único método abstrato.

    Sem esta base, cada provedor duplicaria o token bucket e a ordem "consome
    antes de chamar" — que é justamente onde um erro custa dinheiro.
    """

    #: Identifica o provedor na chave de cache (REQ-134). Fica no cliente, e não
    #: no serviço, para `services/` continuar sem saber que existe configuração
    #: de provedor — ele pergunta ao cliente o que o cliente é.
    nome: str

    def __init__(
        self,
        *,
        model: str,
        rate_per_minute: float,
        rate_burst: int,
        now: Callable[[], float] = time.monotonic,
    ):
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
        dica = await self._gerar(montar_prompt(nome_do_jogo, name_en))
        # Carimbado aqui, e não em cada implementação: um provedor novo não pode
        # entrar no app esquecendo de se identificar.
        return dica.model_copy(update={"provedor": self.nome})

    @abstractmethod
    async def _gerar(self, prompt: str) -> Dica:
        """Chama o provedor com busca web e devolve texto + fontes citadas.

        Deve traduzir as exceções do SDK para `AiRateLimitError` /
        `AiUnavailableError` (REQ-136). Deixar exceção de SDK escapar vira 500
        sem `detail`, e o frontend não tem o que exibir.
        """
