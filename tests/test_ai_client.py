"""Testes da única camada que fala HTTP com a Anthropic.

O fake é `httpx.MockTransport`, o mesmo padrão de `test_client.py`: a Anthropic é
boundary externo real, então substituí-la no limite HTTP é legítimo — e permite
assertar sobre o **corpo que sai pela rede**, que é onde moram os requisitos de
custo (payload mínimo) e de privacidade (nada do jogador no prompt).

Nenhum teste aqui toca a rede. Um teste que gasta dinheiro ao rodar é defeito.
"""

import json

import httpx
import pytest
from anthropic import AsyncAnthropic

from app.ai.anthropic_client import AnthropicClient
from app.errors import AiRateLimitError, AiUnavailableError


def make_ai(handler, *, rate_per_minute=600.0, rate_burst=10, model="claude-haiku-4-5"):
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    sdk = AsyncAnthropic(api_key="KEY-DE-TESTE", http_client=http)
    client = AnthropicClient(
        sdk,
        model=model,
        rate_per_minute=rate_per_minute,
        rate_burst=rate_burst,
    )
    return client, http


def resposta_ok(texto="Use a fonte termal."):
    """Corpo mínimo de /v1/messages que o cliente precisa saber ler."""
    return {
        "id": "msg_1",
        "type": "message",
        "role": "assistant",
        "model": "claude-haiku-4-5",
        "content": [{"type": "text", "text": texto}],
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 10, "output_tokens": 5},
    }


async def test_teto_local_barra_antes_de_qualquer_chamada_paga():
    """AC-116 — estourou o bucket, nem sai da máquina.

    `burst=1` deixa passar exatamente uma. A asserção que importa é
    `len(chamadas) == 1`: se o bucket fosse consultado *depois* do request, o
    dinheiro já teria sido gasto quando a exceção subisse.
    """
    chamadas = []

    def handler(request):
        chamadas.append(request)
        return httpx.Response(200, json=resposta_ok())

    client, http = make_ai(handler, rate_per_minute=0.0, rate_burst=1)
    try:
        await client.sintetizar("Nioh: Complete Edition", "Spa Healer")
        with pytest.raises(AiRateLimitError):
            await client.sintetizar("Nioh: Complete Edition", "Spa Healer")
    finally:
        await http.aclose()

    assert len(chamadas) == 1


async def test_payload_minimo_e_valido_em_qualquer_modelo_configuravel():
    """AC-119/CON-113 — sem `thinking`, sem `effort`, busca básica.

    Esse shape é aceito por haiku-4-5, sonnet-5 e opus-4-8 igualmente, e é o que
    permite `AI_MODEL` ser trocado por env sem branch nenhum no código. As
    asserções negativas são as que importam: `effort` **erra com 400** em Haiku
    4.5, e `thinking: adaptive` não existe naquela geração — mandar qualquer um
    dos dois transformaria a troca de modelo numa quebra em produção.
    """
    corpos = []

    def handler(request):
        corpos.append(json.loads(request.content))
        return httpx.Response(200, json=resposta_ok())

    client, http = make_ai(handler)
    try:
        await client.sintetizar("Nioh: Complete Edition", "Spa Healer")
    finally:
        await http.aclose()

    corpo = corpos[0]
    assert corpo["model"] == "claude-haiku-4-5"
    assert "thinking" not in corpo
    assert "output_config" not in corpo
    # A busca web é o que torna isso uma chamada só, em vez de um pipeline de
    # retrieval próprio (§7 da spec).
    assert [t["type"] for t in corpo["tools"]] == ["web_search_20250305"]


async def test_fontes_saem_dos_resultados_de_busca_sem_repetir():
    """A Fonte é o que separa "a IA resumiu um guia" de "a IA afirmou algo".

    Sem ela, uma alucinação e um fato têm a mesma aparência na tela. A mesma URL
    aparecendo em duas buscas é o caso comum (o guia 100% casa com várias
    queries) — repeti-la na UI é ruído.
    """
    def handler(request):
        return httpx.Response(
            200,
            json={
                **resposta_ok(),
                "content": [
                    {
                        "type": "web_search_tool_result",
                        "tool_use_id": "srvtoolu_1",
                        "content": [
                            {
                                "type": "web_search_result",
                                "title": "Nioh 100% Achievement Guide",
                                "url": "https://exemplo/guia",
                            }
                        ],
                    },
                    {
                        "type": "web_search_tool_result",
                        "tool_use_id": "srvtoolu_2",
                        "content": [
                            {
                                "type": "web_search_result",
                                "title": "Nioh 100% Achievement Guide",
                                "url": "https://exemplo/guia",
                            },
                            {
                                "type": "web_search_result",
                                "title": "Spa Healer — vídeo",
                                "url": "https://exemplo/video",
                            },
                        ],
                    },
                    {"type": "text", "text": "Use a fonte termal."},
                ],
            },
        )

    client, http = make_ai(handler)
    try:
        dica = await client.sintetizar("Nioh: Complete Edition", "Spa Healer")
    finally:
        await http.aclose()

    assert dica.texto == "Use a fonte termal."
    assert [(f.title, f.url) for f in dica.fontes] == [
        ("Nioh 100% Achievement Guide", "https://exemplo/guia"),
        ("Spa Healer — vídeo", "https://exemplo/video"),
    ]


