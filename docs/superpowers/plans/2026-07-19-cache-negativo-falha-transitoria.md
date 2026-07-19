# Cache Negativo de Falha Transitória — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fazer o `_cached()` do `AchievementsService` lembrar de uma falha transitória da Steam por 60 s, para que uma carga de biblioteca com cache quente pare de re-pagar os 3,5 s de backoff de um jogo quebrado.

**Architecture:** Uma sentinela `_Falha` (NamedTuple com tipo + mensagem) gravada no `TTLCache` sob a mesma chave do valor, com TTL próprio (`FALHA_TTL = 60`). Na leitura, uma sentinela é convertida de volta em exceção — instância **nova**, não a guardada. O conjunto de exceções guardadas é fechado: `SteamUnavailableError` e `SteamRateLimitError`, as duas únicas que passam pelo backoff de `SteamClient._get()`. Toda a mudança de comportamento vive em **um método** (`_cached`), o que a estende automaticamente aos sete chamadores.

**Tech Stack:** Python 3.12, `asyncio`, `pytest` + `pytest-asyncio`, `uv`. Nenhuma dependência nova.

**Spec:** `spec/spec-design-cache-negativo-falha-transitoria.md` (v1.1). Em caso de divergência entre este plano e a spec, **a spec vence** — pare e reporte.

## Global Constraints

- **Um arquivo de produção é tocado:** `app/services/achievements.py`. Nenhuma alteração em `app/steam/`, `app/ai/`, `app/web/`, `app/schemas/` ou `frontend/` (CON-143).
- **Nenhuma dependência nova** no `pyproject.toml` (PLT-001).
- **`_cached_ou_ausente()` permanece inalterado** (CON-140). Se um passo parecer exigir mexer nele, o passo está errado.
- **Conjunto guardado fechado:** exatamente `SteamUnavailableError` e `SteamRateLimitError`. **Nenhuma** exceção de IA (CON-141).
- **`FALHA_TTL = 60`**, independente do TTL do valor da chave (REQ-143).
- **Um teste por ciclo RED/GREEN.** Proibido escrever dois testes antes de implementar (`CLAUDE.md`).
- **Testes pela interface pública:** `game_detail`, `list_library`, `dica`. **Nunca** invocar `_cached` diretamente no teste.
- **Fakes escritos à mão:** usar o `FakeSteamClient`/`FakeAiClient` que já existem em `tests/test_service.py`. Proibido `mock.patch`.
- **Relógio:** atravessar TTL com `TTLCache(now=lambda: relogio["agora"])`. **Nunca** `time.sleep` ou `asyncio.sleep`.
- **Idioma:** comentários, docstrings, nomes de teste e mensagens em **pt-BR**.
- Nenhum teste existente pode ser **deletado**.

---

## File Structure

| Arquivo | Responsabilidade | Ação |
|---|---|---|
| `app/services/achievements.py` | Sentinela `_Falha`, constante `FALHA_TTL`, conjunto `_FALHAS_GUARDADAS`, guarda dentro de `_cached()` | Modificar |
| `tests/test_service.py` | Todos os testes desta feature, junto dos demais testes de cache do service | Modificar (append) |
| `spec/spec-architecture-steam-achievements.md` | CON-011 remete à spec nova; tabela de TTLs ganha `FALHA_TTL` | Modificar |
| `CLAUDE.md` | Convenção de cache menciona a guarda | Modificar |
| `ROADMAP.md` | Item da latência sai de "Correções pendentes" | Modificar |

Nenhum arquivo novo. A feature é pequena e coesa demais para justificar um módulo próprio: extrair `_Falha` para `core/` criaria um import a mais para ganhar zero reuso (o `TTLCache` não precisa conhecê-la — a sentinela é semântica do service).

---

### Task 1: Sentinela de falha e guarda no `_cached()`

Cobre **AC-140** e **AC-141**. É o núcleo: depois dele a feature funciona; as tarefas seguintes travam bordas.

**Files:**
- Modify: `app/services/achievements.py` (imports no topo; constantes ~linha 56; sentinela junto de `_NAO_EXISTE` na linha 60; método `_cached` na linha 345)
- Test: `tests/test_service.py` (append ao final)

