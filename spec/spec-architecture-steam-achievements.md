---
title: App Web de Conquistas Steam — Especificação de Comportamento
version: 2.0
date_created: 2026-06-28
last_updated: 2026-07-12
owner: rafa.limadalmagro
tags: [architecture, design, app, steam, fastapi, react]
---

# Introduction

Especificação de comportamento de um app web para acompanhar biblioteca, tempo de
jogo e progresso de conquistas de uma conta Steam. A consulta é em **tempo real**
contra a Steam Web API (**sem banco de dados**). Arquitetura **fullstack**:
backend FastAPI expõe **API JSON** sob `/api`; frontend é um **SPA React** (Vite +
Tailwind + shadcn/ui) consumindo a API via **TanStack React Query**. Em produção o
FastAPI serve o build estático do SPA; em dev o Vite serve o front com proxy
`/api` → FastAPI. Esta spec é a fonte de verdade da fase SDD e precede o PLAN e o
ciclo RED/GREEN/REFACTOR.

> **v2.0** — a v1.x descrevia um app server-rendered (Jinja2, rota `GET /`,
> `STEAM_ID` via env, exposição só em localhost). Nada disso existe mais: o app é
> API JSON + SPA, o `steamid` vem da URL e o app está publicado. Esta versão
> corrige as seções defasadas e escreve os requisitos das features que já foram
> entregues sem nunca terem sido especificadas (REQ-050..054).

## 1. Purpose & Scope

**Propósito:** definir, de forma não ambígua, o comportamento observável do app —
rotas, ordenação, agrupamento, cálculo de progresso, filtros, cache, proteção de
quota e tratamento de erro — suficiente para outro agente implementar via TDD sem
fazer perguntas.

**No escopo:**
- Listar biblioteca + tempo de jogo (playtime).
- Detalhe de jogo: conquistas obtidas × pendentes, % de progresso, raridade global.
- Ordenação da biblioteca: playtime, nome, % concluído, nº de conquistas, última
  vez jogado.
- Agrupamento da biblioteca por gênero.
- Busca por nome (client-side) e filtro por status na página de detalhe.
- Perfil público do jogador (nome e avatar).

**Fora do escopo (não implementar):**
- Login Steam OpenID ou autenticação de qualquer tipo.
- Comparação entre jogos, histórico/snapshots, qualquer persistência relacional.
- Banco de dados, fila, Redis ou serviço de apoio com estado durável.

**Audiência:** o desenvolvedor/agente que implementará o app.

**Premissas:**
- `STEAM_API_KEY` válida disponível via env. **Não existe `STEAM_ID` em
  configuração** — o `steamid` é parâmetro de rota, informado por quem acessa.
- O app é **multiusuário de leitura, sem login**: qualquer visitante consulta
  qualquer SteamID. Isso é aceitável porque **todo dado exposto já é público na
  Steam** — a API só o reempacota. Perfil privado simplesmente não devolve dados.
- App roda em `uvicorn` com **1 worker** (o cache é estado em processo).
- **O app está publicado na internet** (SPA na Vercel, API em host Docker). Como o
  `steamid` é input público, o app **precisa** se defender: validação de entrada
  (REQ-052), teto de quota (REQ-053) e teto de memória do cache (REQ-054).

## 2. Definitions

- **Steam Web API**: API HTTP oficial da Valve para dados de jogadores/jogos.
- **appid**: identificador numérico de um jogo na Steam.
- **SteamID64**: identificador do jogador, **17 dígitos numéricos**.
- **playtime**: tempo total jogado (campo `playtime_forever`, em minutos).
- **conquista (achievement)**: objetivo do jogo; tem flag `achieved` (0/1).
- **schema (do jogo)**: metadados das conquistas (nome, descrição, ícone), obtidos
  via `GetSchemaForGame`.
- **% de progresso**: `conquistas_obtidas / total_conquistas * 100`.
- **raridade global**: % de **todos** os jogadores da Steam que obteve uma
  conquista. É por jogo, não por jogador.
- **fan-out**: disparo de N chamadas HTTP (uma por jogo) para montar uma visão.
- **TTLCache**: cache em memória com expiração por tempo (volátil, por processo).
- **token bucket**: teto de vazão de chamadas à Steam, para proteger a quota da
  chave.
- **SPA**: Single-Page Application (React; o HTML não é montado no servidor).
- **best-effort**: dado decorativo cuja falha é engolida — nunca derruba a página.
- **supports_achievements**: indica se o jogo tem sistema de conquistas.

## 3. Requirements, Constraints & Guidelines

### Funcionais — biblioteca e detalhe

- **REQ-001**: `GET /api/users/{steamid}/games` devolve os jogos da conta com
  nome, ícone e playtime, como JSON `list[Game]`.
- **REQ-002**: `GET /api/users/{steamid}/games` aceita o parâmetro de query `sort`
  com os valores: `playtime` (default), `name`, `percent`, `ach_count`,
  `last_played`. O vocabulário é declarado **uma única vez**, no domínio
  (`app/schemas/models.py`, como `Literal`), e usado tanto pela rota quanto pelo
  service — é assim que ele chega ao OpenAPI e, dali, aos tipos do SPA
  (`npm run generate:api`). Ausente ⇒ `playtime`. Valor **inválido ⇒ 422** (ver §4).
- **REQ-003**: `sort` **só ordena**. Nenhum valor de `sort` dispara chamada extra à
  Steam: sem `include`, a rota executa **uma única** chamada (`GetOwnedGames`).
  `sort=percent`/`ach_count` sem `include=achievements` é legal — os campos vêm
  `null` e a ordenação os trata como `0`, mantendo a lista estável.
