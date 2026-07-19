---
title: Dica de Conquista por IA (Fase B, sem monetização) — Especificação de Comportamento
version: 1.0
date_created: 2026-07-18
last_updated: 2026-07-18
owner: rafa.limadalmagro
tags: [backend, frontend, ia, anthropic, achievements, detalhe, custo]
---

# Introduction

Especificação da **Fase B** do projeto: um agente de IA que busca na web e
sintetiza *como obter* uma conquista pendente, exibido sob demanda no detalhe do
jogo. Alvo: **v0.0.4**.

O ciclo anterior (`spec-design-guia-conquista-pendente.md`) entregou dois links
determinísticos e o insumo `name_en`. Ele resolveu "para onde eu vou procurar".
Esta iteração resolve o que a §7 daquela spec identificou como o único ganho real
do agente sobre os links: **sintetizar** — ler o guia 100% de 40 páginas e
extrair a seção daquela conquista, em vez de entregar o usuário a uma busca.

**Esta spec reverte deliberadamente uma parte da §10.1 daquela spec.** A §10.1
registrou a Fase B como serviço pago via Stripe, reabrindo três invariantes
(login/multiusuário, banco, webhook). Esta iteração **não** monetiza e **não**
reabre nenhum dos três — ver §7 e o ADR-0002. A monetização permanece registrada
como intenção futura, sem data e sem escopo.

Estende os REQ-090..100; ocupa a numeração REQ-110+ no mesmo espaço.

## 1. Purpose & Scope

**Propósito:** definir o comportamento observável do acesso à dica de conquista
gerada por IA, de forma não ambígua, suficiente para implementação via TDD sem
novas perguntas.

**No escopo:**

- Endpoint JSON `GET /api/users/{steamid}/games/{appid}/achievements/{apiname}/dica`.
- Serviço que chama a API Anthropic com a ferramenta server-side de busca web e
  devolve texto sintetizado + fontes citadas.
- Cache `dica:{appid}:{apiname}`, compartilhado entre visitantes.
- Gate duplo contra abuso da chave paga: validação contra a biblioteca +
  token bucket próprio para o LLM.
- Configuração por ambiente da chave (`ANTHROPIC_API_KEY`) e do modelo
  (`AI_MODEL`).
- Botão + painel expansível no `AchievementItem`, **ao lado** do link existente.

**Fora do escopo (não implementar nesta iteração):**

- **Qualquer monetização**: Stripe, assinatura, checkout, webhook de pagamento,
  gate de assinante. Ver §7 e ADR-0002.
- **Login, multiusuário, identidade persistente.** O `steamid` continua vindo da
  URL pública e continua não autenticando ninguém.
- **Persistência de qualquer natureza.** Sem banco, sem arquivo em disco, sem
  Redis. O `TTLCache` volátil é o único cache (CON-115).
- **Streaming (SSE)** da resposta. One-shot, ver §7.
- **Personalização pelo progresso do jogador.** A dica é função de
  (jogo, conquista), nunca de quem pergunta (CON-111).
- Remoção ou alteração do link "Como conseguir" (YouTube) e do link de guias da
  comunidade. Ambos permanecem intactos.
- Dica em conquista **obtida** — não há problema a resolver ali.
- Pipeline próprio de retrieval (API de busca de terceiros, scraping, chunking).
  Ver §7.

**Audiência:** o desenvolvedor/agente que implementará a mudança.

**Premissas:**

- `Achievement.name_en` já existe no contrato da API
  (`app/schemas/models.py:71`) e é o insumo de busca do agente.
- `game_detail` já popula `owned_games:{steamid}` e `player_ach:{steamid}:{appid}`
  no cache; o gate de validação (REQ-116) lê **essas mesmas entradas** e não
  introduz chamada nova à Steam.
- As exceções tipadas vivem em `app/errors.py` e o mapa
  exceção → status HTTP vive em `app/web/routes.py`.
- O padrão de token bucket já existe em `app/steam/client.py:20` (`_TokenBucket`).

## 2. Definitions