**Interfaces:**
- Consumes: `TTLCache.get/set` (`app/core/cache.py`), `SteamUnavailableError`/`SteamRateLimitError` (`app/errors.py`), `FakeSteamClient`/`make_service`/`STEAMID` (`tests/test_service.py`).
- Produces: `FALHA_TTL: int = 60`, `_Falha(tipo: type[Exception], mensagem: str)` (NamedTuple privado), `_FALHAS_GUARDADAS: tuple[type[Exception], ...]`. A assinatura de `_cached(self, key, ttl, fetch)` **não muda** — Tasks 2–5 dependem disso.

---

- [ ] **Step 1: Escrever o teste que falha (AC-140)**

Adicionar ao final de `tests/test_service.py`:

```python
async def test_falha_transitoria_da_steam_nao_e_re_buscada_dentro_da_janela():
    """Um jogo quebrado não pode custar o backoff em toda requisição.

    Medido no app real: o GetPlayerAchievements do appid 1966720 devolve 5xx de
    forma consistente, o client retenta 4× (3,5s dormindo) e a biblioteca inteira
    espera. Sem guardar a falha, esse custo se repete a cada request.
    """
    client = FakeSteamClient(
        owned_games=[{"appid": 10, "name": "A", "playtime_forever": 1, "img_icon_url": "a"}],
        achievements={10: SteamUnavailableError("Steam indisponível")},
    )
    service = make_service(client)

    for _ in range(2):
        with pytest.raises(SteamUnavailableError):
            await service.game_detail(STEAMID, 10)

    assert client.ach_calls == [10]  # a segunda leitura veio do cache, não da Steam
```

O `SteamUnavailableError` já está importado no topo de `tests/test_service.py` — não duplicar o import.

- [ ] **Step 2: Rodar o teste e confirmar que falha**

```bash
uv run pytest tests/test_service.py::test_falha_transitoria_da_steam_nao_e_re_buscada_dentro_da_janela -v
```

Esperado: **FAIL** com `assert [10, 10] == [10]` — a Steam foi consultada duas vezes.

- [ ] **Step 3: Implementar o mínimo**

Em `app/services/achievements.py`, acrescentar ao bloco `from app.errors import (...)` do topo as duas exceções que faltam, mantendo a ordem alfabética:

```python
from app.errors import (
    DicaIndisponivel,
    DicaSemOrcamento,
    SteamDataUnavailable,
    SteamError,
    SteamProfileNotFound,
    SteamRateLimitError,
    SteamUnavailableError,
    SteamVanityNotFound,
)
```

Logo após a constante `GENRES_MISS_TTL` (fim do bloco de TTLs, ~linha 56), acrescentar:

```python
# TTL da *falha*, e não do valor — de propósito independente do TTL da chave.
# Amarrá-lo ao TTL do valor faria uma indisponibilidade de 30s ficar guardada por
# 24h em `schema:` ou 7 dias em `genres:`. Ver REQ-143.
FALHA_TTL = 60
```

Junto de `_NAO_EXISTE` (linha 60), acrescentar:

```python
class _Falha(NamedTuple):
    """Sentinela de falha transitória guardada no cache.

    Guarda **tipo e mensagem**, nunca a instância da exceção: a sentinela vive
    até FALHA_TTL e pode ser lida por dezenas de requisições nesse intervalo, e
    re-levantar a mesma instância encadeia `__traceback__` a cada vez.
    """

    tipo: type[Exception]
    mensagem: str


# Conjunto FECHADO. O critério não é "é transitória?" — é "o fetch paga retry com
# backoff?", e hoje isso significa exatamente "passa por SteamClient._get()".
# Nenhuma exceção de `ai/` entra aqui: aquela camada não retenta e não dorme, e o
# AiRateLimitError pode vir do token bucket local, que se recupera sozinho — a
# guarda prolongaria o bloqueio em vez de evitar uma espera. Ver CON-141/GUD-140.
_FALHAS_GUARDADAS = (SteamUnavailableError, SteamRateLimitError)
```

Substituir o corpo de `_cached` (linha 345) por:

```python
    async def _cached(self, key: str, ttl: int | Callable[[Any], int], fetch):
        """Busca no cache; no miss, chama `fetch` e guarda o resultado.

        `ttl` pode depender do valor (gênero encontrado dura mais que gênero
        ausente). `None` nunca é cacheado: é o próprio sinal de miss do TTLCache.

        Falha transitória também é guardada, com TTL próprio (`FALHA_TTL`), e
        volta como exceção — nunca como valor. Colapsá-la num valor faria o
        detalhe de um jogo momentaneamente fora do ar afirmar "jogo sem
        conquistas", que é o significado já ocupado por `[]` (CON-011).
        """
        hit = self._cache.get(key)
        # Antes do `is not None`: a sentinela é um valor, e cair no return a
        # devolveria ao chamador como se fosse dado (CON-142).
        if isinstance(hit, _Falha):
            raise hit.tipo(hit.mensagem)
        if hit is not None:
            return hit
        try:
            value = await fetch()
        except _FALHAS_GUARDADAS as exc:
            self._cache.set(key, _Falha(type(exc), str(exc)), FALHA_TTL)
            raise
        if value is not None:
            self._cache.set(key, value, ttl(value) if callable(ttl) else ttl)
        return value
```

- [ ] **Step 4: Rodar o teste e confirmar que passa**

```bash
uv run pytest tests/test_service.py::test_falha_transitoria_da_steam_nao_e_re_buscada_dentro_da_janela -v
```

Esperado: **PASS**.

- [ ] **Step 5: Escrever o segundo teste, que falha (AC-141)**

```python
async def test_falha_guardada_volta_como_excecao_nova_e_nao_como_valor():
    """A sentinela nunca chega ao chamador, e o re-levantamento não reusa a
    instância guardada — ela vive até 60s no cache, e `raise` da mesma instância
    encadeia traceback a cada leitura."""
    erro = SteamUnavailableError("Steam indisponível")
    client = FakeSteamClient(
        owned_games=[{"appid": 10, "name": "A", "playtime_forever": 1, "img_icon_url": "a"}],
        achievements={10: erro},
    )
    service = make_service(client)

    with pytest.raises(SteamUnavailableError):
        await service.game_detail(STEAMID, 10)
    with pytest.raises(SteamUnavailableError) as segunda:
        await service.game_detail(STEAMID, 10)

    assert segunda.value is not erro  # instância nova (REQ-141)
    assert str(segunda.value) == "Steam indisponível"
```

- [ ] **Step 6: Rodar e confirmar**

```bash
uv run pytest tests/test_service.py -k "falha_guardada_volta_como_excecao" -v
```

Esperado: **PASS** direto (a implementação do Step 3 já satisfaz). Se falhar em `segunda.value is not erro`, a implementação está re-levantando a instância guardada — corrigir para construir `hit.tipo(hit.mensagem)`.

> Nota: este é o caso legítimo de um teste que nasce verde. Ele não é redundante — trava uma decisão (instância nova) que uma refatoração futura desfaria em silêncio.

- [ ] **Step 7: Rodar a suíte inteira**

```bash
uv run pytest
```

Esperado: **todos os testes passam**, incluindo os 94 pré-existentes. Se algum teste antigo quebrar, **pare e reporte** — a spec proíbe deletar testes, e uma quebra aqui significa que a guarda mudou comportamento não previsto.

- [ ] **Step 8: Commit**

