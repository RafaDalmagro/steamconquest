---
title: Cache Negativo de Falha Transitória — Especificação de Comportamento
version: 1.1
date_created: 2026-07-19
last_updated: 2026-07-19
owner: rafa.limadalmagro
tags: [backend, cache, resiliencia, latencia, steam, ia]
---

# Introduction

Especificação da guarda de **falha transitória** no helper `_cached()` do
`AchievementsService`. Hoje uma falha de fetch não é registrada em lugar nenhum:
o helper propaga a exceção e não guarda nada. Como o `SteamClient` retenta com
backoff exponencial antes de desistir, **cada requisição volta a pagar o backoff
inteiro** para o mesmo recurso quebrado.

O efeito foi medido no app real (`/verify` da revisão de arquitetura, jul/2026):
o `GetPlayerAchievements` do **appid 1966720** devolve 5xx de forma consistente;
o client retenta 4× (0,5 + 1 + 2 = **3,5 s dormindo**) e só então levanta. O
fan-out da biblioteca engole o erro — mas não engole a latência, porque
`asyncio.gather` espera o jogo quebrado. Resultado com o cache quente e 154 dos
155 jogos vindos do cache: **4,7 s de resposta**, dos quais ~4,5 s são um único
jogo.

Esta iteração faz o `_cached()` **lembrar da falha por uma janela curta**, no
mesmo espírito do cache negativo que o CON-011 já exige para o "não" que é
resposta. Alvo de latência: carga quente da biblioteca em **~0,1 s**.

Esta spec **não** altera nenhum contrato HTTP, nenhum modelo de domínio e nenhuma
tela.

> **v1.1** — a v1.0 incluía `AiUnavailableError` e `AiRateLimitError` no conjunto
> guardado, afirmando que eram "retentadas". A validação contra o código mostrou
> que **não são**: `app/ai/base.py` tem apenas um `TokenBucket`, sem `sleep` e sem
> retry. Pior, o `AiRateLimitError` de `base.py` vem do bucket local, que se
> recupera sozinho por refill — guardá-lo por 60 s prolongaria um bloqueio em vez
> de evitar uma espera. As duas saíram do conjunto (ver CON-141 e GUD-140). A v1.0
> também descrevia errado o mecanismo de `_app_genres` (CON-145).

## 1. Purpose & Scope

**Propósito:** definir, de forma não ambígua, quando uma falha de fetch é
guardada no cache, por quanto tempo, o que acontece na leitura seguinte e quais
falhas ficam explicitamente de fora.

**Escopo:** o helper `_cached()` de `app/services/achievements.py` e **todos** os
seus sete chamadores atuais — `_owned_games`, `_schema`, `_schema_en`,
`_app_genres`, `_global_percentages`, `_player_achievements` e `dica`.

Dos sete, a guarda só chega a disparar em **três**: `_owned_games`, `_schema` e
`_player_achievements`. Os outros quatro nunca levantam do `fetch` (CON-145) ou
levantam apenas exceções fora do conjunto guardado (`dica`, CON-141). Isso é
consequência do desenho, não uma lacuna — a guarda mora no helper justamente para
não precisar saber quem são os três.

**Fora de escopo** (ver CON-140 e CON-141): o helper `_cached_ou_ausente()`, a
camada `steam/`, a camada `ai/`, o `TTLCache`, as rotas, o SPA.

**Público-alvo:** o agente ou pessoa que implementa o ciclo RED/GREEN/REFACTOR
seguinte. Assume familiaridade com `app/services/achievements.py`,
`app/errors.py` e `app/core/cache.py`.

## 2. Definitions

| Termo | Definição |
|---|---|
| **Falha transitória** | Erro cuja causa é temporária e cuja recuperação não depende de ação do usuário nem de mudança de configuração: indisponibilidade do fornecedor (5xx), falha de rede, ou rate limit (429). É exatamente o conjunto de erros que o `SteamClient._get()` **retenta com backoff** antes de desistir. |
| **Falha permanente** | Erro cuja causa não muda por si só dentro da janela de cache: perfil privado, credencial inválida, recurso inexistente, orçamento diário esgotado. Não é retentada, portanto não custa backoff. |
| **Backoff** | Espera crescente entre tentativas do `SteamClient`. Com os defaults (`max_retries=3`, `backoff=0.5`), uma falha persistente custa 0,5 + 1 + 2 = **3,5 s** antes da exceção chegar ao service. |
| **Cache negativo** | Entrada de cache que registra uma resposta não-positiva, para que ela não seja re-buscada. Já existe no projeto para "o dado não existe" (CON-011). Esta spec acrescenta o caso "a busca falhou". |
| **Sentinela de falha** | Valor interno gravado no `TTLCache` que representa uma falha transitória registrada. Nunca é devolvido a um chamador (CON-142). |
| **`FALHA_TTL`** | Tempo de vida da sentinela de falha, em segundos. Distinto do TTL do valor de sucesso da mesma chave (REQ-143). |
| **Fan-out** | O `asyncio.gather` sobre a biblioteca em `_fill_counts`/`_fill_genres`, limitado por `Semaphore`. |