| Termo | Definição |
|---|---|
| **Dica** | O texto sintetizado por IA explicando como obter **uma** conquista específica. Sempre este termo — nunca "guia". |
| **Guia** | Reservado ao corpus da Steam (guias da comunidade, por jogo), já linkado pelo REQ-098. **Não** é a Dica. |
| **Fase B** | Nome histórico desta feature na `spec-design-guia-conquista-pendente.md` §10.1. |
| **Fonte** | URL citada pela ferramenta de busca web, exibida junto da Dica para conferência. |
| **Busca web server-side** | Ferramenta `web_search_20250305` da API Anthropic, executada na infraestrutura da Anthropic dentro da mesma chamada. |
| **Payload mínimo** | Corpo de requisição que omite `thinking` e `output_config.effort` e usa a variante básica de busca, sendo por isso válido em todos os modelos configuráveis (CON-113). |
| **Gate** | Conjunto de verificações que impedem que input público converta-se em chamada paga (REQ-116, REQ-117). |
| **`apiname`** | Identificador estável da conquista na Steam (ex.: `ACH_SPA`). Não é o texto exibido. |

## 3. Requirements, Constraints & Guidelines

### Backend — serviço e integração

- **REQ-110**: O serviço deve expor um método que, dado `appid` e a conquista,
  devolva uma Dica composta por texto sintetizado e lista de fontes.
- **REQ-111**: A Dica deve ser obtida em **uma única chamada** à API Anthropic,
  usando a ferramenta de busca web server-side. Nenhuma outra chamada de rede
  para conteúdo é permitida.
- **REQ-112**: O prompt enviado deve conter **apenas** o nome do jogo e o
  `name_en` da conquista. Nenhum dado do jogador entra no prompt.
- **REQ-113**: Se a conquista não tiver `name_en` (`None`), o serviço **não** deve
  chamar a API paga; a rota devolve 404 com mensagem em pt-BR.
- **REQ-114**: A Dica deve ser cacheada em `dica:{appid}:{apiname}` via o helper
  `_cached()`, com TTL de 7 dias (`DICA_TTL = 604_800`).
- **REQ-115**: Falha na chamada à API Anthropic deve levantar exceção tipada
  própria, **propagada** — nunca engolida. A Dica **é** o endpoint; devolver
  vazio silenciosamente é pior que devolver erro.

### Backend — gate contra abuso

- **SEC-110**: A `ANTHROPIC_API_KEY` só pode existir em env/`.env`. Nunca em
  resposta da API, log, bundle do frontend ou commit.
- **REQ-116**: Antes de qualquer chamada paga, o serviço deve validar que o
  `appid` está na biblioteca do `steamid` **e** que o `apiname` corresponde a uma
  conquista **pendente** (`achieved == False`) daquele jogo. Falha em qualquer
  uma das condições ⇒ 404, sem chamada paga.
- **REQ-117**: Toda chamada à API Anthropic deve passar por um token bucket
  global no cliente de IA, configurável por `ai_rate_per_minute` /
  `ai_rate_burst`. Estourou ⇒ exceção tipada ⇒ 429.
- **SEC-111**: O gate do REQ-116 é **boundary de segurança**, não otimização.
  Ele deve rodar antes da consulta ao cache e antes da chamada, e não pode ser
  contornado por parâmetro de query.

### Backend — configuração

- **REQ-118**: `Settings` deve ganhar `anthropic_api_key: str`,
  `ai_model: str = "claude-haiku-4-5"`, `ai_rate_per_minute: float` e
  `ai_rate_burst: int`.
- **CON-110**: O modelo é trocável **apenas** por variável de ambiente. Não deve
  existir parâmetro de query, header ou campo de request que escolha modelo —
  input público não decide onde o dinheiro é gasto.

### Restrições de arquitetura e custo

- **CON-111**: A chave de cache é `dica:{appid}:{apiname}` — sem `steamid`. A
  Dica é a mesma para todo visitante e o cache é compartilhado, como
  `global_pct:{appid}` e `schema_en:{appid}`.
- **CON-112**: O `steamid` da rota serve **exclusivamente** ao gate do REQ-116.
  Ele não entra na chave de cache nem no prompt.
- **CON-113**: O corpo da requisição à API Anthropic deve ser o **payload mínimo**:
  sem `thinking`, sem `output_config.effort`, com `web_search_20250305`. Esse
  shape é aceito por `claude-haiku-4-5`, `claude-sonnet-5` e `claude-opus-4-8`
  igualmente, então `AI_MODEL` troca por string sem branch no código.
- **CON-114**: **Proibido** montar matriz de capacidade por modelo. Ver §7.
- **CON-115**: O cache continua sendo o `TTLCache` volátil, com teto de entradas.
  Nenhuma persistência é introduzida.