async def test_busca_que_falha_nao_derruba_a_dica():
    """Guard-rail do contrato da ferramenta: `content` é lista no sucesso e
    *objeto* no erro. Iterar sem checar transformaria uma busca falha num 502.

    A Dica sem fontes é pior que com, mas muito melhor que nenhuma Dica.
    """
    def handler(request):
        return httpx.Response(
            200,
            json={
                **resposta_ok(),
                "content": [
                    {
                        "type": "web_search_tool_result",
                        "tool_use_id": "srvtoolu_1",
                        "content": {"type": "web_search_tool_result_error",
                                    "error_code": "max_uses_exceeded"},
                    },
                    {"type": "text", "text": "Não encontrei material confiável."},
                ],
            },
        )

    client, http = make_ai(handler)
    try:
        dica = await client.sintetizar("Nioh: Complete Edition", "Spa Healer")
    finally:
        await http.aclose()

    assert dica.texto == "Não encontrei material confiável."
    assert dica.fontes == []


async def test_texto_junta_todos_os_blocos():
    """Com busca web a resposta vem **citada**, e citação quebra o texto em
    vários blocos `text`. Pegar só o primeiro entrega o preâmbulo e descarta a
    resposta — foi exatamente o que o /verify pegou em produção: 170 chars
    terminando em "1. ", no ponto onde a lista começaria.
    """
    def handler(request):
        return httpx.Response(
            200,
            json={
                **resposta_ok(),
                "content": [
                    {"type": "text", "text": "Passos práticos:\n\n"},
                    {"type": "text", "text": "1. Use a fonte termal.\n"},
                    {"type": "text", "text": "2. Espere o terceiro chefe."},
                ],
            },
        )

    client, http = make_ai(handler)
    try:
        dica = await client.sintetizar("Nioh: Complete Edition", "Spa Healer")
    finally:
        await http.aclose()

    assert dica.texto == (
        "Passos práticos:\n\n1. Use a fonte termal.\n2. Espere o terceiro chefe."
    )


async def test_busca_web_tem_teto_de_rodadas():
    """`max_uses` é o multiplicador de custo mais direto que existe aqui.

    Sem teto, o modelo decide quantas buscas fazer, e cada rodada traz mais
    resultados para dentro do contexto — o /verify mediu 9-10 fontes, ou seja
    várias rodadas. Limitar corta o custo por dica sem o usuário notar.
    """
    corpos = []

    def handler(request):
        corpos.append(json.loads(request.content))
        return httpx.Response(200, json=resposta_ok())

    client, http = make_ai(handler)
    try:
        await client.sintetizar("Nioh: Complete Edition", "Spa Healer")
    finally:
        await http.aclose()

    assert corpos[0]["tools"][0]["max_uses"] == 3


async def test_rate_limit_do_provedor_vira_excecao_tipada():
    """REQ-136 — hoje a exceção do SDK **escapa** e vira 500 sem `detail`.

    O teste que existia não pegava isso: o fake levantava `AiUnavailableError`
    já mapeada, ou seja exercitava um mapeamento que não existe. Aqui o 429 vem
    da rede, como na vida real.
    """
    def handler(request):
        return httpx.Response(429, json={"type": "error", "error": {"type": "rate_limit_error", "message": "slow down"}})

    client, http = make_ai(handler)
    try:
        with pytest.raises(AiRateLimitError):
            await client.sintetizar("Nioh: Complete Edition", "Spa Healer")
    finally:
        await http.aclose()


async def test_falha_generica_do_provedor_vira_excecao_tipada():
    """AC-137 — 5xx do provedor tem de virar 502 com mensagem, não 500 cru."""
    def handler(request):
        return httpx.Response(500, json={"type": "error", "error": {"type": "api_error", "message": "boom"}})

    client, http = make_ai(handler)
    try:
        with pytest.raises(AiUnavailableError):
            await client.sintetizar("Nioh: Complete Edition", "Spa Healer")
    finally:
        await http.aclose()


# --- Gemini (spec-design-provedor-de-ia-plugavel.md) -------------------------


def make_gemini(handler, *, rate_per_minute=600.0, rate_burst=10,
                model="gemini-3.1-flash-lite"):
    """Mesmo seam da Anthropic: MockTransport injetado no SDK (PAT-130).

    O `google-genai` aceita `httpx_async_client` no `HttpOptions`, então dá para
    assertar sobre o corpo real que sai pela rede nos dois provedores — que é
    onde moram os requisitos de custo e de privacidade.
    """
    from google.genai import Client, types

    from app.ai.gemini_client import GeminiClient

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    sdk = Client(
        api_key="CHAVE-DE-TESTE",
        http_options=types.HttpOptions(httpx_async_client=http),
    )
    client = GeminiClient(
        sdk, model=model, rate_per_minute=rate_per_minute, rate_burst=rate_burst
    )
    return client, http