## 3. Requirements, Constraints & Guidelines

### Requisitos

- **REQ-140**: `_cached(key, ttl, fetch)` deve capturar as falhas transitórias
  levantadas por `fetch`, gravar uma **sentinela de falha** em `key` e, em
  seguida, **re-levantar** a exceção original ao chamador. O comportamento
  observável da primeira falha é idêntico ao de hoje: quem chama recebe a mesma
  exceção que receberia sem esta feature.

- **REQ-141**: Em uma leitura cujo `key` contém uma sentinela de falha válida,
  `_cached()` deve levantar uma exceção **do mesmo tipo e com a mesma mensagem**
  da falha registrada, **sem invocar `fetch`**. A exceção levantada deve ser uma
  **instância nova**, não a instância guardada — re-levantar repetidamente a
  mesma instância acumula frames em `__traceback__` a cada requisição, e o
  objeto vive no cache por até `FALHA_TTL`.

- **REQ-142**: O conjunto de exceções guardadas é **fechado e explícito**:
  `SteamUnavailableError` e `SteamRateLimitError`. Qualquer outra exceção propaga
  sem ser guardada, como hoje. O critério que define o conjunto é **"o fetch paga
  retry com backoff"**, e no código de hoje isso significa exatamente **"o fetch
  passa por `SteamClient._get()`"** — ver GUD-140.

- **REQ-143**: A sentinela de falha usa a constante `FALHA_TTL = 60` (segundos),
  **independente** do `ttl` do valor de sucesso daquela chave. Uma falha em
  `dica:{provedor}:{appid}:{apiname}` (cujo valor dura 7 dias) expira em 60 s,
  não em 7 dias.

- **REQ-144**: Uma gravação de sucesso na mesma chave **substitui** a sentinela
  de falha. Após `FALHA_TTL`, a chamada seguinte deve invocar `fetch` novamente e,
  havendo sucesso, gravar e devolver o valor normalmente.

- **REQ-145**: A latência da biblioteca com cache quente e um jogo em falha
  registrada deve ser dominada pelas leituras de cache, não pelo backoff. Alvo
  observável: a segunda carga consecutiva **não** executa nenhuma espera do
  `SteamClient` para o jogo em falha.

### Restrições

- **CON-140**: `_cached_ou_ausente()` **não** recebe a guarda. Ele já possui
  sentinela própria para "não existe" (`_NAO_EXISTE` com `NOT_FOUND_TTL`), e as
  duas semânticas de ausência — "a Steam respondeu que não existe" e "a Steam não
  respondeu" — não podem colapsar num helper só: a primeira é uma resposta, a
  segunda é um contratempo. Se `player_summary`/`vanity` passarem a custar
  backoff de forma perceptível, é ciclo SDD próprio.

- **CON-141**: **Nenhuma** falha da camada `ai/` é guardada —
  `AiUnavailableError`, `AiRateLimitError` e `DicaSemOrcamento` ficam todas de
  fora, embora a chave `dica:{provedor}:{appid}:{apiname}` seja servida pelo
  `_cached()`. Três razões, em ordem de peso:
  1. **Não há backoff a economizar.** `app/ai/base.py` não retenta e não dorme:
     tem apenas um `TokenBucket`. A espera de 3,5 s que motiva esta spec existe
     só em `SteamClient._get()`.
  2. **Guardar `AiRateLimitError` seria uma regressão.** Ele é levantado por duas
     fontes indistinguíveis pelo tipo: o 429 do SDK e a recusa do **token bucket
     local** (`base.py`). O bucket **se recupera sozinho** por refill (com
     `ai_rate_per_minute=2.0`, em ~30 s). Guardá-lo por `FALHA_TTL` converteria um
     bloqueio auto-resolvido em ~30 s num bloqueio garantido de 60 s — na única
     feature paga do app.
  3. **`DicaSemOrcamento` é gate, não falha de fetch.** Não toca a rede, não
     retenta, e só se restabelece no dia seguinte — muito além de `FALHA_TTL`.

  Consequência aceita: uma Anthropic/Gemini em 5xx continua sendo re-consultada a
  cada clique. Custo real disso é **zero em dinheiro** (a chamada falha antes de
  gerar token) e a latência é a do SDK, não a de um backoff nosso. Se a camada
  `ai/` **ganhar** retry com backoff no futuro, este CON deve ser reaberto — e o
  GUD-140 diz como decidir.