- **CON-116**: A camada de IA vive em `app/ai/` e é a **única** que fala HTTP com
  a Anthropic — espelho exato do papel de `app/steam/`. `services/` não importa o
  SDK; `web/` não conhece a Anthropic.

### Frontend

- **REQ-118a**: A Dica é apresentada ao usuário sob a persona **NPC**
  (ver `CONTEXT.md`). A persona vive **só na camada de apresentação** — copy do
  painel, do botão, do carregamento e das mensagens do `_ERROR_MAP`. O
  vocabulário de domínio (`Dica`, `dica:{appid}:{apiname}`, `DicaIndisponivel`,
  rota `/dica`) **não** muda, e o `_prompt` enviado ao modelo **não** ganha voz
  em personagem: voz compete com precisão, que é a única razão da feature
  existir.
- **SEC-113**: O painel deve declarar que o texto foi escrito por um **modelo de
  IA**, junto ao nome da persona. Não é preferência de tom: a `Fonte` só existe
  porque o modelo pode errar, e uma persona sem esse marcador lê como alguém que
  *sabe* — a confiança deixa de ser condicional. Coberto por teste próprio em
  `AchievementItem.test.tsx`.
- **REQ-119**: O `AchievementItem` deve exibir, **somente** em conquista pendente
  com `name_en`, um controle que dispara a busca da Dica sob demanda. Nada é
  buscado no carregamento da página.
- **REQ-120**: Enquanto a Dica carrega, exibir skeleton. Ao chegar, exibir o
  texto e as fontes como links externos.
- **REQ-121**: O link "Como conseguir" (YouTube) permanece **inalterado** e
  visível, independentemente do estado da Dica.
- **REQ-122**: Erro ao buscar a Dica deve exibir a mensagem `detail` da API e
  manter o link YouTube utilizável como alternativa.
- **SEC-112**: Todo link de fonte deve usar `rel="noopener noreferrer"` e
  `target="_blank"`.

### Padrões

- **PAT-110**: Dado novo da API ⇒ método em `src/api/client.ts` + hook React
  Query; a UI consome o hook. Sem exceção.
- **PAT-111**: A Dica é buscada com `enabled: false` até o clique (ou hook
  disparado sob demanda) — nunca em `useEffect` no mount.
- **GUD-110**: Comentários e mensagens ao usuário em pt-BR.
- **GUD-111**: A escolha do payload mínimo deve ser marcada no código com um
  comentário `ponytail:` nomeando o teto e o caminho de upgrade.

## 4. Interfaces & Data Contracts

### Modelo de domínio (novo)

```python
class Fonte(BaseModel):
    """URL citada pela busca web, para o usuário conferir a Dica."""
    title: str
    url: str


class Dica(BaseModel):
    """Síntese de IA sobre como obter uma conquista pendente."""
    # Markdown simples. Escrito em pt-BR pelo modelo.
    texto: str
    fontes: list[Fonte]
```

### Endpoint

| Método | Caminho |
|---|---|
| `GET` | `/api/users/{steamid}/games/{appid}/achievements/{apiname}/dica` |

**Resposta 200** — `Dica`:

```json
{
  "texto": "Spa Healer é obtida ao usar a fonte termal em ...",
  "fontes": [
    { "title": "Nioh 100% Achievement Guide", "url": "https://steamcommunity.com/..." }
  ]
}
```

**Contrato de erro** — `{"detail": "<mensagem pt-BR>"}`:

| Status | Quando |
|---|---|
| 404 | Jogo fora da biblioteca, conquista inexistente, conquista já **obtida**, ou `name_en` ausente (REQ-113, REQ-116) |
| 429 | Token bucket de IA estourado (REQ-117) ou rate limit da Anthropic |
| 502 | Falha da API Anthropic (REQ-115) |
| 422 | Parâmetro inválido na URL (handler existente) |

### Configuração (env)

| Variável | Default | Descrição |
|---|---|---|
| `ANTHROPIC_API_KEY` | — (obrigatória) | Segredo. Só env. |
| `AI_MODEL` | `claude-haiku-4-5` | ID do modelo. Trocável sem alterar código (CON-113). |
| `AI_RATE_PER_MINUTE` | `10` | Teto sustentado de chamadas pagas. |
| `AI_RATE_BURST` | `20` | Rajada absorvida. |

### Chave de cache

| Chave | TTL | Compartilhada? |
|---|---|---|
| `dica:{appid}:{apiname}` | `DICA_TTL = 604_800` (7 dias) | Sim — entre todos os visitantes |

