---
title: App Web Pessoal de Conquistas Steam — Especificação de Comportamento
version: 1.0
date_created: 2026-06-28
last_updated: 2026-06-28
owner: rafa.limadalmagro
tags: [architecture, design, app, steam, fastapi]
---

# Introduction

Especificação de comportamento de um app web **pessoal** (single-user) para
acompanhar biblioteca, tempo de jogo e progresso de conquistas de **uma** conta
Steam. A consulta é em **tempo real** contra a Steam Web API (**sem banco de
dados**). Arquitetura **fullstack**: backend FastAPI expõe **API JSON** sob
`/api`; frontend é um **SPA React** (Vite + Tailwind + shadcn/ui) consumindo a
API via **TanStack React Query**. Em produção o FastAPI serve o build estático
do SPA; em dev o Vite serve o front com proxy `/api` → FastAPI. Esta spec é a
fonte de verdade da fase SDD e precede o PLAN e o ciclo RED/GREEN/REFACTOR.

## 1. Purpose & Scope

**Propósito:** definir, de forma não ambígua, o comportamento observável do app
— rotas, ordenação, cálculo de progresso, filtros, cache, tratamento de erro e
contratos com a Steam — suficiente para outro agente implementar via TDD sem
fazer perguntas.

**No escopo:**
- Listar biblioteca + tempo de jogo (playtime).
- Detalhe de jogo: conquistas obtidas × pendentes, % de progresso.
- Ordenação da biblioteca (index): playtime, nome, % concluído, nº de conquistas.
- Filtro por status (obtidas/pendentes) na página de detalhe.

**Fora do escopo (não implementar):**
- Multiusuário, login Steam OpenID, autenticação de qualquer tipo.
- Comparação entre jogos, histórico/snapshots, qualquer persistência relacional.
- Banco de dados, fila, Redis ou serviço de apoio com estado durável.

**Audiência:** o desenvolvedor/agente que implementará o app.

**Premissas:**
- Conta Steam com `STEAM_API_KEY` e `STEAM_ID` válidos disponíveis via env.
- App roda em `uvicorn` com **1 worker** (cache é estado em processo).
- Exposição apenas em **localhost/LAN** — ausência de autenticação é aceitável.

## 2. Definitions

- **Steam Web API**: API HTTP oficial da Valve para dados de jogadores/jogos.
- **appid**: identificador numérico de um jogo na Steam.
- **playtime**: tempo total jogado (campo `playtime_forever`, em minutos).
- **conquista (achievement)**: objetivo do jogo; tem flag `achieved` (0/1).
- **schema (do jogo)**: metadados das conquistas (nome, descrição, ícone),
  obtidos via `GetSchemaForGame`.
- **% de progresso**: `conquistas_obtidas / total_conquistas * 100`.
- **fan-out**: disparo de N chamadas HTTP (uma por jogo) para montar uma visão.
- **TTLCache**: cache em memória com expiração por tempo (volátil, por processo).
- **SSR**: Server-Side Rendering (HTML montado no servidor, Jinja2).
- **supports_achievements**: indica se o jogo tem sistema de conquistas.

## 3. Requirements, Constraints & Guidelines

### Funcionais
- **REQ-001**: A rota `GET /` lista os jogos da conta com nome, ícone e playtime.
- **REQ-002**: `GET /` aceita o parâmetro de query `sort` com valores:
  `playtime` (default), `name`, `percent`, `ach_count`.
- **REQ-003**: Para `sort=playtime` e `sort=name`, `GET /` executa **uma única**
  chamada (`GetOwnedGames`) e **não** busca conquistas.
- **REQ-004**: Para `sort=percent` e `sort=ach_count`, `GET /` executa fan-out de
  `GetPlayerAchievements` para todos os jogos e a lista **exibe** o % por jogo.
- **REQ-005**: A rota `GET /game/{appid}` exibe a lista completa de conquistas do
  jogo, cada uma marcada como obtida ou pendente, com nome/descrição/ícone, além
  da contagem (obtidas/total) e do % de progresso.