- **REQ-004**: `GET /api/users/{steamid}/games` aceita o parâmetro de query
  `include`, **repetível**, com os valores `achievements` e `genres`. É o caller
  que declara os dados caros que quer; a rota **não os deduz** do `sort`.
  `include=achievements` executa fan-out de `GetPlayerAchievements` para todos os
  jogos e a resposta **inclui** o % e a contagem por jogo. O fan-out é
  **best-effort por jogo**: um jogo que falhe fica sem %, sem derrubar a lista.
  Valor inválido ⇒ **422**.
- **REQ-005**: `GET /api/users/{steamid}/games/{appid}` devolve a lista completa
  de conquistas do jogo, cada uma marcada como obtida ou pendente, com
  nome/descrição/ícone, além da contagem (obtidas/total) e do % de progresso.
- **REQ-006**: O % e a contagem derivam de `GetPlayerAchievements` (flag
  `achieved`). O schema **não** é necessário para o percentual, apenas para
  nome/descrição/ícone das conquistas.
- **REQ-007**: O filtro por status na página de detalhe é **client-side**,
  operando sobre a lista já carregada, sem nova chamada ao servidor/Steam.
- **REQ-008**: Jogo sem sistema de conquistas é tratado como
  `supports_achievements=False` e renderizado sem quebrar (mensagem informativa).
- **REQ-009**: O nome do jogo no detalhe vem da **biblioteca** (nome da loja)
  quando disponível em cache; o `gameName` do schema é apenas plano B, porque às
  vezes é o codinome interno do estúdio (ex.: `GFREMP2` para Remnant II). Último
  recurso: `App {appid}`.

### Funcionais — custo zero de quota

Requisitos que não acrescentam nenhuma chamada à Steam: derivam de campos que já
vêm nas respostas atuais ou de agregação client-side.

- **REQ-030**: O detalhe exibe a **data de desbloqueio** de cada conquista obtida
  (`unlocktime` do `GetPlayerAchievements`) e ordena a lista: obtidas primeiro, da
  mais recente para a mais antiga; pendentes depois, na ordem do schema.
  `unlocktime` ausente ou `0` numa conquista obtida ⇒ sem data (a Steam devolve
  `0` para desbloqueios muito antigos) — a conquista continua listada.
- **REQ-031**: A biblioteca oferece **busca por nome**, filtrando **client-side** a
  lista já carregada (mesmo princípio do REQ-007): zero chamadas ao servidor. A
  busca é estado efêmero da UI e **não** entra na URL — ao contrário de `sort` e
  `group`, que são estado **da URL do SPA** (`/u/{steamid}?sort=…&group=genre`).
  ⚠️ `group` é do SPA, **não** da API: quem agrupa é a Library, client-side. Para a
  API, o SPA traduz essa intenção em `include=genres` (REQ-004/REQ-050).
- **REQ-032**: A biblioteca exibe um **resumo agregado** do que está em tela: nº de
  jogos e horas totais. Quando os dados de conquista estiverem carregados
  (`include=achievements`), também o nº de jogos 100% concluídos. O resumo reflete
  a lista **após** a busca do REQ-031.
- **REQ-033**: O card do jogo exibe um badge de **jogado recentemente** quando o
  `GetOwnedGames` traz `playtime_2weeks`. O campo só aparece no payload quando
  houve jogo nas últimas duas semanas — a ausência é o caso normal, não erro.

### Funcionais — campo/endpoint novo

Requisitos que exigiram documentar campo ou endpoint antes de implementar (ver
`Steam_Web_API_Documentation.md`).

- **REQ-040**: O detalhe exibe a **raridade global** de cada conquista — o % de
  jogadores que a obteve — vinda de
  `ISteamUserStats/GetGlobalAchievementPercentagesForApp/v2` (parâmetro `gameid`),
  com junção por `apiname`. A UI mostra o % e marca como **rara** a conquista
  abaixo de 10%. É a única feature pós-v1.0 que **custa quota**: +1 chamada por
  jogo, cacheada em `global_pct:{appid}` — a chave é o **jogo**, não o jogador,
  logo o cache é compartilhado entre todos os visitantes. A Steam devolve
  `percent` como **string** (`"49.9"`); o client converte para `float` na
  fronteira.
- **REQ-041**: A raridade é **decoração e nunca derruba a página**: jogo sem
  estatísticas globais (403 ou lista vazia), falha de rede ou rate limit ⇒ as
  conquistas são renderizadas sem raridade, e o detalhe responde 200. Mesma
  postura best-effort do fan-out do REQ-004.
- **REQ-042**: `sort=last_played` ordena a biblioteca pela **última vez jogado**
  (`rtime_last_played` do `GetOwnedGames`), decrescente. Custo zero de quota: o
  campo já vem no payload que o app busca. `rtime_last_played` ausente ou `0`
  significa **nunca jogado** (não 1970) ⇒ esses jogos vão para o fim da lista. O
  card exibe a data.

### Funcionais — entregues na v2.0 (antes não especificados)

- **REQ-050**: `GET /api/users/{steamid}/games?include=genres` preenche o campo
  `genres` de cada jogo. **Quem agrupa é o SPA** (client-side, pelo primeiro
  gênero) — a API apenas *inclui* o dado, e o nome do parâmetro diz isso. O gênero
  **não existe na Web API oficial**: vem do endpoint **não-oficial da loja**
  (`store/appdetails`), que não usa a `STEAM_API_KEY`. O preenchimento é **lazy**
  (só quando pedido) e **100% best-effort**: a loja rate-limita agressivo, e
  qualquer falha devolve lista vazia ⇒ o jogo cai em "Sem categoria" e a
  biblioteca **nunca quebra**. `include` ausente ⇒ `genres` vem `[]`.