- **CON-142**: A sentinela de falha **nunca** pode ser devolvida a um chamador
  nem escapar do `_cached()` como valor. Um chamador que receba a sentinela como
  se fosse dado produziria erro de tipo em produção, longe da causa.

- **CON-143**: Nenhum contrato externo muda. As rotas continuam mapeando
  `SteamRateLimitError` → 429, `SteamUnavailableError` → 502 e as demais como
  hoje; os modelos de `app/schemas/models.py` não mudam; o SPA não muda e
  `npm run generate:api` **não** precisa ser rodado.

- **CON-144**: O comportamento best-effort de `_fill_counts` é preservado: um
  jogo cuja conquista falhou (agora vindo do cache) continua sem `percent`,
  `achieved_count` e `total_count`, e **não** derruba a biblioteca.

- **CON-145**: Três chamadores nunca chegam a levantar do `fetch`, por mecanismos
  **diferentes** — a distinção importa porque só o primeiro grupo é decisão do
  service:
  - `_global_percentages` e `_schema_en` capturam `SteamError` **dentro do
    próprio `buscar()`** e devolvem `{}`, gravado com seus TTLs de miss curtos já
    existentes;
  - `_app_genres` não captura nada: quem engole é o **client**
    (`SteamClient.get_app_genres` devolve `[]` em qualquer falha e nunca levanta),
    porque o endpoint da loja é não-oficial e instável.

  Em nenhum dos três a sentinela é acionada, e nada neles deve ser alterado. Isto
  é constatação, não requisito — não escrever código para forçá-lo. `_schema`
  (pt-BR), ao contrário do seu irmão `_schema_en`, **propaga** e portanto é
  coberto pela guarda.

### Segurança

- **SEC-140**: A mensagem da exceção registrada é a mesma que já seria exibida
  hoje. A sentinela **não** pode acrescentar à mensagem nenhum dado que ela já
  não tivesse — em particular, nada de `steamid`, `appid`, URL de chamada ou
  chave de API. O cache guarda tipo e mensagem, não contexto de requisição.

### Diretrizes

- **GUD-140**: Ao acrescentar uma exceção ao conjunto do REQ-142, o teste é
  único: **o fetch que a levanta paga retry com backoff?** Se sim, guardar
  economiza latência real. Se não, guardar só atrasa a recuperação sem ganho.
  Não usar "é transitória?" como critério isolado — é ambíguo o bastante para
  justificar qualquer inclusão, e foi o que produziu o erro da v1.0 desta spec.
  Verificação mecânica: abrir o caminho de código e procurar um `sleep` de
  backoff. Hoje ele existe em **um** lugar (`SteamClient._sleep`).
  Contra-indicação adicional: se a exceção puder vir de um **gate local que se
  recupera por si** (token bucket, orçamento), guardá-la prolonga o bloqueio em
  vez de encurtar a espera — exclusão, não inclusão.

- **PAT-140**: A guarda vive no helper compartilhado, não em cada chamador. Uma
  guarda em `_cached()` cobre os sete chamadores atuais e todos os futuros; N
  guardas nos chamadores deixam cada novo chamador quebrado por omissão.

## 4. Interfaces & Data Contracts

### Assinatura pública

Inalterada. `_cached()` é interno ao service e sua assinatura não muda:

```python
async def _cached(self, key: str, ttl: int | Callable[[Any], int], fetch): ...
```

### Estado interno gravado no `TTLCache`

| Situação | Valor gravado | TTL |
|---|---|---|
| Sucesso (`value is not None`) | o próprio valor | `ttl` (ou `ttl(value)`) |
| Sucesso com `value is None` | nada é gravado | — |
| Falha do REQ-142 | sentinela de falha carregando **tipo** e **mensagem** | `FALHA_TTL` |
| Falha fora do REQ-142 | nada é gravado | — |