## 5. Acceptance Criteria

- **AC-110**: Given uma conquista pendente com `name_en` num jogo da biblioteca,
  When o endpoint da Dica é chamado, Then a resposta é 200 com `texto` não vazio
  e `fontes` como lista.
- **AC-111**: Given a mesma conquista já consultada e dentro do TTL, When o
  endpoint é chamado de novo, Then **nenhuma** chamada à API Anthropic ocorre e a
  resposta vem do cache.
- **AC-112**: Given dois `steamid` diferentes que possuem o mesmo jogo, When ambos
  pedem a Dica da mesma conquista, Then a segunda requisição é servida do cache —
  a chave não contém `steamid`.
- **AC-113**: Given um `appid` que **não** está na biblioteca do `steamid`, When o
  endpoint é chamado, Then a resposta é 404 e **nenhuma** chamada paga ocorre.
- **AC-114**: Given uma conquista já **obtida**, When o endpoint é chamado, Then a
  resposta é 404 e nenhuma chamada paga ocorre.
- **AC-115**: Given uma conquista cujo `name_en` é `None`, When o endpoint é
  chamado, Then a resposta é 404 e nenhuma chamada paga ocorre.
- **AC-116**: Given o token bucket de IA esgotado, When o endpoint é chamado,
  Then a resposta é 429 e nenhuma chamada paga ocorre.
- **AC-117**: Given que a API Anthropic falha, When o endpoint é chamado, Then a
  resposta é 502 com `detail` em pt-BR, e o erro **não** é cacheado.
- **AC-118**: Given qualquer chamada ao serviço, When o corpo enviado à API
  Anthropic é inspecionado, Then ele não contém `steamid`, nem lista de
  conquistas do jogador, nem qualquer dado do jogador.
  *Coberto estruturalmente, não por teste próprio:* a assinatura
  `sintetizar(nome_do_jogo, name_en)` e a de `_prompt()` tornam impossível passar
  dado do jogador, e o AC-110 já assere o par exato recebido. Um teste que
  verificasse "o `steamid` não está no corpo" numa função que nunca recebe
  `steamid` passaria por construção — teatro, não verificação.
- **AC-119**: Given o `AI_MODEL` alterado para `claude-opus-4-8`, When o endpoint
  é chamado, Then a requisição é aceita sem alteração de código (payload mínimo,
  CON-113).
- **AC-120**: Given uma conquista pendente no detalhe do jogo, When o usuário
  abre a aba "Pendentes", Then **nenhuma** requisição de Dica é disparada até um
  clique explícito.
- **AC-121**: Given o clique no controle da Dica, When a resposta ainda não
  chegou, Then um skeleton é exibido; When chega, Then texto e fontes aparecem.
- **AC-122**: Given a Dica em qualquer estado (carregando, sucesso, erro), When o
  `AchievementItem` é renderizado, Then o link "Como conseguir" (YouTube) continua
  presente e funcional.
- **AC-123**: Given uma conquista **obtida**, When renderizada, Then nenhum
  controle de Dica é exibido.

## 6. Test Automation Strategy

- **Test Levels**: Unit (serviço, cliente de IA, token bucket), Integration
  (rotas via `TestClient`), Component (frontend via Vitest).
- **Frameworks**: `pytest` (backend), Vitest + Testing Library (frontend).
- **Test Data Management**: cliente de IA **falso escrito à mão**, injetado por
  construtor, no padrão de `tests/test_service.py`. Proibido `mock.patch` em
  dependência interna. O SDK da Anthropic é boundary externo real — se precisar
  ser substituído, é no limite HTTP, nunca no serviço.
- **Coverage Requirements**: todo AC-110..AC-123 tem teste automatizado
  correspondente.
- **Custo**: **nenhum teste pode chamar a API Anthropic de verdade.** Um teste que
  gasta dinheiro ao rodar `uv run pytest` é um defeito.
- **CI/CD Integration**: `uv run pytest` e `npm run test` verdes antes do ship.

## 7. Rationale & Context

### Por que sem monetização, revertendo a §10.1

A §10.1 da spec anterior registrou a Fase B como serviço pago via Stripe. Ao
planejar a v0.0.4 ficou claro que aquilo constrói a **catraca antes do show**:

| | Só o agente (esta spec) | Agente + Stripe |
|---|---|---|
| Invariantes reabertos | nenhum | login, multiusuário, banco |
| Superfície de entrada nova | 1 endpoint autenticado por gate | + webhook HMAC público |
| Trabalho que é IA | quase todo | minoria — a maior parte é cobrança |
| Pré-requisito de negócio | nenhum | alguém disposto a pagar |

O app tem **um** usuário e nenhuma evidência de demanda. Monetizar exige saber
*quem paga*, o que é identidade persistente — e o `steamid` vem da URL pública,
é forjável, e não autentica ninguém. Construir isso agora é dívida sem receita.
A decisão está registrada no **ADR-0002**, com gatilho explícito para reabrir.

### Por que o disparo condicional da §9 anterior foi considerado satisfeito

A §9 da spec anterior condicionava a Fase B a "evidência de que abrir o guia 100%
custa tempo real". Essa medição não existe e não vai existir num app de um
usuário sem telemetria. O critério foi substituído por um julgamento explícito do
dono: o clique atual custa tempo o bastante para justificar ~$4/mês. Registrar
isso é honesto; fingir que houve medição não seria.

### Por que busca web da própria API, e não pipeline próprio

A alternativa "modelo open source barato" economiza tokens e custa um subsistema:

| | Busca web server-side | Pipeline próprio |
|---|---|---|
| Chamadas de rede | 1 | busca + N fetches + LLM |
| Dependências novas | nenhuma | API de busca + parser HTML |
| Segredos novos | 1 | 2 |
| Alucinação | mitigada por citação | mitigada por citação |
| Quebra quando | a API muda (versionada) | o HTML de terceiro muda (não versionado) |

A economia máxima estimada é ~$10/mês contra um parser para manter. É a mesma
troca que a §7 da spec anterior já recusou uma vez.

### Por que Haiku 4.5, e por que configurável

A tarefa é sumarização sobre texto recuperado, não raciocínio profundo — o teto
de capacidade não é o gargalo. Haiku é o piso barato **sem mudar arquitetura**:
mesma API, mesma busca embutida, mesma chamada única. Se a síntese ficar rasa em
conquista obscura, subir para Sonnet 5 ou Opus 4.8 é trocar uma string.

Custo assumido: Haiku 4.5 **não** suporta a variante `web_search_20260209` com
filtragem dinâmica. Sem ela, mais tokens de resultado chegam ao contexto, então o
custo por Dica é maior que a estimativa ingênua — ainda o mais barato disponível,
com margem menor.

### Por que payload mínimo e não matriz de capacidade

Os parâmetros válidos variam por modelo: `effort` e `thinking: adaptive` erram em
Haiku 4.5; a busca com filtragem dinâmica exige modelo mais novo. Uma matriz
modelo → parâmetros extrairia o máximo de cada um, e desatualizaria a cada
lançamento da Anthropic — abstração especulativa para um app de um usuário que vai
trocar de modelo talvez uma vez. O payload mínimo é aceito por todos os três
modelos-alvo. O teto (deixar filtragem dinâmica e thinking na mesa) é consciente e
fica marcado no código.

### Por que one-shot e não streaming

Streaming melhora a percepção de latência **apenas do primeiro visitante de cada
conquista** — o resto lê do cache instantaneamente. O custo seria
`StreamingResponse` no FastAPI, um consumidor no frontend que não é React Query
(ela não faz streaming), tratamento de erro no meio do stream, e um cache que
guarda texto completo mas serve hit sem streamar. Diff grande por um ganho que
quase ninguém vê.

### Por que a Dica é genérica, não personalizada

Personalizar pelo progresso mudaria a chave para `dica:{steamid}:{appid}:{apiname}`
— cache por jogador, zero compartilhamento, custo multiplicado por visitante. E
o ganho não existe: "como pegar Spa Healer" não depende do resto da biblioteca.

### Por que o gate é duplo

`appid` e `apiname` vêm da URL. A validação contra a biblioteca limita **o que**
pode ser pedido e sai de graça (os dados já estão em cache para o detalhe). Ela
sozinha ainda permitiria varrer a biblioteca inteira — 500 jogos × 50 conquistas =
25 mil chamadas pagas. O token bucket limita **quão rápido**. Juntos, o pior caso
é "alguém paga lentamente pelas suas próprias conquistas pendentes".

### Por que "dica" e não "guia"