- **REQ-051**: `GET /api/users/{steamid}/profile` devolve o nome de exibição
  (`personaname`) e o avatar (`avatarfull`) do jogador, via
  `ISteamUser/GetPlayerSummaries/v2`. Este endpoint é também o **desempate de
  erro** do app: a Steam responde "biblioteca indisponível" tanto para conta
  inexistente quanto para perfil privado, e só o perfil separa os dois casos
  (`players: []` ⇒ conta não existe; player presente ⇒ perfil privado). O
  desempate é pago **apenas no caminho de erro**.
- **REQ-052**: O `steamid` de qualquer rota deve ter **17 dígitos numéricos**.
  Fora disso ⇒ **422** com `{"detail": "<mensagem pt-BR>"}`, **antes** de qualquer
  chamada à Steam. O SPA também valida, mas a validação do servidor é a rede de
  segurança — o `steamid` é input público.
- **REQ-053**: Toda chamada que usa a `STEAM_API_KEY` passa por um **token bucket
  global** no client (`steam_rate_per_minute` / `steam_rate_burst`), que protege a
  quota da chave contra qualquer chamador. O teto é consumido **por tentativa**
  (o retry também gasta quota), e estourá-lo ⇒ `SteamRateLimitError` ⇒ **429**. O
  endpoint de gênero (loja) **não** passa pelo bucket: não usa a chave, logo não
  há quota a proteger.
- **REQ-054**: O `TTLCache` tem **teto de entradas** (`_MAXSIZE`). Como o
  `steamid` vem da URL, o espaço de chaves é controlado por quem chama: sem teto,
  IDs sempre novos fazem o dict crescer indefinidamente (entradas nunca relidas
  nunca expiram) até derrubar o processo. Ao encher, descarta primeiro uma entrada
  **expirada**; não havendo, a mais antiga.

### Funcionais — identificação do perfil

O usuário **não sabe** o próprio SteamID64: ele tem o **link do perfil** ou o
**nome do perfil**. Exigir 17 dígitos é exigir que ele faça, no olho, o trabalho
que a máquina faz — e para o link `/id/<nome>` nem no olho dá.

- **REQ-060**: O campo de entrada do SPA aceita **qualquer forma de identificação
  que o usuário tenha**. Uma função pura (`normalizeSteamId`) classifica o input
  em três resultados, nesta ordem, **antes** de qualquer rede:

  A ordem das linhas **é** o algoritmo: a primeira que casa vence. Trocá-las muda o
  comportamento (ver a nota da 5ª linha).

| # | Entrada | Resultado | Custo |
|---|---|---|---|
| 1 | URL `steamcommunity.com/profiles/76561197960287930` (com/sem esquema, `/` final ou sufixo) | **steamid** (extrai os 17 dígitos) | 0 chamadas |
| 2 | `76561197960287930` (17 dígitos crus) | **steamid** | 0 chamadas |
| 3 | URL `steamcommunity.com/id/<nome>` | **vanity** ⇒ REQ-061 | 1 chamada |
| 4 | Só dígitos, mas **não** 17 (ex.: 16 = dígito comido no copiar/colar) | **inválido** — erro local | 0 chamadas |
| 5 | `<nome>` solto (2–32 chars, `[A-Za-z0-9_-]`) | **vanity** ⇒ REQ-061 | 1 chamada |
| 6 | Vazio, fora do charset, ou acima de 32 chars | **inválido** — erro local | 0 chamadas |

  A linha 4 vir **antes** da 5 é **deliberado**, e é a única ordem que importa:
  `1234` casa com o charset de vanity (linha 5), mas é o erro de digitação mais
  provável que existe. Tratá-lo como vanity gastaria quota para devolver "perfil
  não encontrado", quando a mensagem certa ("um SteamID64 tem 17 dígitos") sai de
  graça. O preço: um vanity puramente numérico jamais é resolvido. Trade-off aceito.

  As linhas 1 e 3 exigem o host `steamcommunity.com` — é o que a URL de um perfil
  Steam tem. Um caminho solto (`/profiles/765…`, sem host) **não** é reconhecido:
  ninguém copia meia URL da barra de endereços.
- **REQ-061**: `GET /api/resolve?vanity={nome}` devolve `{"steamid": "<17 dígitos>"}`
  via `ISteamUser/ResolveVanityURL/v1`. É o **único** caminho possível: resolver
  exige a `STEAM_API_KEY`, e o SPA nunca fala com a Steam (CON-030).
  - O `{nome}` é validado (2–32 chars, `[A-Za-z0-9_-]`) **antes** de virar chave de
    cache ou chamada à Steam ⇒ fora disso, **422**. Sem essa guarda, texto livre de
    tamanho arbitrário vira chave de dict (o `steamid` das outras rotas é contido
    pelo funil de 17 dígitos do REQ-052; um vanity **não é**).
  - Nome inexistente (`success: 42`, que a Steam manda com HTTP **200**) ⇒
    `SteamVanityNotFound` ⇒ **404** com mensagem **própria**: a do REQ-052 manda
    "conferir os 17 dígitos", e quem digitou um nome não digitou dígito nenhum.
  - Passa pelo token bucket do REQ-053 (é chamada com a chave) e tem cache
    positivo **e negativo** (CON-011).