### Matriz de comportamento por exceção

| Exceção levantada por `fetch` | Guardada? | Motivo |
|---|---|---|
| `SteamUnavailableError` | Sim | 5xx/rede em `_get()` — retentada, custa 3,5 s |
| `SteamRateLimitError` | Sim | 429 em `_get()` — retentada, custa 3,5 s; e re-bater numa Steam que pediu pausa é contraproducente |
| `SteamDataUnavailable` | Não | 401/403, **não** retentada (o `_get()` levanta na hora); guardar atrasaria em até 60 s o app perceber que o perfil virou público |
| `SteamProfileNotFound` | Não | corpo vazio, não retentada; e `_cached_ou_ausente` já trata este caso onde ele ocorre |
| `SteamVanityNotFound` | Não | idem |
| `AiUnavailableError` | Não | a camada `ai/` não retenta e não dorme — não há backoff a economizar (CON-141) |
| `AiRateLimitError` | Não | idem, e pode vir do token bucket local, que se recupera por refill: guardar **prolongaria** o bloqueio (CON-141) |
| `DicaSemOrcamento` | Não | gate, não falha de fetch; não toca a rede (CON-141) |
| `DicaIndisponivel` | Não | ausência é a resposta, não falha; não toca a rede |
| Qualquer outra | Não | conjunto fechado (REQ-142) |

Regra de bolso equivalente à tabela: **guarda-se o que passou por
`SteamClient._get()`, e nada mais.**

### Tabela de TTLs — linha nova

A tabela de TTLs da spec de arquitetura ganha uma linha que **não é por chave, e
sim por natureza do resultado**:

| Constante | Valor | Aplica-se a |
|---|---|---|
| `FALHA_TTL` | 60 s | Falha transitória em **qualquer** chave servida por `_cached()` |

## 5. Acceptance Criteria

- **AC-140**: Given um `fetch` que levanta `SteamUnavailableError`, When
  `_cached()` é chamado duas vezes com a mesma chave dentro de `FALHA_TTL`, Then
  o `fetch` é invocado **exatamente uma vez**.

- **AC-141**: Given a situação do AC-140, When a segunda chamada ocorre, Then ela
  levanta `SteamUnavailableError` — e **não** devolve `None`, `[]` ou a
  sentinela.

- **AC-142**: Given uma falha registrada, When o relógio injetado avança além de
  `FALHA_TTL`, Then a chamada seguinte invoca o `fetch` novamente.

- **AC-143**: Given um `fetch` que levanta `SteamDataUnavailable`, When
  `_cached()` é chamado duas vezes com a mesma chave, Then o `fetch` é invocado
  **duas** vezes e ambas levantam `SteamDataUnavailable`.

- **AC-144**: Given uma falha registrada em uma chave, When o `fetch` seguinte
  (após `FALHA_TTL`) tem sucesso, Then o valor é devolvido, gravado com o TTL do
  valor, e a chamada posterior o lê do cache sem invocar o `fetch`.

- **AC-145**: Given `game_detail(steamid, appid)` para um jogo cujo
  `player_ach:{steamid}:{appid}` tem falha registrada, When a rota responde,
  Then ela propaga a exceção (mapeada para 502/429 pelas rotas) e **não** devolve
  `supports_achievements: false` — o jogo quebrado não pode ser apresentado como
  jogo sem conquistas.

- **AC-146**: Given uma biblioteca em que exatamente um jogo levanta
  `SteamUnavailableError` e os demais estão em cache, When `list_library` é
  chamada duas vezes com `include=achievements`, Then na segunda chamada o client
  falso **não** recebe nenhuma chamada de conquistas, e o jogo em falha continua
  vindo com `percent: None`.

- **AC-147**: Given um `fetch` que levanta `SteamUnavailableError` para a chave
  `schema:{appid}` (cujo TTL de valor é `SCHEMA_TTL`, 24 h), When o relógio avança
  61 s, Then a chamada seguinte invoca o `fetch` novamente — a falha expira por
  `FALHA_TTL`, nunca pelo TTL do valor. Este é o teste que trava a
  independência do REQ-143.