- **REQ-006**: O % e a contagem derivam de `GetPlayerAchievements` (flag
  `achieved`). O schema **não** é necessário para o percentual, apenas para
  nome/descrição/ícone das conquistas.
- **REQ-007**: O filtro por status na página de detalhe é **client-side** (JS),
  operando sobre a lista já renderizada, sem nova chamada ao servidor/Steam.
- **REQ-008**: Jogo sem sistema de conquistas é tratado como
  `supports_achievements=False` e renderizado sem quebrar (mensagem informativa).

### Cache
- **REQ-010**: Resultados são cacheados em `TTLCache` por processo, volátil.
  Chaves: `owned_games`, `ach_counts:{appid}`, `schema:{appid}`.
- **CON-010**: TTL `owned_games` = 300s; `ach_counts:{appid}` = 300s;
  `schema:{appid}` = 86400s (schema é quase imutável). Valores configuráveis.

### Concorrência / Resiliência
- **REQ-020**: O fan-out é limitado por `Semaphore(steam_concurrency)` para
  evitar 429 em contas grandes.
- **REQ-021**: O client HTTP aplica retry com backoff em respostas 429 e 5xx.
  Esgotado o retry, propaga exceção tipada.
- **CON-020**: `httpx.AsyncClient` deve ter timeout explícito (connect/read 10s).

### Arquitetura (invariantes)
- **PAT-001**: Dependências apontam para o domínio: `web → services → steam`.
- **PAT-002**: `web/` não importa `httpx` nem fala com a Steam direto.
- **PAT-003**: `services/` não importa `Request`/`fastapi`.
- **PAT-004**: `steam/` é a única camada que faz HTTP com a Steam; seus métodos
  retornam dict desembrulhado ou levantam exceção tipada.
- **PAT-005**: Wiring (`AsyncClient` + `TTLCache` + service) no `lifespan` de
  `main.py`, em `app.state`, injetado por `Depends(get_service)`.
- **CON-030**: Sem banco, fila, Redis ou OpenID. Sem abstrações especulativas.

### Segurança
- **SEC-001**: `STEAM_API_KEY` e `STEAM_ID` apenas via env/`.env`. Nunca em
  template, resposta, commit ou log. `.env` no `.gitignore`.
- **SEC-002**: A key trafega apenas na querystring server-side. Log `DEBUG` do
  `httpx` **proibido** (vaza a URL com a chave).

### Idioma
- **GUD-001**: `GetSchemaForGame` é chamado com `l=brazilian`; quando faltar
  tradução, usar o texto em inglês retornado.
- **GUD-002**: Comentários de código e mensagens ao usuário em pt-BR.

## 4. Interfaces & Data Contracts

### Rotas HTTP (app)

| Método | Rota | Query | Resposta |
|---|---|---|---|
| GET | `/api/games` | `sort` ∈ {`playtime`,`name`,`percent`,`ach_count`} | JSON `list[Game]` |
| GET | `/api/games/{appid}` | — | JSON `GameDetail` |

- `sort` ausente/inválido ⇒ trata como `playtime` (default).
- Paths não-`/api` são servidos pelo SPA (StaticFiles + fallback p/ `index.html`,
  para deep-link de rotas do React Router como `/game/{appid}`).
- O filtro por status (detalhe) e a exibição/loading são **client-side** no SPA
  (React Query dá o estado de carregamento; o filtro roda no navegador).

### Steam Web API (fonte de verdade: `Steam_Web_API_Documentation.md`)

| Endpoint | Parâmetros-chave | Uso |
|---|---|---|
| `IPlayerService/GetOwnedGames/v1` | `steamid`, `include_appinfo=1`, `include_played_free_games=1` | biblioteca + playtime + nome + `img_icon_url` |
| `ISteamUserStats/GetPlayerAchievements/v1` | `steamid`, `appid` | flag `achieved` (0/1) por conquista → % e contagem |
| `ISteamUserStats/GetSchemaForGame/v2` | `appid`, `l=brazilian` | `availableGameStats.achievements`: `name`/`displayName`/`description`/`icon` |