```bash
git add app/services/achievements.py tests/test_service.py
git commit -m "feat(cache): guardar falha transitória da Steam por 60s

Um jogo quebrado custava o backoff (3,5s) em toda carga da biblioteca.
A falha vira sentinela no cache e volta como exceção nova, nunca como
valor: colapsá-la em [] faria o detalhe dizer 'jogo sem conquistas'.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Expiração pelo `FALHA_TTL`, inclusive em chave de TTL longo

Cobre **AC-142** e **AC-147**. Trava o REQ-143 — a independência entre o TTL da falha e o TTL do valor.

**Files:**
- Test: `tests/test_service.py` (append)
- Modify: nenhum arquivo de produção esperado (a Task 1 já implementa). Se um teste falhar, corrigir `app/services/achievements.py`.

**Interfaces:**
- Consumes: `FALHA_TTL`, `_Falha`, `_cached` da Task 1; `TTLCache(now=...)`, `AchievementsService`, `SCHEMA_TTL`.
- Produces: nada de novo.

---

- [ ] **Step 1: Escrever o teste que falha (AC-142)**

```python
async def test_falha_guardada_expira_e_a_steam_volta_a_ser_consultada():
    """60s é curto de propósito: uma indisponibilidade que terminou não pode
    ficar visível. O relógio é injetado — nada de sleep na suíte."""
    relogio = {"agora": 1000.0}
    client = FakeSteamClient(
        owned_games=[{"appid": 10, "name": "A", "playtime_forever": 1, "img_icon_url": "a"}],
        achievements={10: SteamUnavailableError("Steam indisponível")},
    )
    service = AchievementsService(client, TTLCache(now=lambda: relogio["agora"]))

    with pytest.raises(SteamUnavailableError):
        await service.game_detail(STEAMID, 10)

    relogio["agora"] += 61  # passou do FALHA_TTL

    with pytest.raises(SteamUnavailableError):
        await service.game_detail(STEAMID, 10)

    assert client.ach_calls == [10, 10]
```

- [ ] **Step 2: Rodar e confirmar**

```bash
uv run pytest tests/test_service.py -k "falha_guardada_expira" -v
```

Esperado: **PASS**. Se falhar com `[10]`, a sentinela foi gravada com o TTL do valor (`ACH_TTL = 300`) em vez de `FALHA_TTL` — corrigir a chamada `self._cache.set(...)` no `except`.

- [ ] **Step 3: Escrever o teste do TTL longo (AC-147)**

```python
async def test_falha_em_chave_de_ttl_longo_expira_pelo_ttl_da_falha():
    """`schema:{appid}` vale 24h. A *falha* nele vale 60s.

    Se a sentinela herdasse o TTL do valor, uma Steam que voltou ao ar em cinco
    minutos ficaria marcada como quebrada por um dia — e em `genres:`, por sete.
    """
    relogio = {"agora": 1000.0}
    client = FakeSteamClient(
        owned_games=[{"appid": 10, "name": "A", "playtime_forever": 1, "img_icon_url": "a"}],
        achievements={10: [{"apiname": "x", "achieved": 1, "unlocktime": 0}]},
        schemas={10: SteamUnavailableError("Steam indisponível")},
    )
    service = AchievementsService(client, TTLCache(now=lambda: relogio["agora"]))

    with pytest.raises(SteamUnavailableError):
        await service.game_detail(STEAMID, 10)

    relogio["agora"] += 61

    with pytest.raises(SteamUnavailableError):
        await service.game_detail(STEAMID, 10)

    # (10, None) é o schema pt-BR; (10, "english") é o schema_en, que engole a
    # falha dentro do próprio buscar() e não interessa aqui (CON-145).
    assert [c for c in client.schema_calls if c == (10, None)] == [(10, None), (10, None)]
```

- [ ] **Step 4: Rodar e confirmar**

```bash
uv run pytest tests/test_service.py -k "ttl_longo" -v
```

Esperado: **PASS**.

- [ ] **Step 5: Rodar a suíte e commitar**

```bash
uv run pytest
git add tests/test_service.py
git commit -m "test(cache): travar independência entre FALHA_TTL e TTL do valor

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: As exclusões — permanentes da Steam e toda a camada `ai/`

Cobre **AC-143** e **AC-148**. Estes testes são o guarda-corpo do erro que a v1.0 da spec cometeu: sem eles, incluir `AiRateLimitError` no conjunto passaria despercebido.

**Files:**
- Test: `tests/test_service.py` (append)
- Modify: nenhum arquivo de produção esperado.

**Interfaces:**
- Consumes: `_FALHAS_GUARDADAS` da Task 1; `FakeAiClient`, `SteamDataUnavailable`, `AiRateLimitError`, `Dica`, `Fonte`.
- Produces: nada de novo.

---

- [ ] **Step 1: Escrever o teste das permanentes (AC-143)**