- **AC-148**: Given um `fetch` que levanta `AiRateLimitError` para a chave
  `dica:{provedor}:{appid}:{apiname}`, When `_cached()` é chamado duas vezes,
  Then o `fetch` é invocado **duas** vezes — nenhuma falha da camada `ai/` é
  guardada (CON-141). Este teste existe para que uma inclusão futura de
  `AiRateLimitError` no conjunto quebre um teste em vez de passar despercebida.

## 6. Test Automation Strategy

- **Níveis:** unitário no `AchievementsService`, com client falso escrito à mão.
  Nenhum teste desta spec toca a rede.
- **Framework:** `pytest` + `pytest-asyncio`, como o restante de `tests/`.
- **Padrão de dublê:** client falso escrito à mão (classe simples no próprio
  teste), contando invocações — nunca `mock.patch` sobre dependência interna,
  conforme o `CLAUDE.md` do projeto.
- **Controle de tempo:** relógio injetado no `TTLCache`
  (`TTLCache(now=lambda: agora)`), que já é testável por construção. **Não usar**
  `asyncio.sleep` nem `time.sleep` para atravessar o `FALHA_TTL`.
- **Interface pública:** os testes de AC-145 e AC-146 exercitam `game_detail` e
  `list_library`. Os de AC-140..144, AC-147 e AC-148 exercitam `_cached()` através
  de um chamador real (`_player_achievements`, `_schema`, `dica`), **nunca**
  invocando `_cached` diretamente — testar o helper por dentro fixaria detalhe de
  implementação e quebraria a regra de testes pela interface pública do
  `CLAUDE.md`.
- **Teste de regressão de escopo:** o AC-148 existe para falhar caso alguém
  reintroduza as exceções de IA no conjunto guardado. Não removê-lo por parecer
  redundante — ele é o guarda-corpo do erro que a v1.0 desta spec cometeu.
- **CI:** `uv run pytest` no job de backend do GitHub Actions, sem segredos novos.
- **Ordem RED/GREEN:** um AC por ciclo, na ordem AC-140 → AC-148. Proibido
  escrever mais de um teste antes de implementar.

## 7. Rationale & Context

**Por que no `_cached()` e não em `_player_achievements`.** O ponto medido é um
só (conquistas), mas a causa não é: qualquer chamador que pague backoff tem o
mesmo problema, e uma guarda por chamador deixa o próximo chamador quebrado por
omissão. O helper compartilhado é ao mesmo tempo o diff menor e a correção de
raiz (PAT-140).

**Por que a falha não pode virar `[]`.** Foi a descoberta que fechou o desenho.
`_fill_counts` engole a exceção (o jogo fica sem %), mas `game_detail` a
**propaga** — e usa `SteamDataUnavailable` para desempatar perfil privado de
conta inexistente. Além disso `[]` já tem significado ocupado em
`player_ach:{steamid}:{appid}`: "jogo sem conquistas" (CON-011). Colapsar falha
em `[]` faria o detalhe de um jogo momentaneamente fora do ar afirmar, com cara
de resposta bem-sucedida, que o jogo não tem conquistas — e ainda cacharia a
mentira por `ACH_TTL`. Daí o AC-145.

**Por que `FALHA_TTL` é independente do TTL do valor.** O `CLAUDE.md` já registra
o perigo na Dica: com TTL de 7 dias, cachear um 429 transitório congelaria o
painel quebrado por uma semana. Amarrar a falha ao TTL do valor reintroduziria
exatamente esse defeito nas chaves de TTL longo servidas pelo `_cached()` —
`schema` e `schema_en` (24 h), `genres` (7 dias), `global_pct` (24 h). Um TTL
próprio e curto é o que torna a guarda segura em chaves cujo valor é praticamente
estático. O AC-147 trava isso com a chave de 24 h.

**Por que nenhuma falha de IA é guardada.** Este é o ponto onde a v1.0 desta spec
estava errada, e o erro é instrutivo. A v1.0 aplicou o rótulo "transitória" às
exceções de IA por analogia com as da Steam, sem abrir o código: `app/ai/base.py`
não retenta e não dorme — só tem um `TokenBucket`. Sem backoff, guardar a falha
não economiza espera nenhuma; e no caso do `AiRateLimitError` vindo do bucket
local, que se recupera por refill em ~30 s, guardar por 60 s deixa o usuário
**mais** tempo bloqueado do que se nada fosse feito. Uma "otimização" que piora o
caso que ela diz melhorar é pior que a ausência dela, e ainda mais na única
feature que custa dinheiro. Daí o GUD-140 ter deixado de dizer "é transitória?" e
passado a exigir a verificação mecânica: procure o `sleep` de backoff no caminho
de código.