- **REQ-062**: O SPA oferece um **fallback textual** (elemento nativo recolhível,
  fechado por padrão) ensinando a achar o **link do perfil** — não o SteamID64,
  que o REQ-060 tornou desnecessário. Sem screenshots: print da UI da Steam
  envelhece a cada mudança da Valve, e print desatualizado é pior que texto
  nenhum. Inclui a única falha que o app **não consegue** consertar sozinho: o
  perfil privado.

**Explicitamente fora de escopo:** rate limit por IP no `/api/resolve` e partição
do cache por prefixo. A superfície já existe hoje — `GET /api/users/<17 dígitos
aleatórios>/profile` custa exatamente o mesmo (1 requisição ⇒ 1 chamada Steam ⇒ 1
entrada de cache negativo). O vanity não cria uma classe nova de risco; abre mais
uma porta do mesmo tamanho. Blindar uma e deixar a irmã aberta é teatro. Se doer,
a correção é rate limit por IP **na frente de tudo**.

### Cache

- **REQ-010**: Resultados são cacheados em `TTLCache` por processo, **volátil**
  (não é banco de dados). Chaves e TTLs:

| Chave | TTL (hit) | TTL (miss/vazio) | Escopo |
|---|---|---|---|
| `owned_games:{steamid}` | 300s | — | jogador |
| `player_ach:{steamid}:{appid}` | 300s | 300s | jogador × jogo |
| `player_summary:{steamid}` | 300s | 60s (conta inexistente) | jogador |
| `schema:{appid}` | 86400s | — | jogo |
| `global_pct:{appid}` | 86400s | 3600s | jogo |
| `genres:{appid}` | 604800s | 3600s | jogo |
| `vanity:{nome}` | 300s | 60s (nome inexistente) | nome do perfil (REQ-061) |

- **CON-010c**: `vanity:{nome}` é **case-sensitive**, embora a Steam trate o nome
  como case-insensitive: `Rafa` e `rafa` viram duas entradas apontando para o mesmo
  steamid. É desperdício de entrada, não bug — e o teto (`_MAXSIZE`, REQ-054) já
  responde pelo crescimento. Normalizar o caixa de um valor que a Steam trata como
  opaco custaria mais do que economiza.

- **CON-010**: As chaves de dado **por jogador** incluem obrigatoriamente o
  `steamid`. Omiti-lo vazaria dados entre jogadores.
- **CON-010b**: `GetPlayerAchievements` é buscado por **um único** módulo do
  service, e o que entra em `player_ach:{steamid}:{appid}` é uma **projeção enxuta**
  de cada conquista — `apiname`, `achieved` (já normalizado para bool) e
  `unlocktime`. **Nunca o payload cru**: guardá-lo inflaria um `TTLCache` cujo teto
  conta entradas, não bytes (REQ-054). Por isso o `GetPlayerAchievements` é chamado
  **sem `l=`** — o parâmetro de idioma faz a Steam incluir `name`/`description` em
  cada conquista (payload dobra: 5076 → 2561 bytes num jogo de 43 conquistas) que o
  app não usa, pois o texto exibido vem do `schema:{appid}`, cacheado por jogo.
  A contagem (obtidas/total) da biblioteca e a lista do detalhe são **duas leituras
  do mesmo cache**: quem ordena por `%` e depois abre um jogo não paga a chamada
  duas vezes.
  Conquista **sem `apiname`** é descartada nessa projeção: sem nome não há como
  casar com o schema nem com a raridade, e a exceção derrubaria o fan-out inteiro
  (que só engole `SteamError`), violando o best-effort do REQ-004.
- **CON-011**: **Cache negativo é obrigatório onde o "não" é uma resposta**, e não
  um erro:
  - jogo **sem conquistas** ⇒ cacheia `[]` em `player_ach`. Devolver "nada" e
    não cachear faria **todo** load com `include=achievements` re-consultar a Steam
    para **todos** esses jogos, para sempre (`None` é o sinal de miss do cache, por
    isso o "não" é `[]`);
  - conta **inexistente** ⇒ cacheia o "não" (TTL curto), para que marretar o mesmo
    ID inválido não queime a quota da chave;
  - **nome de perfil inexistente** (REQ-061) ⇒ mesmo motivo, mesmo TTL curto. Curto
    e não longo porque um nome livre hoje **pode ser registrado amanhã** — ao
    contrário de um appid, que é imutável;
  - gênero/raridade **vazios** ⇒ TTL curto (o vazio pode ser um 429 transitório, e
    não ausência real — não merece 24h/7d de cache).
- **CON-012**: TTL curto para dado do jogador (muda), TTL longo para dado do jogo
  (não muda). Valores configuráveis.

### Concorrência / Resiliência

- **REQ-020**: O fan-out é limitado por `Semaphore(steam_concurrency)` para evitar
  429 em contas grandes.
- **REQ-021**: O client HTTP aplica retry com backoff em respostas 429 e 5xx.
  Esgotado o retry, propaga exceção tipada.
- **CON-020**: `httpx.AsyncClient` deve ter timeout explícito (connect/read 10s).

### Arquitetura (invariantes)

- **PAT-001**: Dependências apontam para o domínio: `web → services → steam`.
- **PAT-002**: `web/` não importa `httpx` nem fala com a Steam direto; devolve
  modelos de domínio como **JSON** (não renderiza HTML).
- **PAT-003**: `services/` não importa `Request`/`fastapi`.
- **PAT-004**: `steam/` é a única camada que faz HTTP com a Steam; seus métodos
  retornam dict desembrulhado ou levantam exceção tipada.