```python
async def test_falha_permanente_nao_e_guardada():
    """401/403 não passam pelo backoff — o `_get()` levanta na hora, então não há
    espera a economizar. Guardar só faria o app demorar até 60s para perceber que
    um perfil acabou de virar público."""
    client = FakeSteamClient(
        owned_games=[{"appid": 10, "name": "A", "playtime_forever": 1, "img_icon_url": "a"}],
        achievements={10: SteamDataUnavailable("acesso negado")},
        summary={"personaname": "Fulano"},
    )
    service = make_service(client)

    for _ in range(2):
        with pytest.raises(SteamDataUnavailable):
            await service.game_detail(STEAMID, 10)

    assert client.ach_calls == [10, 10]  # nada foi guardado
```

O `summary` é obrigatório: `game_detail` captura `SteamDataUnavailable` e chama `_assert_exists()` para desempatar perfil privado de conta inexistente antes de re-levantar.

- [ ] **Step 2: Rodar e confirmar**

```bash
uv run pytest tests/test_service.py -k "falha_permanente" -v
```

Esperado: **PASS**.

- [ ] **Step 3: Escrever o teste da camada de IA (AC-148)**

```python
async def test_falha_da_ia_nunca_e_guardada():
    """Nenhuma exceção de `ai/` entra no conjunto (CON-141).

    A camada não retenta e não dorme, então não há backoff a economizar; e o
    AiRateLimitError também é levantado pelo token bucket local, que se recupera
    por refill em ~30s. Guardá-lo por 60s prolongaria o bloqueio na única feature
    paga do app — piorando exatamente o caso que a guarda diz melhorar.
    """
    ai = FakeAiClient(dica=AiRateLimitError("teto local de chamadas pagas atingido"))
    client = FakeSteamClient(
        owned_games=[{"appid": 10, "name": "A", "playtime_forever": 1, "img_icon_url": "a"}],
        achievements={10: [{"apiname": "x", "achieved": 0, "unlocktime": 0}]},
        schemas_en={10: {"achievements": [{"name": "x", "displayName": "Spa Healer"}]}},
    )
    service = make_service(client, ai=ai)

    for _ in range(2):
        with pytest.raises(AiRateLimitError):
            await service.dica(STEAMID, 10, "x")

    assert len(ai.calls) == 2  # a segunda tentou de novo, como deve
```

Acrescentar `AiRateLimitError` ao bloco `from app.errors import (...)` do topo de `tests/test_service.py`, em ordem alfabética (antes de `AiUnavailableError`).

- [ ] **Step 4: Rodar e confirmar**

```bash
uv run pytest tests/test_service.py -k "falha_da_ia" -v
```

Esperado: **PASS**. Se falhar com `len(ai.calls) == 1`, alguma exceção de IA entrou em `_FALHAS_GUARDADAS` — removê-la.

- [ ] **Step 5: Rodar a suíte e commitar**

```bash
uv run pytest
git add tests/test_service.py
git commit -m "test(cache): travar as exclusões do conjunto guardado

Permanentes da Steam e toda a camada ai/ ficam de fora. O teste da IA
existe para quebrar caso alguém a reintroduza — foi o erro da v1.0 da
spec.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Recuperação — sucesso sobrescreve a falha

Cobre **AC-144**. Sem isto, um erro poderia "grudar" na chave.

**Files:**
- Test: `tests/test_service.py` (append)
- Modify: nenhum arquivo de produção esperado.

**Interfaces:**
- Consumes: tudo da Task 1. Produces: nada.

---

- [ ] **Step 1: Escrever o teste**

```python
async def test_sucesso_apos_a_falha_expirar_substitui_a_sentinela():
    """A falha não pode grudar: passado o FALHA_TTL, um fetch bem-sucedido grava
    o valor com o TTL normal e as leituras seguintes o leem do cache."""
    relogio = {"agora": 1000.0}
    client = FakeSteamClient(
        owned_games=[{"appid": 10, "name": "A", "playtime_forever": 1, "img_icon_url": "a"}],
        achievements={10: SteamUnavailableError("Steam indisponível")},
        schemas={10: {"gameName": "A", "achievements": [{"name": "x", "displayName": "X"}]}},
    )
    service = AchievementsService(client, TTLCache(now=lambda: relogio["agora"]))

    with pytest.raises(SteamUnavailableError):
        await service.game_detail(STEAMID, 10)

    relogio["agora"] += 61
    # A Steam voltou: o fake passa a devolver a conquista em vez de levantar.
    client._ach[10] = [{"apiname": "x", "achieved": 1, "unlocktime": 0}]

    detalhe = await service.game_detail(STEAMID, 10)
    assert detalhe.achieved_count == 1

    # Terceira leitura: o valor veio do cache, não da Steam (2 chamadas ao todo).
    await service.game_detail(STEAMID, 10)
    assert client.ach_calls == [10, 10]