**Por que 60 s.** É o mesmo `NOT_FOUND_TTL` já em uso, pela mesma razão: janela
larga o bastante para absorver a rajada de uma carga de biblioteca (que dispara
dezenas de chamadas em segundos) e curta o bastante para que uma indisponibilidade
que terminou não fique visível. Não é número calibrado contra medição — é o
menor valor que resolve o caso medido, e deve ser revisto se o padrão de falha
observado mudar.

**Por que permanentes ficam de fora.** Elas não pagam backoff (401/403 e corpo
vazio não são retentados), então não há latência a economizar — e o único efeito
de guardá-las seria atrasar a recuperação: quem torna o perfil público e recarrega
esperaria até 60 s para o app concordar. Trocar zero ganho por um atraso visível
é ruim em qualquer direção.

**Por que uma instância nova a cada re-levantamento.** A sentinela vive até 60 s e
pode ser lida por dezenas de requisições nesse intervalo. `raise` da mesma
instância faz o Python encadear `__traceback__` a cada vez, e o objeto retido no
cache mantém vivos os frames encadeados. Guardar tipo e mensagem e construir uma
instância nova custa uma linha e não tem esse comportamento.

**Relação com o CON-011.** Esta spec **estende** o princípio do CON-011, não o
contradiz. O CON-011 diz "cacheie o 'não' quando o 'não' é uma resposta"; aqui o
que se cacheia não é uma resposta, é a **ausência de resposta** — e por isso ela
é lida de volta como exceção, e não como valor, e por isso tem TTL próprio.

**Custo de quota.** Estritamente negativo: a mudança só **remove** chamadas à
Steam e ao provedor de IA. Nenhum endpoint novo, nenhuma chamada nova.

## 8. Dependencies & External Integrations

### Sistemas Externos
- **EXT-001**: Steam Web API — já integrada; nenhuma chamada nova. A mudança
  reduz o número de requisições em cenário de falha.
- **EXT-002**: Provedor de IA ativo (Anthropic ou Gemini) — já integrado. Esta
  spec **não** altera o comportamento do caminho de IA: nenhuma falha dele é
  guardada (CON-141). Dependência listada apenas porque a chave da Dica é servida
  pelo helper alterado.

### Dependências de Infraestrutura
- **INF-001**: `TTLCache` em memória, volátil e por processo. Já existe, com
  relógio injetável e teto de entradas — nenhuma alteração é requerida nele.

### Dependências de Plataforma
- **PLT-001**: Python 3.12 / `asyncio`. Sem dependência nova; nenhum pacote é
  acrescentado ao `pyproject.toml`.

### Dependências de Dados
- Nenhuma. A feature não introduz persistência, não lê fonte de dados nova e não
  altera nenhum modelo de domínio.

## 9. Examples & Edge Cases

### Caso medido — carga da biblioteca com um jogo quebrado

```
# Antes
GET /api/users/{steamid}/games?include=achievements   (cache quente)
  ├─ 154 jogos: cache hit                      ~0,1 s
  └─ appid 1966720: 4 tentativas + backoff     ~4,5 s   ← re-pago a cada request
                                          total ~4,7 s

# Depois — primeira requisição idêntica; a partir da segunda, dentro de FALHA_TTL
GET /api/users/{steamid}/games?include=achievements
  ├─ 154 jogos: cache hit                      ~0,1 s
  └─ appid 1966720: sentinela → levanta na hora, fan-out engole  ~0 s
                                          total ~0,1 s
```

### Borda — falha seguida de sucesso na mesma chave

```
t=0    fetch levanta SteamUnavailableError  → sentinela gravada (60 s), exceção propaga
t=10   leitura                              → levanta SteamUnavailableError, fetch NÃO é chamado
t=61   leitura                              → sentinela expirou, fetch é chamado
t=61   fetch tem sucesso                    → valor gravado com ACH_TTL, devolvido
t=62   leitura                              → valor do cache, fetch NÃO é chamado
```

### Borda — a mesma chave, dois chamadores com tratamentos opostos

`player_ach:{steamid}:{appid}` com falha registrada:

- `list_library(include=achievements)` → `_fill_counts` captura `SteamError`,
  o jogo vem com `percent: None`. **200 OK.**