- **PAT-005**: Wiring (`AsyncClient` + `TTLCache` + service) no `lifespan` de
  `main.py`, em `app.state`, injetado por `Depends(get_service)`.
- **PAT-006**: **O frontend nunca fala com a Steam** — só com `/api`. O FastAPI é
  o único gateway da Steam.
- **CON-030**: Sem banco, fila, Redis ou OpenID. Sem abstrações especulativas.

### Segurança

- **SEC-001**: `STEAM_API_KEY` apenas via env/`.env`. Nunca em resposta da API,
  bundle do frontend, commit ou log. `.env` no `.gitignore`.
- **SEC-002**: A key trafega apenas na querystring **server-side**. Log `DEBUG` do
  `httpx` **proibido** (vaza a URL com a chave).
- **SEC-003**: O bundle do frontend é **público**: só variáveis `VITE_*` chegam
  nele, e nenhuma delas pode conter segredo.

### Configuração / Ambientes

- **CON-040**: Config **só por ambiente** (12-factor). `ENVIRONMENT=dev|prod`
  (default `dev`). Em `prod`, `/docs`, `/redoc` e `/openapi.json` são
  **desligados**; em dev ficam ativos porque a geração de tipos do frontend lê o
  schema.
- **CON-041**: **Same-origin nos dois ambientes** — dev via proxy do Vite, prod via
  rewrite `/api/*`. Logo `CORS_ORIGINS` fica vazio e o middleware de CORS só é
  registrado quando não é vazio.

### Idioma

- **GUD-001**: `GetSchemaForGame` é chamado com `l=brazilian`; quando faltar
  tradução, usar o texto em inglês retornado.
- **GUD-002**: Comentários de código e mensagens ao usuário em pt-BR.

## 4. Interfaces & Data Contracts

### Rotas HTTP (API JSON, prefixo `/api`)

| Método | Rota | Query | Resposta |
|---|---|---|---|
| GET | `/api/users/{steamid}/profile` | — | JSON `PlayerSummary` |
| GET | `/api/users/{steamid}/games` | `sort` ∈ {`playtime`,`name`,`percent`,`ach_count`,`last_played`}; `include` (repetível) ∈ {`achievements`,`genres`} | JSON `list[Game]` |
| GET | `/api/users/{steamid}/games/{appid}` | — | JSON `GameDetail` |
| GET | `/api/resolve` | `vanity` (2–32 chars, `[A-Za-z0-9_-]`) | JSON `ResolvedProfile` (REQ-061) |

- `{steamid}`: 17 dígitos (REQ-052). Fora do padrão ⇒ **422**.
- `/api/resolve` é a **única** rota que ecoa um `steamid` no corpo — descobri-lo é
  o serviço que ela presta. Não é vazamento: o `steamid` já vive na URL pública
  `/u/{steamid}` do SPA. O segredo é a `STEAM_API_KEY`, e ela continua server-side.
- `sort`/`include` ausentes ⇒ default (`playtime` / nada incluído). Valor **fora do
  vocabulário ⇒ 422** com `detail` em pt-BR: o vocabulário está no OpenAPI, então
  lixo na querystring é erro do caller, não algo a adivinhar em silêncio.
- Os dois eixos são **ortogonais**: `sort` ordena, `include` decide o que buscar.
- Paths não-`/api` são servidos pelo SPA (StaticFiles + fallback p/ `index.html`,
  para deep-link de rotas do React Router).
- Busca por nome, filtro por status e agrupamento visual são **client-side** no
  SPA.

### Steam Web API (fonte de verdade: `Steam_Web_API_Documentation.md`)

| Endpoint | Parâmetros-chave | Uso |
|---|---|---|
| `IPlayerService/GetOwnedGames/v1` | `steamid`, `include_appinfo=1`, `include_played_free_games=1` | biblioteca + playtime + nome + `img_icon_url` + `playtime_2weeks` (REQ-033) + `rtime_last_played` (REQ-042) |
| `ISteamUserStats/GetPlayerAchievements/v1` | `steamid`, `appid`, `l=brazilian` | flag `achieved` (0/1) por conquista → % e contagem; `unlocktime` (REQ-030) |
| `ISteamUserStats/GetSchemaForGame/v2` | `appid`, `l=brazilian` | `availableGameStats.achievements`: `name`/`displayName`/`description`/`icon`/`icongray` |
| `ISteamUserStats/GetGlobalAchievementPercentagesForApp/v2` | **`gameid`** | raridade global por `apiname` (REQ-040) |
| `ISteamUser/GetPlayerSummaries/v2` | `steamids` | `personaname` + `avatarfull`; desempate de erro (REQ-051) |
| `store/appdetails` (**não-oficial**, sem key) | `appids`, `filters=genres` | gêneros (REQ-050) |
| `ISteamUser/ResolveVanityURL/v1` | `vanityurl` | nome do perfil → SteamID64 (REQ-061) |

⚠️ O parâmetro do endpoint de raridade é `gameid`, não `appid` — é o único assim.
⚠️ O `ResolveVanityURL` sinaliza fracasso com HTTP **200** + `success: 42` no corpo
— quem olhar o status code vai achar que deu certo.
⚠️ O endpoint de gênero é da **loja**, não da Web API: base URL diferente, sem
chave, sem contrato, e rate-limita agressivo.

### Modelo de domínio (pydantic)