```

Mexer em `client._ach` diretamente é aceitável aqui: o `FakeSteamClient` é um fake do próprio arquivo de teste, e "o fornecedor voltou ao ar no meio do teste" não tem outra forma de ser expresso.

- [ ] **Step 2: Rodar e confirmar**

```bash
uv run pytest tests/test_service.py -k "sucesso_apos_a_falha" -v
```

Esperado: **PASS**.

- [ ] **Step 3: Rodar a suíte e commitar**

```bash
uv run pytest
git add tests/test_service.py
git commit -m "test(cache): garantir que sucesso substitui a falha guardada

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Integração — a mesma entrada lida por dois chamadores com tratamentos opostos

Cobre **AC-145** e **AC-146**. É a tarefa que prova o ganho real e o invariante mais importante: a biblioteca é best-effort, o detalhe não pode mentir.

**Files:**
- Test: `tests/test_service.py` (append)
- Modify: nenhum arquivo de produção esperado.

**Interfaces:**
- Consumes: tudo da Task 1. Produces: nada.

---

- [ ] **Step 1: Escrever o teste do detalhe (AC-145)**

```python
async def test_detalhe_de_jogo_em_falha_nao_vira_jogo_sem_conquistas():
    """O invariante mais caro desta feature.

    `[]` já significa "jogo sem conquistas" em `player_ach:` (CON-011). Se a falha
    fosse guardada como `[]`, o detalhe de um jogo momentaneamente fora do ar
    responderia 200 afirmando que ele não tem conquistas — e cacharia a mentira
    por ACH_TTL. A falha volta como exceção justamente para isso.
    """
    client = FakeSteamClient(
        owned_games=[{"appid": 10, "name": "A", "playtime_forever": 1, "img_icon_url": "a"}],
        achievements={10: SteamUnavailableError("Steam indisponível")},
    )
    service = make_service(client)

    with pytest.raises(SteamUnavailableError):
        await service.game_detail(STEAMID, 10)
    # Segunda leitura, agora servida pela sentinela: mesmo resultado.
    with pytest.raises(SteamUnavailableError):
        await service.game_detail(STEAMID, 10)
```

- [ ] **Step 2: Rodar e confirmar**

```bash
uv run pytest tests/test_service.py -k "nao_vira_jogo_sem_conquistas" -v
```

Esperado: **PASS**.

- [ ] **Step 3: Escrever o teste da biblioteca (AC-146)**

```python
async def test_biblioteca_com_jogo_quebrado_nao_reconsulta_a_steam_na_segunda_carga():
    """O caso medido: 155 jogos, um deles em 5xx consistente.

    Na segunda carga nenhuma chamada de conquistas é feita — nem para os jogos
    que deram certo (cache normal) nem para o quebrado (sentinela). É a diferença
    entre 4,7s e ~0,1s. O jogo quebrado segue sem %, best-effort como sempre.
    """
    client = FakeSteamClient(
        owned_games=[
            {"appid": 10, "name": "Bom", "playtime_forever": 1, "img_icon_url": "a"},
            {"appid": 20, "name": "Quebrado", "playtime_forever": 1, "img_icon_url": "b"},
        ],
        achievements={
            10: [{"apiname": "x", "achieved": 1, "unlocktime": 0}],
            20: SteamUnavailableError("Steam indisponível"),
        },
    )
    service = make_service(client)

    await service.list_library(STEAMID, include=["achievements"])
    chamadas_da_primeira_carga = len(client.ach_calls)

    jogos = await service.list_library(STEAMID, include=["achievements"])

    assert len(client.ach_calls) == chamadas_da_primeira_carga  # segunda carga: zero
    quebrado = next(j for j in jogos if j.appid == 20)
    assert quebrado.percent is None  # best-effort preservado (CON-144)
    bom = next(j for j in jogos if j.appid == 10)
    assert bom.percent == 100.0
```