"Guia" já está ocupado: o REQ-098 linka os *guias da comunidade Steam*, um corpus
por jogo. Chamar a síntese de IA de "guia" faria `guide:{appid}:{apiname}` e
"guias da comunidade" coexistirem com sentidos diferentes no mesmo módulo.

### Custos assumidos conscientemente

1. **Custo em dinheiro por Dica não cacheada.** Primeira vez que o projeto tem
   custo marginal por request.
2. **Cache volátil sobre dado pago.** Todo restart do processo joga fora Dicas já
   compradas. Aceito porque o volume é de um usuário; o gatilho para reavaliar é a
   fatura, não a estética.
3. **Mais um alvo de toque por conquista pendente**, somando aos ~90 tab stops que
   a §7 anterior já contabilizou na aba "Pendentes" de um jogo grande.
4. **Latência de segundos** no primeiro acesso de cada conquista, sem streaming.

## 8. Dependencies & External Integrations

### External Systems

- **EXT-110**: API Anthropic (`/v1/messages`) — geração da Dica com ferramenta de
  busca web server-side. Única fonte de conteúdo sintetizado.
- **EXT-111**: Steam Web API — já integrada; **nenhuma chamada nova** é
  introduzida por esta spec (o gate lê o cache existente).

### Third-Party Services

- **SVC-110**: Anthropic Messages API — requer chave de API válida; erro de
  autenticação, rate limit e indisponibilidade devem virar exceções tipadas
  mapeadas para 502/429.

### Infrastructure Dependencies

- **INF-110**: Egress HTTPS do container do backend para a API Anthropic.
- **INF-111**: `TTLCache` em memória, por processo. Sem infraestrutura nova.

### Data Dependencies

- **DAT-110**: `Achievement.name_en` — insumo obrigatório do prompt. Ausente ⇒
  sem chamada paga (REQ-113).
- **DAT-111**: `owned_games:{steamid}` e `player_ach:{steamid}:{appid}` no cache —
  insumos do gate (REQ-116).

### Technology Platform Dependencies

- **PLT-110**: SDK oficial `anthropic` para Python, cliente assíncrono, coerente
  com o `async` em I/O já adotado no projeto.

### Compliance Dependencies

- **COM-110**: `ANTHROPIC_API_KEY` sujeita à mesma disciplina de segredo da
  `STEAM_API_KEY` (SEC-001 da spec de arquitetura): nunca no bundle, no log ou em
  resposta.

## 9. Examples & Edge Cases

```python
# REQ-115 — a Dica *é* o endpoint: o erro propaga, e nada é cacheado.
# Contraste deliberado com _global_percentages, onde o except devolve {} porque
# raridade é decoração. Aqui, engolir a falha entregaria um painel vazio sem
# explicação — pior que um 502 que o frontend sabe exibir.
# A assinatura espelha `game_detail(steamid, appid)`: recebe identificadores da
# URL e resolve tudo internamente, para a rota só orquestrar. Passar um
# `Achievement` já montado obrigaria a rota a construir o detalhe inteiro para
# pedir uma dica.
async def dica(self, steamid: str, appid: int, apiname: str) -> Dica:
    # A ORDEM dos gates é requisito, não estilo: cada etapa abaixo custa mais que
    # a anterior. Biblioteca primeiro porque é a única que limita o espaço de
    # `appid`; sem ela, `_player_achievements` e `_schema_en` já gastariam uma
    # ida à Steam com input público para descobrir que a resposta é não.
    owned = await self._owned_games(steamid)
    jogo = next((g for g in owned if g["appid"] == appid), None)
    if jogo is None:
        raise DicaIndisponivel(...)

    player = await self._player_achievements(steamid, appid)
    entry = next((p for p in player or [] if p.apiname == apiname), None)
    if entry is not None and entry.achieved:
        raise DicaIndisponivel(...)

    name_en = ...  # de `_schema_en(appid)`
    if name_en is None:
        raise DicaIndisponivel(...)

    # _cached() e não _cached_ou_ausente(): aqui erro é erro. Cachear o "falhou"
    # transformaria um 429 transitório da Anthropic em 7 dias de painel quebrado.
    return await self._cached(
        f"dica:{appid}:{apiname}",
        DICA_TTL,
        lambda: self._ai.sintetizar(jogo["name"], name_en),
    )
```