- `game_detail(steamid, appid)` → a exceção propaga, a rota mapeia para **502**.

As duas leituras usam a **mesma** entrada de cache e chegam a resultados
diferentes de propósito: a biblioteca é best-effort, o detalhe não pode mentir.

### Borda — falha em chave de TTL longo

`schema:{appid}` tem `SCHEMA_TTL` de 24 h. Uma `SteamUnavailableError` registrada
em `t=0` deixa de valer em `t=60`, **não** em `t=86400`. Uma Steam que voltou ao
ar em cinco minutos volta a ser consultada em até um minuto.

### Não-caso — a Dica e o resto da camada `ai/`

`dica:{provedor}:{appid}:{apiname}` é servida pelo `_cached()`, mas **nenhuma**
das suas falhas é guardada (CON-141). Duas chamadas com o provedor em 429 fazem
duas tentativas, como hoje:

```
t=0    AiRateLimitError (bucket local recusou)  → nada é gravado, exceção propaga → 429
t=30   bucket refez o token, leitura            → fetch é chamado, pode ter sucesso
```

Se a falha fosse guardada, a leitura de `t=30` levantaria mesmo com o bucket já
recuperado, e o usuário esperaria até `t=60`. É o cenário que a v1.0 desta spec
teria produzido.

### Não-caso — genres, global_pct e schema_en

`_global_percentages` e `_schema_en` capturam a falha dentro do próprio
`buscar()`; `_app_genres` recebe `[]` do client, que nunca levanta. Nos três, o
valor é gravado com o TTL de miss curto já existente e a sentinela nunca é
acionada. Nada neles deve ser alterado por esta spec (CON-145). `_schema`
(pt-BR) é o irmão que **não** engole e portanto **é** coberto pela guarda.

## 10. Validation Criteria

A implementação está conforme quando:

1. Todos os AC-140..148 têm teste correspondente e a suíte `uv run pytest` passa.
2. Nenhum teste existente foi **deletado** para acomodar a mudança. Testes
   reescritos são aceitáveis apenas se o comportamento esperado mudou de fato, e
   a mudança está justificada nesta spec ou no `ROADMAP.md`.
3. `_cached_ou_ausente()` permanece inalterado (CON-140).
4. Nenhum arquivo de `app/steam/`, `app/ai/`, `app/web/`, `app/schemas/` ou
   `frontend/` foi modificado (CON-143).
5. `pyproject.toml` não ganhou dependência (PLT-001).
6. A documentação foi atualizada no mesmo ciclo:
   - `spec/spec-architecture-steam-achievements.md`: CON-011 passa a remeter a
     esta spec para o caso "falha", e a tabela de TTLs ganha a linha `FALHA_TTL`;
   - `CLAUDE.md`: a seção de convenções de cache menciona a guarda de falha junto
     de `_cached()`/`_cached_ou_ausente()`;
   - `ROADMAP.md`: o item "Um jogo quebrado custa ~4,5 s em toda carga da
     biblioteca" sai de **Correções pendentes** e é marcado como entregue, com o
     número medido depois.
7. `/verify` no app real confirma a queda de latência na carga quente da
   biblioteca do perfil de demonstração. O número medido é registrado no
   `ROADMAP.md` — se a carga quente **não** cair para a ordem de 0,1 s, a causa
   presumida está errada e o ciclo não está concluído.

## 11. Related Specifications / Further Reading

- `spec/spec-architecture-steam-achievements.md` — CON-010 a CON-012 (política de
  cache e TTLs), REQ-053/054 (token bucket e teto de entradas), REQ-004 (fan-out
  best-effort da biblioteca).
- `spec/spec-design-dica-conquista-ia.md` — origem do `DICA_TTL` de 7 dias e do
  alerta sobre cachear 429 em chave de TTL longo, que esta spec generaliza no
  REQ-143.
- `spec/spec-design-provedor-de-ia-plugavel.md` — origem das exceções
  `AiUnavailableError` / `AiRateLimitError` / `DicaSemOrcamento` e do
  `TokenBucket` de `app/ai/base.py`, cuja ausência de retry é a razão do CON-141.
- `ROADMAP.md` — seção "Correções pendentes", item da latência, com a medição de
  origem.
- `docs/adr/0001-steam-client-unico.md` — por que a camada `steam/` é o único
  ponto HTTP, e por que a guarda não pertence a ela.