- [ ] **Step 4: Rodar e confirmar**

```bash
uv run pytest tests/test_service.py -k "jogo_quebrado_nao_reconsulta" -v
```

Esperado: **PASS**.

- [ ] **Step 5: Rodar a suíte e commitar**

```bash
uv run pytest
git add tests/test_service.py
git commit -m "test(cache): provar o ganho na biblioteca e o invariante do detalhe

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: Documentação

Cobre o item 6 dos critérios de validação da spec (§10.6). Sem isto o CON-011 fica mentindo por omissão — o mesmo defeito que a v2.0 da spec de arquitetura foi escrita para corrigir.

**Files:**
- Modify: `spec/spec-architecture-steam-achievements.md` (CON-011, ~linha 294; tabela de TTLs)
- Modify: `CLAUDE.md` (seção "Convenções de código", bullet dos dois helpers de cache)
- Modify: `ROADMAP.md` (seção "Correções pendentes")

**Interfaces:** nenhuma — só documentação. Nenhum teste.

---

- [ ] **Step 1: Estender o CON-011 na spec de arquitetura**

Ao final do CON-011 em `spec/spec-architecture-steam-achievements.md`, acrescentar:

```markdown
  - **falha transitória** (5xx/429 da Steam, após esgotar o retry) ⇒ é guardada
    como *falha* e re-levantada como exceção, com TTL próprio de 60 s
    (`FALHA_TTL`), **nunca** convertida em valor. Sem isto, um jogo em 5xx
    consistente faz toda carga da biblioteca re-pagar 3,5 s de backoff.
    Especificado em `spec/spec-design-cache-negativo-falha-transitoria.md`.
```

- [ ] **Step 2: Acrescentar `FALHA_TTL` à tabela de TTLs**

Na tabela de TTLs da mesma spec, acrescentar uma linha ao final:

```markdown
| `FALHA_TTL` | 60 s | Falha transitória em **qualquer** chave servida por `_cached()` — por natureza do resultado, não por chave |
```

- [ ] **Step 3: Atualizar o `CLAUDE.md`**

Na seção "Convenções de código", logo após o bullet que começa com "Dois helpers, e a escolha não é estilo", acrescentar:

```markdown
- O `_cached()` também guarda **falha transitória** (`SteamUnavailableError`,
  `SteamRateLimitError`) por `FALHA_TTL` = 60 s, re-levantando-a como exceção
  nova — nunca como valor. O critério de inclusão não é "é transitória?", é **"o
  fetch paga retry com backoff?"**, e hoje isso significa "passa por
  `SteamClient._get()`". Nenhuma exceção de `ai/` entra: aquela camada não
  retenta, e o `AiRateLimitError` também vem do token bucket local, que se
  recupera por refill — guardá-lo prolongaria o bloqueio na única feature paga.
```

- [ ] **Step 4: Mover o item no `ROADMAP.md`**

Na seção "Correções pendentes", trocar o `- [ ]` do item "Um jogo quebrado custa ~4,5s em toda carga da biblioteca" por `- [x]` e acrescentar ao final do parágrafo:

```markdown
      **Entregue** (jul/2026): a guarda vive no `_cached()` compartilhado, não em
      `_player_achievements` — assim vale para `owned_games` e `schema` sem código
      novo. Falha vira sentinela com TTL próprio de 60 s e volta como exceção, não
      como valor. Spec: `spec/spec-design-cache-negativo-falha-transitoria.md`.
      Latência medida no `/verify`: **PREENCHER NA TASK 7**.
```

> O marcador `PREENCHER NA TASK 7` é intencional e temporário — a Task 7 o substitui pelo número medido. Não commitar a Task 7 sem substituí-lo.

- [ ] **Step 5: Commit**

```bash
git add spec/spec-architecture-steam-achievements.md CLAUDE.md ROADMAP.md
git commit -m "docs(cache): registrar a guarda de falha no CON-011, CLAUDE.md e roadmap

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 7: `/verify` no app real

Cobre o item 7 dos critérios de validação (§10.7). **Esta tarefa pode reprovar a feature.** Se a carga quente não cair para a ordem de 0,1 s, a causa presumida está errada e o ciclo não está concluído — reportar, não maquiar.