```python
class PlayerSummary(BaseModel):
    personaname: str
    avatar_url: str | None
    # Sem steamid, de propósito: quem chama /profile já o tem no path.

class ResolvedProfile(BaseModel):
    steamid: str                 # o único modelo que ecoa steamid (REQ-061)

class Game(BaseModel):
    appid: int
    name: str
    playtime_minutes: int
    playtime_2weeks_minutes: int | None   # só quem jogou nas últimas 2 semanas (REQ-033)
    last_played_at: datetime | None       # None = nunca jogado (REQ-042)
    icon_url: str | None
    percent: float | None        # preenchido só em include=achievements
    achieved_count: int | None
    total_count: int | None
    genres: list[str]            # preenchido só em include=genres (REQ-050)

class Achievement(BaseModel):
    apiname: str
    display_name: str
    description: str | None
    icon_url: str | None
    achieved: bool
    unlocked_at: datetime | None    # só nas obtidas, e nem sempre (REQ-030)
    global_percent: float | None    # None quando a raridade não veio (REQ-041)

class GameDetail(BaseModel):
    appid: int
    name: str
    supports_achievements: bool
    achieved_count: int
    total_count: int
    percent: float
    achievements: list[Achievement]
```

### Mapeamento de erro → HTTP

Todo erro responde `JSONResponse({"detail": "<mensagem pt-BR>"}, status)` — um
**contrato único**, inclusive para o 422 (o `detail` array do FastAPI é
substituído por string, porque o SPA exibe o campo direto).

| Condição | Exceção | Status |
|---|---|---|
| `steamid` fora do padrão de 17 dígitos | `RequestValidationError` | **422** JSON `{detail}` |
| `sort` ou `include` fora do vocabulário | `RequestValidationError` | **422** JSON `{detail}` |
| Conta inexistente (`players: []`) | `SteamProfileNotFound` | **404** JSON `{detail}` |
| Nome de perfil inexistente (`success: 42`) | `SteamVanityNotFound` | **404** JSON `{detail}` — mensagem **própria**, fala em link/nome, não em "17 dígitos" |
| `vanity` fora do formato (2–32, `[A-Za-z0-9_-]`) | `RequestValidationError` | **422** JSON `{detail}` |
| Perfil privado / key inválida (401/403 Steam) | `SteamDataUnavailable` | **404** JSON `{detail}` |
| 429 persistente, ou token bucket estourado | `SteamRateLimitError` | **429** JSON `{detail}` |
| 5xx persistente / falha de upstream | `SteamUnavailableError` | **502** JSON `{detail}` |
| Jogo sem stats (`playerstats.success:false`) | — | **200** com `supports_achievements=False` |
| Raridade ou gênero indisponível | — | **200** sem o dado (best-effort) |

## 5. Acceptance Criteria

- **AC-001**: Given uma conta válida, When `GET /api/users/{steamid}/games` sem
  `sort`, Then a lista vem ordenada por playtime decrescente e **apenas uma**
  chamada Steam é feita.
- **AC-002**: Given `?sort=name`, When responde, Then ordena por nome (alfabético)
  sem buscar conquistas.
- **AC-003**: Given `?sort=percent&include=achievements`, When responde, Then busca
  conquistas de todos os jogos (respeitando o `Semaphore`), inclui o % por jogo e
  ordena por % decrescente.
- **AC-004**: Given uma segunda chamada `?include=achievements` dentro do TTL, When
  responde, Then usa o cache `player_ach:{steamid}:{appid}` e **não** refaz o
  fan-out.
- **AC-004b**: Given `?include=achievements` já executado, When o **detalhe** de um
  desses jogos é aberto dentro do TTL, Then a Steam **não** é consultada de novo
  para esse jogo — e vice-versa (CON-010b).
- **AC-004c**: Given `?sort=percent` **sem** `include`, When responde, Then
  **nenhuma** chamada de conquistas é feita e todos os jogos vêm com `percent:
  null` (ordenação estável, sem erro).
- **AC-004d**: Given `?sort=xpto` ou `?include=xpto`, When responde, Then **422**
  com `{"detail": "<pt-BR>"}` e **nenhuma** chamada à Steam.
- **AC-005**: Given `GET /api/users/{steamid}/games/{appid}` de um jogo com
  conquistas, When responde, Then traz cada conquista como obtida/pendente, a
  contagem e o %.
- **AC-006**: Given a página de detalhe carregada, When o usuário aciona o filtro
  de status, Then a lista filtra no navegador sem nova requisição.
- **AC-007**: Given um jogo sem sistema de conquistas, When `GET
  /api/users/{steamid}/games/{appid}`, Then responde **200** com
  `supports_achievements=False` (não quebra).
- **AC-008**: Given perfil privado ou key inválida, When qualquer rota, Then
  responde **404** com mensagem amigável em pt-BR no campo `detail`.
