from google.genai import Client, errors, types

from app.ai.base import ClienteDeIA, sem_repetir
from app.errors import AiRateLimitError, AiUnavailableError
from app.schemas.models import Dica, Fonte


class GeminiClient(ClienteDeIA):
    """Camada que fala HTTP com a Gemini Developer API.

    Irmã do `AnthropicClient`, não filha: o que compartilham (bucket, prompt,
    contrato de erro) mora na base. Aqui fica só o que é do fornecedor — como a
    busca é declarada e como as fontes voltam.
    """

    nome = "gemini"

    def __init__(self, sdk: Client, **kwargs):
        super().__init__(**kwargs)
        self._sdk = sdk

    async def _gerar(self, prompt: str) -> Dica:
        try:
            resposta = await self._chamar(prompt)
        except errors.APIError as exc:
            # O SDK não tem exceção dedicada para rate limit — `ClientError`
            # cobre todo 4xx —, então o desempate é pelo código. Sem isso um 429
            # viraria 502 e a mensagem mandaria "tente mais tarde" quando o certo
            # é "tente em instantes".
            if getattr(exc, "code", None) == 429:
                raise AiRateLimitError(str(exc)) from exc
            raise AiUnavailableError(str(exc)) from exc

        return Dica(texto=resposta.text or "", fontes=sem_repetir(_fontes(resposta)))

    async def _chamar(self, prompt: str):
        """Só o request — o `try` acima cerca a rede, e nada mais."""
        return await self._sdk.aio.models.generate_content(
            model=self._model,
            contents=prompt,
            # Equivalente funcional do `web_search` da Anthropic. Aqui não há
            # parâmetro de teto de rodadas: nos modelos 3.x a cobrança é por
            # busca executada, e quem segura o volume é o orçamento diário.
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())]
            ),
        )


def _fontes(resposta) -> list[Fonte]:
    """Fontes do `grounding_metadata`, que é onde o Gemini devolve as citações."""
    fontes: list[Fonte] = []
    for candidato in resposta.candidates or []:
        meta = getattr(candidato, "grounding_metadata", None)
        # Resposta sem grounding é possível (o modelo pode decidir não buscar).
        # Dica sem fonte é pior que com, e muito melhor que um erro.
        if meta is None:
            continue
        for chunk in meta.grounding_chunks or []:
            web = getattr(chunk, "web", None)
            if web is None or not web.uri:
                continue
            fontes.append(Fonte(title=web.title or web.uri, url=web.uri))
    return fontes