### Modelo de domínio (pydantic, ilustrativo)

```python
class Game(BaseModel):
    appid: int
    name: str
    playtime_minutes: int
    icon_url: str | None
    percent: float | None        # preenchido só em sort=percent/ach_count
    achieved_count: int | None
    total_count: int | None

class Achievement(BaseModel):
    apiname: str
    display_name: str
    description: str | None
    icon_url: str | None
    achieved: bool

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

Erros mapeados retornam `JSONResponse({"detail": "<mensagem pt-BR>"}, status)`;
o SPA exibe a mensagem do campo `detail`.

| Condição | Exceção | Status app |
|---|---|---|
| Perfil privado / key inválida (401/403 Steam) | `SteamDataUnavailable` | 404 JSON `{detail}` |
| 429 persistente | `SteamRateLimitError` | 429 JSON `{detail}` |
| 5xx persistente / falha de upstream | `SteamUnavailableError` | 502 JSON `{detail}` |
| Jogo sem stats (`playerstats.success:false`) | — | 200 com `supports_achievements=False` |

## 5. Acceptance Criteria

- **AC-001**: Given uma conta válida, When `GET /` sem `sort`, Then a lista é
  ordenada por playtime decrescente e **apenas uma** chamada Steam é feita.
- **AC-002**: Given `GET /?sort=name`, When renderiza, Then ordena por nome
  (alfabético) sem buscar conquistas.
- **AC-003**: Given `GET /?sort=percent`, When renderiza, Then busca conquistas
  de todos os jogos (respeitando o `Semaphore`), exibe o % por jogo e ordena por
  % decrescente.
- **AC-004**: Given uma segunda chamada `GET /?sort=percent` dentro do TTL, When
  renderiza, Then usa o cache `ach_counts:{appid}` e **não** refaz o fan-out.
- **AC-005**: Given `GET /game/{appid}` de um jogo com conquistas, When
  renderiza, Then mostra cada conquista como obtida/pendente, a contagem e o %.
- **AC-006**: Given a página de detalhe carregada, When o usuário aciona o filtro
  de status, Then a lista filtra no navegador sem nova requisição.
- **AC-007**: Given um jogo sem sistema de conquistas, When `GET /game/{appid}`,
  Then responde 200 com mensagem de que o jogo não tem conquistas (não quebra).
- **AC-008**: Given perfil privado/key inválida, When qualquer rota, Then exibe
  página de erro amigável em pt-BR (detalhe ⇒ 404).
- **AC-009**: Given a Steam responde 429/5xx repetidamente, When o retry esgota,
  Then o app responde 429/502 respectivamente.
- **AC-010**: Given qualquer execução, When inspecionado o log, Then a
  `STEAM_API_KEY` nunca aparece.

## 6. Test Automation Strategy

- **Test Levels**: Unit (domínio/services), Integration (rotas via `TestClient`),
  Boundary (client HTTP).
- **Frameworks**: `pytest`. Domínio testado por **client falso** injetado (sem
  rede). `monkeypatch`/AsyncMock apenas no boundary HTTP real.
- **Test Data**: fixtures com payloads representativos da Steam (jogo com
  conquistas, jogo sem stats, perfil privado, 429/5xx).
- **CI/CD**: `uv run pytest` deve passar localmente; pipeline opcional.
- **Coverage**: priorizar 100% dos comportamentos da spec (services e rotas);
  sem meta numérica rígida, mas todo AC deve ter teste.
- **Performance**: validar que `sort=playtime` faz 1 request e que o fan-out
  respeita o `Semaphore` (sem rajada além do limite).

## 7. Rationale & Context

- **Sem banco / tempo real**: simplicidade para uso pessoal; o `TTLCache`
  absorve a maior parte do custo sem introduzir estado durável.
- **Index leve por padrão + fan-out sob demanda**: ordenar por % exige buscar
  conquistas de todos os jogos (N+1). Tornar isso opt-in (`sort=percent`/
  `ach_count`) mantém o carregamento padrão instantâneo (1 request) e evita 429
  no caso comum, pagando o custo só quando o usuário pede ordenação por progresso.
- **Filtro client-side**: a lista completa já está no HTML do detalhe; filtrar no
  navegador é instantâneo e não rebate na Steam.
- **Cache de schema com TTL longo**: schema é quase imutável e caro; separá-lo de
  `ach_counts` evita refazer a chamada cara a cada navegação.
- **Camadas com dependência para o domínio**: torna `services` testável sem rede.

## 8. Dependencies & External Integrations

### External Systems
- **EXT-001**: Steam Web API — integração HTTP REST (JSON) para biblioteca,
  conquistas e schema.

### Third-Party Services
- **SVC-001**: Steam Web API — requer `STEAM_API_KEY`; sujeita a rate limiting
  (429) e indisponibilidade (5xx); sem SLA garantido para uso pessoal.

### Infrastructure Dependencies
- **INF-001**: Runtime único (`uvicorn`, 1 worker) — cache em processo exige
  worker único para consistência.
- **INF-002**: Docker / docker compose para empacotamento e execução.

### Data Dependencies
- **DAT-001**: Conta Steam alvo (`STEAM_ID`) — dados consumidos em tempo real;
  perfil precisa estar acessível à key configurada.

### Technology Platform Dependencies
- **PLT-001**: Python 3.12.
- **PLT-002**: FastAPI + Jinja2 (SSR); httpx (async) como client HTTP;
  pydantic-settings para config; gerenciador `uv`.

### Compliance Dependencies
- **COM-001**: Nenhuma exigência regulatória; restrição de segurança é não
  vazar a `STEAM_API_KEY` (ver SEC-001/SEC-002).

## 9. Examples & Edge Cases

```text
# Carregamento padrão (barato)
GET /                  -> 1 request (GetOwnedGames), ordena por playtime
  Half-Life 2 | 120h
  Portal      |  8h