**Files:**
- Modify: `ROADMAP.md` (substituir o marcador da Task 6)

**Interfaces:** nenhuma.

---

- [ ] **Step 1: Subir o backend**

```bash
uv run uvicorn app.main:app --reload
```

Requer `STEAM_API_KEY` real no `.env` da raiz. Se ela não estiver disponível, **pare e reporte** — não simular, não inventar número.

- [ ] **Step 2: Medir a carga fria e a quente**

Em outro terminal, com um `steamid` de biblioteca grande (o perfil de demonstração usado no `/verify` anterior serve):

```bash
STEAMID=<steamid>
curl -s -o /dev/null -w "fria:   %{time_total}s\n" \
  "http://localhost:8000/api/users/$STEAMID/games?include=achievements"
curl -s -o /dev/null -w "quente: %{time_total}s\n" \
  "http://localhost:8000/api/users/$STEAMID/games?include=achievements"
```

Esperado: a **quente** na ordem de **0,1 s**. A referência a bater é a medição anterior de **4,7 s**.

- [ ] **Step 3: Confirmar que o detalhe do jogo quebrado ainda erra honestamente**

```bash
curl -s -w "\nHTTP %{http_code}\n" "http://localhost:8000/api/users/$STEAMID/games/1966720"
```

Esperado: **HTTP 502** com `{"detail": "A Steam está indisponível no momento."}` — e **não** um 200 com `supports_achievements: false`. Um 200 aqui significa que a falha virou valor: a feature está errada (AC-145).

- [ ] **Step 4: Registrar o número medido**

Substituir `PREENCHER NA TASK 7` no `ROADMAP.md` pelo valor real medido no Step 2, no formato: `carga quente de 4,7s para <X>s`.

- [ ] **Step 5: Commit**

```bash
git add ROADMAP.md
git commit -m "docs(roadmap): registrar a latência medida no /verify

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

**1. Cobertura da spec**

| Requisito | Tarefa |
|---|---|
| REQ-140 (guardar e re-levantar) | Task 1 |
| REQ-141 (instância nova) | Task 1, Step 5 |
| REQ-142 (conjunto fechado) | Task 1, Step 3 + Task 3 |
| REQ-143 (`FALHA_TTL` independente) | Task 2 |
| REQ-144 (sucesso sobrescreve) | Task 4 |
| REQ-145 (latência) | Task 5 + Task 7 |
| CON-140 (`_cached_ou_ausente` intacto) | Global Constraints; nenhuma tarefa o toca |
| CON-141 (nada de IA) | Task 3, Step 3 |
| CON-142 (sentinela não vaza) | Task 1, Step 5 |
| CON-143 (contratos externos) | Global Constraints; nenhuma tarefa toca `web/`/`schemas/`/`frontend/` |
| CON-144 (best-effort preservado) | Task 5, Step 3 |
| CON-145 (não-casos) | Constatação; verificado no filtro do teste da Task 2, Step 3 |
| SEC-140 (mensagem não ganha dado) | Task 1, Step 3 — a sentinela guarda só `str(exc)` |
| GUD-140 / PAT-140 | Comentários da Task 1, Step 3 |
| AC-140..148 | Tasks 1–5 |
| §10.6 (docs) | Task 6 |
| §10.7 (`/verify`) | Task 7 |

Sem lacunas.

**2. Placeholders**

Uma ocorrência deliberada: `PREENCHER NA TASK 7` no `ROADMAP.md` (Task 6, Step 4), com instrução explícita de substituição na Task 7, Step 4. Não é placeholder de plano — é um valor que só existe após a medição, e inventá-lo seria pior.

**3. Consistência de tipos e nomes**

`FALHA_TTL`, `_Falha(tipo, mensagem)` e `_FALHAS_GUARDADAS` são definidos na Task 1, Step 3 e usados com esses mesmos nomes nas Tasks 2, 3 e 6. A assinatura de `_cached(self, key, ttl, fetch)` não muda em tarefa nenhuma. Os atributos do fake (`ach_calls`, `schema_calls`, `_ach`, `calls`) conferem com `tests/test_service.py`.