- **AC-009**: Given a Steam responde 429/5xx repetidamente, When o retry esgota,
  Then o app responde **429**/**502** respectivamente.
- **AC-010**: Given qualquer execução, When inspecionado o log ou a resposta, Then
  a `STEAM_API_KEY` nunca aparece.
- **AC-011**: Given um jogo com estatísticas globais, When abre o detalhe, Then
  cada conquista exibe o % global e a que está abaixo de 10% aparece como rara.
- **AC-012**: Given a Steam não devolve raridade (403, lista vazia, rede ou 429),
  When abre o detalhe, Then responde **200** com todas as conquistas, apenas sem
  raridade — não quebra e não vira erro.
- **AC-013**: Given `?sort=last_played`, When responde, Then ordena pela última vez
  jogado (mais recente primeiro), com os nunca jogados por último, e **nenhuma**
  chamada Steam além do `GetOwnedGames`.
- **AC-050**: Given `?include=genres` e a loja indisponível (429/403/rede), When
  responde, Then a biblioteca vem **completa**, apenas com `genres` vazio — não
  quebra.
- **AC-051**: Given um SteamID **inexistente**, When qualquer rota, Then responde
  **404** "Steam ID não encontrado" (e não a mensagem de perfil privado).
- **AC-052**: Given um `steamid` com menos/mais de 17 dígitos ou com letras, When
  qualquer rota, Then responde **422** com `{"detail": "<pt-BR>"}` e **nenhuma**
  chamada à Steam é feita.
- **AC-053**: Given o token bucket esgotado, When uma chamada que usa a key é
  tentada, Then o app responde **429** — sem enviá-la à Steam.
- **AC-054**: Given o `TTLCache` cheio (`_MAXSIZE`), When uma chave nova é
  inserida, Then uma entrada é descartada (expirada primeiro; senão a mais antiga)
  e o cache **não cresce** além do teto.
- **AC-055**: Given um jogo **sem conquistas** na biblioteca, When
  `?include=achievements` é chamado duas vezes dentro do TTL, Then a Steam é
  consultada **uma única vez** para esse jogo (cache negativo `[]`, CON-011).
- **AC-060**: Given o usuário cola `https://steamcommunity.com/profiles/76561197960287930`
  — com ou sem `https://`, com `/` final ou sufixo (`/games/?tab=all`) — ou os 17
  dígitos crus, When submete, Then o SPA navega para `/u/76561197960287930`
  **sem chamar `/api/resolve`** — a extração é local (REQ-060).
- **AC-061**: Given o usuário informa `steamcommunity.com/id/<nome>` **ou** o `<nome>`
  solto, When submete, Then o SPA chama `/api/resolve?vanity=<nome>` e navega para
  `/u/{steamid}` com o ID resolvido.
- **AC-062**: Given o usuário informa **16 dígitos**, When submete, Then o erro é
  local ("um SteamID64 tem 17 dígitos"), **nenhuma** requisição é feita e o
  `localStorage` **não** é gravado.
- **AC-063**: Given um `vanity` inexistente, When `GET /api/resolve`, Then responde
  **404** com mensagem que fala em **link/nome do perfil** (nunca "confira os 17
  dígitos"), e uma segunda chamada com o mesmo nome dentro do TTL **não** consulta a
  Steam (cache negativo, CON-011).
- **AC-064**: Given um `vanity` fora do formato (vazio, 1 char, >32 chars, ou com
  caracteres fora de `[A-Za-z0-9_-]`), When `GET /api/resolve`, Then responde **422**
  **antes** de qualquer chamada à Steam e **sem** criar entrada de cache.
- **AC-065**: Given a Steam responde `success: 42` com HTTP **200**, When o client
  resolve um nome, Then levanta `SteamVanityNotFound` — o status `200` **não** é
  tratado como sucesso.

## 6. Test Automation Strategy

- **Test Levels**: Unit (domínio/services), Integration (rotas via `TestClient`),
  Boundary (client HTTP).
- **Frameworks**: `pytest` (backend), `vitest` (frontend). O domínio é testado por
  **client falso** injetado (sem rede); `monkeypatch`/AsyncMock apenas no boundary
  HTTP real.
- **Test Data**: fixtures com payloads representativos da Steam (jogo com
  conquistas, jogo sem stats, perfil privado, conta inexistente, 429/5xx, loja
  throttlada).
- **CI/CD**: GitHub Actions em `push`/`pull_request` — `uv sync` + `uv run pytest`
  (backend) e `npm ci` + `npm run test` + `npm run build` (frontend; o build roda
  `tsc -b`, então o CI também barra erro de tipagem). O CI **não** recebe a
  `STEAM_API_KEY` real: os testes não tocam a rede.
- **Coverage**: sem meta numérica rígida, mas **todo AC deve ter teste**.
- **Performance**: validar que `sort=playtime` faz 1 request e que o fan-out
  respeita o `Semaphore` (sem rajada além do limite).

## 7. Rationale & Context

- **Sem banco / tempo real**: simplicidade; o `TTLCache` absorve a maior parte do
  custo sem introduzir estado durável.
- **Index leve por padrão + fan-out sob demanda**: exibir % exige buscar conquistas
  de todos os jogos (N+1). Tornar isso opt-in (`include=achievements`) mantém o
  carregamento padrão instantâneo (1 request) e evita 429 no caso comum, pagando o
  custo só quando o caller o declara.
- **`include` em vez de deduzir do `sort`**: a rota não adivinha o que o caller
  quer. Ordenação e busca de dado são eixos ortogonais — amarrá-los faria `sort`
  ter um efeito colateral invisível na querystring e impediria exibir o % sem
  ordenar por ele.
- **Filtro e busca client-side**: a lista completa já está no navegador; filtrar lá
  é instantâneo e não rebate na Steam.
- **Cache de dado do jogo separado do dado do jogador**: schema, raridade e gênero
  são iguais para todo mundo ⇒ chave por `appid`, TTL longo, **compartilhado entre
  visitantes**. Playtime e conquistas mudam ⇒ chave por `steamid`, TTL curto.
- **A quota da chave é o recurso escasso, e o `steamid` é input público**: por isso
  o token bucket (REQ-053) fica no **client**, não na rota — assim ele vale para
  qualquer chamador, e nenhuma requisição forjada escapa dele. Pelo mesmo motivo o
  cache tem teto (REQ-054) e o "não existe" é cacheado (CON-011): sem isso, um
  visitante marretando IDs inválidos queima a quota e a memória.
- **Best-effort para decoração**: raridade e gênero enfeitam; falha neles não pode
  derrubar uma página que já tem tudo que importa.
- **Camadas com dependência para o domínio**: torna `services` testável sem rede.

## 8. Dependencies & External Integrations

### External Systems
- **EXT-001**: Steam Web API — integração HTTP REST (JSON) para biblioteca,
  conquistas, schema, raridade e perfil. Requer `STEAM_API_KEY`.
- **EXT-002**: Storefront da Steam (`store/appdetails`) — **não-oficial**, sem
  chave, sem SLA, rate-limita agressivo. Única fonte de gênero. Best-effort.

### Third-Party Services
- **SVC-001**: Steam Web API — sujeita a rate limiting (429) e indisponibilidade
  (5xx); sem SLA garantido. Quota da chave é finita ⇒ ver REQ-053.

### Infrastructure Dependencies
- **INF-001**: Runtime único (`uvicorn`, 1 worker) — o cache é em processo, então
  múltiplos workers teriam caches independentes (não é erro, mas reduz o hit rate).
- **INF-002**: Docker para empacotamento da API.
- **INF-003**: Hospedagem estática do SPA (Vercel) com rewrite `/api/*` → API. Se o
  host da API mudar, atualizar o rewrite — **não** partir para CORS por reflexo.

### Data Dependencies
- **DAT-001**: Conta Steam alvo — informada pelo **visitante via URL**, não por
  configuração. Dados consumidos em tempo real; o perfil precisa estar acessível à
  key configurada.

### Technology Platform Dependencies
- **PLT-001**: Python 3.12+ (backend); gerenciador `uv`.
- **PLT-002**: FastAPI; `httpx` (async) como client HTTP; `pydantic-settings` para
  config. **Sem template engine** — a API só devolve JSON.
- **PLT-003**: React 19 + Vite + TypeScript + Tailwind + shadcn/ui + TanStack React
  Query + React Router (frontend); gerenciador `npm`. Tipos gerados do OpenAPI.

### Compliance Dependencies
- **COM-001**: Nenhuma exigência regulatória. Todo dado exposto já é público na
  Steam. A restrição de segurança é não vazar a `STEAM_API_KEY` (SEC-001..003).

## 9. Examples & Edge Cases

```text
# Carregamento padrão (barato)
GET /api/users/76561197960287930/games
  -> 1 request (GetOwnedGames), ordena por playtime
  [{ "name": "Half-Life 2", "playtime_minutes": 7200 }, ...]

# Ordenação por progresso (fan-out na 1ª vez, cache depois)
GET /api/users/76561197960287930/games?sort=percent&include=achievements
  -> GetOwnedGames + N×GetPlayerAchievements (limitado por Semaphore)
  [{ "name": "Portal", "percent": 91.8, "achieved_count": 45, "total_count": 49 }, ...]

# Gênero para o SPA agrupar (best-effort: a loja pode throttlar)
GET /api/users/76561197960287930/games?include=genres
  -> GetOwnedGames + N×store/appdetails
  jogo sem gênero -> "genres": []  -> SPA mostra "Sem categoria"

# Querystring fora do vocabulário
GET /api/users/76561197960287930/games?sort=xpto
  -> 422 {"detail": "Parâmetro inválido na URL. Confira o endereço e tente de novo."}

# Detalhe
GET /api/users/76561197960287930/games/220
  -> GetPlayerAchievements + GetSchemaForGame + GetGlobalAchievementPercentages

# Edge cases
- steamid "123"                  -> 422 {"detail": "Parâmetro inválido na URL..."}
- steamid inexistente            -> 404 "Steam ID não encontrado"
- perfil privado                 -> 404 "Dados indisponíveis. O perfil pode estar privado."
- jogo sem conquistas            -> 200, supports_achievements=false; cacheia [] (CON-011)
- jogo sem stats globais         -> 200, conquistas sem global_percent (403 engolido)
- loja throttlada (429/403)      -> 200, genres: [] em todos os jogos
- 429/5xx persistente            -> retry/backoff; esgotado -> 429/502
- token bucket estourado         -> 429 sem sequer chamar a Steam
- percent da raridade vem STRING ("49.9") -> convertido a float no client
- campo é `apiname` (não `api_name`); schema usa availableGameStats.achievements
- ícone do jogo: .../images/apps/{appid}/{img_icon_url}.jpg  (hash vazio -> None)
```

## 10. Validation Criteria

- Todos os AC-001..AC-065 cobertos por testes automatizados verdes.
- Qualquer `sort` **sem `include`** comprovadamente faz 1 request (sem fan-out).
- `include=achievements` respeita o `Semaphore` e usa cache na repetição —
  **inclusive para jogo sem conquistas** (AC-055) e **entre biblioteca e detalhe**
  (AC-004b).
- Invariantes de camada (PAT-001..PAT-006) não violadas (web sem `httpx`; services
  sem `fastapi`; frontend sem Steam).
- `STEAM_API_KEY` ausente de logs, respostas e do bundle (SEC-001..003).
- App sobe com `uv run uvicorn app.main:app --reload` + `npm run dev`, e com
  `docker compose up --build`.
- CI verde no GitHub Actions (backend e frontend).

## 11. Related Specifications / Further Reading

- `CLAUDE.md` (raiz do projeto) — instruções e invariantes de arquitetura.
- `Steam_Web_API_Documentation.md` — fonte de verdade dos endpoints consumidos.
- `ROADMAP.md` — o que já foi entregue e o que falta.
- Steam Web API oficial: https://partner.steamgames.com/doc/webapi