# Ordenação por progresso (fan-out na 1ª vez, cache depois)
GET /?sort=percent     -> GetOwnedGames + N×GetPlayerAchievements (Semaphore)
  Portal      |  8h | 92% (45/49)
  Half-Life 2 | 120h | 60% (30/50)

# Detalhe + filtro client-side
GET /game/220          -> GetPlayerAchievements + GetSchemaForGame(l=brazilian)
  [Todas | Obtidas | Pendentes]  (toggle JS, sem novo request)

# Edge cases
- Jogo sem conquistas: playerstats.success:false -> 200, "sem conquistas".
- Perfil privado/key inválida (401/403): página de erro pt-BR; detalhe -> 404.
- 429/5xx persistente: retry/backoff; esgotado -> 429/502.
- Campo correto é `apiname` (não `api_name`); schema usa
  availableGameStats.achievements.
- Ícone de jogo: .../images/apps/{appid}/{img_icon_url}.jpg
```

## 10. Validation Criteria

- Todos os AC-001..AC-010 cobertos por testes automatizados verdes.
- `sort=playtime`/`name` comprovadamente fazem 1 request (sem fan-out).
- `sort=percent`/`ach_count` respeitam o `Semaphore` e usam cache na repetição.
- Invariantes de camada (PAT-001..PAT-005) não violadas (web sem httpx; services
  sem fastapi).
- `STEAM_API_KEY` ausente de logs e respostas (SEC-001/SEC-002).
- App sobe com `uv run uvicorn app.main:app --reload` e `docker compose up --build`.

## 11. Related Specifications / Further Reading

- `CLAUDE.md` (raiz do projeto) — instruções e invariantes de arquitetura.
- `Steam_Web_API_Documentation.md` (a criar) — fonte de verdade dos endpoints.
- Plano de arquitetura aprovado:
  `~/.claude/plans/analise-o-arquivo-claude-md-curious-candle.md`.
- Steam Web API oficial: https://partner.steamgames.com/doc/webapi
