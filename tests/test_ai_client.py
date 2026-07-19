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

from app.ai.client import AiClient
from app.errors import AiRateLimitError


def make_ai(handler, *, rate_per_minute=600.0, rate_burst=10, model="claude-haiku-4-5"):
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    sdk = AsyncAnthropic(api_key="KEY-DE-TESTE", http_client=http)
    client = AiClient(
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