```python
# CON-113 — payload mínimo. Sem `thinking`, sem `output_config.effort`, busca
# básica: aceito por haiku-4-5, sonnet-5 e opus-4-8 igualmente.
# ponytail: teto conhecido — em modelo novo, deixa filtragem dinâmica
# (web_search_20260209) e adaptive thinking na mesa. Upgrade: quando AI_MODEL
# apontar para um modelo novo *de forma permanente*, aí sim vale ramificar.
resposta = await self._client.messages.create(
    model=self._model,          # AI_MODEL — troca por env, sem branch
    max_tokens=1024,
    tools=[{"type": "web_search_20250305", "name": "web_search"}],
    messages=[{"role": "user", "content": prompt}],
)
```

### Edge cases

| Caso | Comportamento esperado |
|---|---|
| Conquista pendente, `name_en` presente, jogo na biblioteca | 200 com Dica; primeira vez chama a API, demais leem cache |
| Conquista **obtida** | 404, sem chamada paga (AC-114) |
| `name_en == None` | 404, sem chamada paga (AC-115) |
| `appid` válido mas fora da biblioteca do `steamid` | 404, sem chamada paga (AC-113) |
| `apiname` inexistente naquele jogo | 404, sem chamada paga |
| `steamid` de perfil privado (`player_ach` indisponível) | 404 — o gate não consegue afirmar que a conquista é pendente, então não gasta |
| Cache da biblioteca frio (deep-link) | O gate popula `owned_games`/`player_ach` pelo caminho já existente antes de decidir; só então libera |
| API Anthropic em 429 | 429 ao cliente; **nada** é cacheado; próxima tentativa re-tenta |
| API Anthropic em 5xx / timeout | 502 ao cliente; nada cacheado |
| Token bucket de IA esgotado | 429 antes de qualquer I/O com a Anthropic (AC-116) |
| Busca web não acha nada útil | 200 com `texto` explicando que não encontrou e `fontes: []`. **É resposta válida e é cacheada** — re-perguntar não muda o resultado e custa de novo |
| Dois visitantes pedem a mesma Dica simultaneamente | Ambos podem chamar a API (sem lock). Aceito: janela estreita, custo de uma chamada extra. `ponytail:` marca o teto |
| `AI_MODEL` apontando para modelo inexistente | Erro na primeira chamada ⇒ 502. Env var é input do dono, não público — falha alta e visível é o comportamento certo |

## 10. Validation Criteria

- Todos os AC-110..AC-123 têm teste automatizado e passam.
- `uv run pytest` e `npm run test` verdes.
- `rg -i "stripe|checkout|subscription|webhook" app/ frontend/src/` não retorna
  nada — o "fora de escopo" de monetização.
- `rg "dica:" app/services/achievements.py` mostra a chave **sem** `steamid` —
  CON-111.
- `rg -n "anthropic" app/web/ app/services/` não retorna import do SDK — CON-116.
- Um teste prova que o corpo enviado à Anthropic não contém `steamid` — AC-118.
- Nenhum teste faz I/O real com a Anthropic (`rg "ANTHROPIC_API_KEY" tests/`
  vazio).
- `CLAUDE.md` lista `dica:{appid}:{apiname}` entre as chaves de cache e documenta
  `app/ai/` no diagrama de arquitetura.
- `frontend/src/api/types.gen.ts` contém `Dica` e `Fonte` — após
  `npm run generate:api`.
- Todo link de fonte casa `rel=.*noopener` — SEC-112.
- `/verify`: numa conquista pendente real, o controle aparece, o clique traz a
  Dica com fontes clicáveis, o link YouTube continua lá, e a conquista obtida ao
  lado **não** mostra controle nenhum.

## 11. Related Specifications / Further Reading

- `spec/spec-design-guia-conquista-pendente.md` — REQ-090..100, o `name_en` que
  esta spec consome, a §7 que rejeitou a IA no ciclo anterior, e a §10.1 que esta
  spec reverte parcialmente.
- `spec/spec-architecture-steam-achievements.md` — SEC-001 (segredo nunca sai do
  backend), contrato de erro, invariante de camadas que `app/ai/` espelha.
- `docs/adr/0002-fase-b-sem-monetizacao.md` — por que Stripe/login/banco ficaram
  fora, e o gatilho para reabrir.
- `docs/adr/0001-steam-client-unico.md` — precedente de "não partir sem seam
  real", que informa a decisão de `app/ai/` ser uma camada só.
- `CLAUDE.md` — disciplina de cache, `_MAXSIZE`, token bucket, e "Antes de propor
  mudanças grandes".