def resposta_gemini(texto="Use a fonte termal.", fontes=()):
    return {
        "candidates": [
            {
                "content": {"parts": [{"text": texto}], "role": "model"},
                "finishReason": "STOP",
                "groundingMetadata": {
                    "groundingChunks": [
                        {"web": {"uri": u, "title": t}} for t, u in fontes
                    ]
                },
            }
        ]
    }


async def test_gemini_declara_a_busca_do_google():
    """AC-135 — sem a ferramenta declarada o modelo responde de memória, e a
    Fonte (que sustenta a conferência) simplesmente não existe.
    """
    corpos = []

    def handler(request):
        corpos.append(json.loads(request.content))
        return httpx.Response(200, json=resposta_gemini())

    client, http = make_gemini(handler)
    try:
        await client.sintetizar("Nioh: Complete Edition", "Spa Healer")
    finally:
        await http.aclose()

    assert corpos[0]["tools"] == [{"googleSearch": {}}]


async def test_gemini_le_texto_e_fontes_do_grounding_sem_repetir():
    """As fontes vêm de `grounding_metadata`, não de blocos como na Anthropic.

    A dedup é a mesma dos dois lados (mora na base): o guia 100% casa com várias
    queries e volta repetido em qualquer provedor.
    """
    def handler(request):
        return httpx.Response(
            200,
            json=resposta_gemini(
                texto="Use a fonte termal em Izumo.",
                fontes=(
                    ("Nioh 100% Guide", "https://exemplo/guia"),
                    ("Nioh 100% Guide", "https://exemplo/guia"),
                    ("Spa Healer — vídeo", "https://exemplo/video"),
                ),
            ),
        )

    client, http = make_gemini(handler)
    try:
        dica = await client.sintetizar("Nioh: Complete Edition", "Spa Healer")
    finally:
        await http.aclose()

    assert dica.texto == "Use a fonte termal em Izumo."
    assert [(f.title, f.url) for f in dica.fontes] == [
        ("Nioh 100% Guide", "https://exemplo/guia"),
        ("Spa Healer — vídeo", "https://exemplo/video"),
    ]


async def test_gemini_sem_grounding_devolve_dica_sem_fontes():
    """O modelo pode decidir não buscar. Dica sem fonte é pior que com — e muito
    melhor que derrubar o painel por falta de um campo opcional.
    """
    def handler(request):
        return httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": "Não encontrei."}],
                                              "role": "model"}, "finishReason": "STOP"}]},
        )

    client, http = make_gemini(handler)
    try:
        dica = await client.sintetizar("Nioh: Complete Edition", "Spa Healer")
    finally:
        await http.aclose()

    assert dica.texto == "Não encontrei."
    assert dica.fontes == []


async def test_gemini_traduz_erros_do_sdk():
    """REQ-136 no outro provedor. Mesmo contrato, exceções de SDK diferentes."""
    for status, esperada in ((429, AiRateLimitError), (500, AiUnavailableError)):
        def handler(request, _s=status):
            return httpx.Response(_s, json={"error": {"code": _s, "message": "x"}})

        client, http = make_gemini(handler)
        try:
            with pytest.raises(esperada):
                await client.sintetizar("Nioh: Complete Edition", "Spa Healer")
        finally:
            await http.aclose()


async def test_o_prompt_e_identico_nos_dois_provedores():
    """CON-132/AC-140 — o que muda é o transporte, nunca o que se pede.

    É este teste que torna a comparação de qualidade honesta: com prompts
    afinados por provedor, comparar as sínteses compararia *prompts*, e a
    conclusão não serviria para decidir qual manter.
    """
    prompts = {}

    def handler_anthropic(request):
        corpo = json.loads(request.content)
        prompts["anthropic"] = corpo["messages"][0]["content"]
        return httpx.Response(200, json=resposta_ok())

    def handler_gemini(request):
        corpo = json.loads(request.content)
        prompts["gemini"] = corpo["contents"][0]["parts"][0]["text"]
        return httpx.Response(200, json=resposta_gemini())

    for make, handler in ((make_ai, handler_anthropic), (make_gemini, handler_gemini)):
        client, http = make(handler)
        try:
            await client.sintetizar("Nioh: Complete Edition", "Spa Healer")
        finally:
            await http.aclose()

    assert prompts["anthropic"] == prompts["gemini"]
    # E o prompt carrega os dois insumos, sem nada do jogador (AC-118).
    assert "Spa Healer" in prompts["gemini"]
    assert "Nioh: Complete Edition" in prompts["gemini"]
