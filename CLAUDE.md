# CLAUDE.md

Instruções de projeto para o Claude Code. Leia antes de editar.

## O que é

App web **pessoal** para acompanhar conquistas, biblioteca e tempo de jogo de
uma conta Steam. **Single-user**, consulta em **tempo real (sem banco)**.
Arquitetura **fullstack**: backend FastAPI expõe **API JSON** sob `/api`; o
frontend é um **SPA React** (Vite + Tailwind + shadcn/ui) que consome a API via
**TanStack React Query**. Em produção o FastAPI serve o build estático do
frontend; em dev o Vite serve o SPA com proxy `/api` → FastAPI.

Escopo fechado na entrevista de arquitetura — não expandir sem pedir:
- Funcionalidades: biblioteca + playtime; conquistas obtidas × pendentes;
  progresso % por jogo; ordenação (biblioteca) e filtro por status (detalhe).
- **Fora de escopo agora:** multiusuário, login Steam OpenID, comparação entre
  jogos, histórico/snapshots, qualquer persistência relacional.

## Stack

**Backend:** Python 3.12 · FastAPI · uvicorn · httpx (async) · pydantic-settings ·
pytest. Gerenciador: **uv**.
**Frontend:** React 19 · Vite · TypeScript · Tailwind v4 · shadcn/ui (Radix) ·
TanStack React Query · React Router. Gerenciador: **npm**. Tipos gerados do
OpenAPI (`openapi-typescript`).
Deploy: Docker (multi-stage: builda o frontend e o FastAPI serve o `dist`).

## Comandos

```bash
# Backend (na raiz)
uv sync                                      # instala deps do backend
uv run uvicorn app.main:app --reload         # API dev (http://localhost:8000)
uv run pytest                                # testes do backend

# Frontend (em frontend/)
npm install                                  # instala deps do frontend
npm run dev                                  # SPA dev (http://localhost:5173, proxy /api)
npm run build                                # gera frontend/dist (servido pelo FastAPI)
npm run test                                 # testes do frontend (Vitest)
npm run typecheck                            # tsc -b — ver aviso abaixo
npm run generate:api                         # regenera tipos TS do /openapi.json (backend up)

docker compose up --build                    # app completo (ENVIRONMENT=prod) em :8000
```

Terminal alvo: Linux nativo (zsh).

⚠️ **Nunca use `tsc --noEmit` neste projeto.** O `tsconfig.json` é só um arquivo
de *references* com `"files": []`, então `--noEmit` checa **zero arquivos** e
passa sempre — inclusive com erro de tipo na árvore. Use `npm run typecheck`
(`tsc -b`), que é o que o `npm run build` e o Dockerfile rodam. Já quebrou um
deploy: um `string` passado onde se esperava `number` atravessou a sessão inteira
com "tsc ok" no console.

**Fluxo dev:** suba o backend (`uv run uvicorn …`) e, em outro terminal, o front
(`npm run dev`). Acesse pelo Vite (5173); ele encaminha `/api` para o 8000.

## Ambientes (DEV × PROD)

Config só por env (12-factor). Backend lê `.env` na raiz; frontend lê
`frontend/.env` (só `VITE_*` chega ao bundle — e o bundle é **público**).

- `ENVIRONMENT=dev|prod` (default `dev`). Em `prod`, `create_app()` desliga
  `/docs`, `/redoc` e `/openapi.json`. Em dev eles ficam ativos porque
  `npm run generate:api` lê o schema. Ao adicionar comportamento que difere
  entre ambientes, ligue-o nesta flag — não crie outra.
- **Same-origin nos dois ambientes**: dev via proxy do Vite (`vite.config.ts`),
  prod via rewrite `/api/*` do `frontend/vercel.json` → API hospedada. Logo
  `CORS_ORIGINS` e `VITE_API_BASE_URL` ficam **vazios**; o middleware de CORS só
  é registrado quando `CORS_ORIGINS` não é vazio. Se mudar o host da API,
  atualize o rewrite do `vercel.json` — não parta para CORS por reflexo.
- Deploy: SPA na Vercel (root `frontend/`), API a partir do `Dockerfile`
  (`STEAM_API_KEY` e `ENVIRONMENT=prod` no painel do host, nunca commitados).

## Arquitetura — invariante (não quebrar)

Dependências apontam sempre para o domínio. Concretamente:

- `web/` (rotas) **não** importa `httpx` nem conhece a Steam direto; retorna
  **modelos de domínio como JSON** (não renderiza HTML).
- `services/` **não** importa `Request`/`fastapi`.
- `steam/` é a única camada que fala HTTP com a Steam.
- `ai/` é a única camada que fala HTTP com provedores de IA — espelho exato do
  papel de `steam/`. Base compartilhada + uma implementação por provedor
  (Anthropic, Gemini); a escolha vive na fábrica de `ai/__init__.py`, nunca num
  `if` no `lifespan`. `services/` recebe um `ClienteDeIA` por construtor e não
  sabe qual é; `web/` não importa SDK. As chaves nunca chegam ao browser.
- Config de IA é **por provedor** (`ANTHROPIC_*`, `GEMINI_*`), nunca genérica: o
  valor certo depende de qual está ativo, e um `AI_MODEL` genérico não diria
  isso. Só a chave do provedor ativo é obrigatória, validada no boot.
- **O frontend nunca fala com a Steam** — só com `/api`. O FastAPI é o único
  gateway da Steam (a `STEAM_API_KEY` nunca chega ao browser).

```
app/                       # backend
├── config.py          # Settings via env (segredos)
├── core/cache.py      # TTLCache em memória — volátil, NÃO é banco
├── steam/             # Infra HTTP da Steam (client + exceptions tipadas)
├── ai/                # Infra HTTP da Anthropic (única camada que fala com o LLM)
├── services/          # Regra de negócio (achievements.py)
├── schemas/models.py  # Modelos de domínio (pydantic) = contrato da API
├── web/routes.py      # Rotas JSON sob /api (list_games, game_detail)
└── main.py            # FastAPI + lifespan + StaticFiles (serve o SPA em prod)

frontend/                  # SPA React
├── src/api/           # types.gen.ts (OpenAPI) + client fetch + hooks React Query
├── src/components/ui/ # componentes shadcn (card, button, tabs, progress…)
├── src/components/    # GameCard, SortBar, AchievementItem…
├── src/pages/         # Library, GameDetail
└── src/lib/           # queryClient, cn()
```

Regra prática (backend): lógica nova de negócio vai em `services/`; nova chamada
à Steam vira um método em `steam/client.py` que retorna dict desembrulhado ou
levanta exceção tipada. Rotas só orquestram e retornam o modelo (JSON).
Regra prática (frontend): dado novo da API → método em `src/api/client.ts` +
hook React Query; a UI consome o hook. Após mudar modelos no backend, rode
`npm run generate:api` para ressincronizar os tipos.

Wiring do backend no `lifespan` (`main.py`): `httpx.AsyncClient` + `TTLCache` +
`AchievementsService` ficam em `app.state`. Injeção por `Depends(get_service)`.
Contrato de erro: exceções tipadas → `JSONResponse({"detail": …})` com 404/429/502.

## Integração Steam

Endpoints em uso (fonte de verdade: `Steam_Web_API_Documentation.md` do projeto):

| Endpoint | Uso |
|---|---|
| `IPlayerService/GetOwnedGames/v1` | biblioteca + playtime |
| `ISteamUserStats/GetPlayerAchievements/v1` | obtidas/pendentes + % |
| `ISteamUserStats/GetSchemaForGame/v2` | nome/descrição/ícone das conquistas |
| `ISteamUserStats/GetGlobalAchievementPercentagesForApp/v2` | raridade global (param é `gameid`, não `appid`) |

Detalhes que já mordem na prática:
- `GetPlayerAchievements` retorna a lista completa com flag `achieved` (0/1).
  **% e contagem saem daqui** — schema NÃO é necessário para o percentual.
- O campo é `apiname` (não `api_name`). Schema usa `availableGameStats.achievements`
  com `name`/`displayName`/`description`/`icon`.
- Jogo sem stats → `playerstats.success:false`/sem `achievements` →
  tratar como `supports_achievements=False`, nunca quebrar.
- Perfil privado / key inválida (401/403) → `SteamDataUnavailable`.
- 429 e 5xx → retry com backoff no client; acima disso, propagar
  `SteamRateLimitError`/`SteamUnavailableError` (rotas mapeiam p/ 429/502).
- Ícone de jogo: `…/images/apps/{appid}/{img_icon_url}.jpg`.

⚠️ `GetOwnedGames` é oficial da Valve mas **não consta** no doc do projeto. Se
mexer em biblioteca, mantenha o tratamento e não troque por `GetAppList` (este é
o catálogo global, não a conta).

## Convenções de código

- Type hints em tudo; async em I/O. Sem abstrações especulativas — seguir a doc
  oficial, não inventar camadas.
- Cache só via `TTLCache`, sempre pelos helpers do service (chaves
  `owned_games:{steamid}`, `player_ach:{steamid}:{appid}`, `schema:{appid}`,
  `schema_en:{appid}`, `genres:{appid}`, `global_pct:{appid}`,
  `player_summary:{steamid}`, `vanity:{nome}`,
  `dica:{provedor}:{appid}:{apiname}`). É
  volátil e por processo; **não**
  introduzir banco para "guardar histórico" sem aprovação explícita.
- Dois helpers, e a escolha não é estilo: `_cached()` quando erro é erro (propaga);
  `_cached_ou_ausente()` quando o **"não existe" é uma resposta**
  e precisa virar valor no cache. O segundo vale para o que é chaveado por **input
  público** (`player_summary:{steamid}`, `vanity:{nome}`): sem cachear o "não",
  marretar o mesmo ID/nome inexistente queima a quota da chave a cada tentativa.
- O `_cached()` guarda **falha transitória** (`SteamUnavailableError`,
  `SteamRateLimitError`) por `FALHA_TTL` = 60s, re-levantando-a como exceção
  **nova** — nunca como valor, e nunca a instância guardada (traceback acumula).
  Sem isso, um jogo em 5xx consistente faz toda carga da biblioteca re-pagar 3,5s
  de backoff. O critério de inclusão não é "é transitória?", é **"o fetch paga
  retry com backoff?"** — hoje, "passa por `SteamClient._get()`". Nenhuma exceção
  de `ai/` entra: aquela camada não retenta, e o `AiRateLimitError` também vem do
  token bucket local, que se recupera por refill — guardá-lo prolongaria o
  bloqueio na única feature paga. Travado por teste; verificado por mutação.
- ⚠️ Quem lê `self._cache` **direto**, sem passar pelo `_cached()`, precisa checar
  o tipo do que recebeu: a sentinela de falha é um `NamedTuple`, logo *truthy* e
  *iterável*, e um `or []` não a filtra. Hoje há **um** ponto assim (`_name()`), e
  ele já checa. Ao criar o segundo, checar também — ou ler pelo helper.
- `player_ach:{steamid}:{appid}` é a **única** porta para `GetPlayerAchievements`:
  a contagem da biblioteca e a lista do detalhe leem a mesma entrada. Guarda uma
  `Progresso` (`apiname`/`achieved`/`unlocktime`) por conquista — nada além disso.
  Por isso o `GetPlayerAchievements` **não** manda `l=`: o idioma faria a Steam
  incluir `name`/`description` (payload dobra) que o app descartaria, pois o texto
  exibido vem do `schema:{appid}` — chave por **jogo**, compartilhada. Não voltar a
  guardar o payload cru: o teto do cache conta entradas, não bytes.
- `dica:{provedor}:{appid}:{apiname}` é o **único dado pago** do app: cada miss é dinheiro,
  não só cota. Três consequências que não são estilo:
  (1) chave **sem `steamid`** — a Dica é função de (jogo, conquista), então o
  primeiro visitante paga e o resto lê; enriquecer o prompt com dados do jogador
  obrigaria a chavear por pessoa e multiplicaria o custo por visitante;
  (2) o gate roda **antes** de qualquer I/O e na ordem biblioteca → pendente →
  `name_en`, porque `appid` vem da URL e as etapas mais internas já custam
  chamada à Steam;
  (3) `_cached()` e nunca `_cached_ou_ausente()` — com TTL de 7 dias, cachear um
  429 transitório congelaria o painel quebrado por uma semana.
- `global_pct:{appid}` e `schema_en:{appid}` são chaveados pelo **jogo**, não pelo
  jogador: raridade e nome em inglês são os mesmos para todo mundo, então o cache
  é compartilhado entre visitantes. Ambos são **decoração** — falha neles nunca
  pode derrubar o detalhe (o service engole o erro e devolve `{}`). Quando engolir,
  engula **dentro** do `buscar()`, com TTL de miss curto (`*_MISS_TTL`): devolver
  `{}` fora do cache faz cada request re-tentar uma Steam que está em 429.
- `schema_en:{appid}` existe porque `display_name` é pt-BR e a Steam devolve
  **outro texto**, não tradução ("Descanso no Spa" × "Spa Healer"). Guia e vídeo
  de conquista são escritos em inglês, então o nome buscável tem de vir de um
  segundo `GetSchemaForGame` com `l=english`. O `name_en` **não** cai para
  `apiname` quando falta: buscar `ACH_SPA` não acha nada, e link que não acha nada
  é pior que link nenhum.
- O `TTLCache` tem **teto de entradas** (`_MAXSIZE`). Não remover: o `steamid`
  vem da URL (input público), então o espaço de chaves é controlado por quem
  chama — sem teto, IDs sempre novos crescem o dict até derrubar o processo.
- Concorrência ao montar a biblioteca limitada por `Semaphore`
  (`steam_concurrency`) — manter, é o que evita 429 em conta grande.
- O `TokenBucket` vive em `core/rate_limit.py` e cada cliente instancia o seu: a
  lógica é a mesma, os números não. O da Steam protege **cota** (renova); o da IA
  protege **fatura** (não renova), e por isso é uma ordem de grandeza menor.
- Toda chamada com a key passa por um **token bucket global** no `SteamClient`
  (`steam_rate_per_minute`/`steam_rate_burst`): protege a quota da chave contra
  qualquer chamador, inclusive header forjado. Estourou → `SteamRateLimitError`
  → 429. O endpoint de gênero (loja) não passa por ele: não usa a key.
- Comentários e mensagens ao usuário em pt-BR.
- Ao adicionar feature, incluir teste em `tests/` usando um client falso
  (ver `tests/test_service.py`) — domínio é testável sem rede; aproveitar isso.

## Segurança (não negociável)

- `STEAM_API_KEY` e `STEAM_ID` só via env/`.env`. Nunca em resposta da API,
  bundle/resposta do frontend, commit ou log. `.env` está no `.gitignore`.
- A key trafega apenas na querystring server-side (backend → Steam). O frontend
  só fala com `/api`, jamais com a Steam. Não habilitar log `DEBUG` do `httpx`
  (vaza a URL com a chave).

## Antes de propor mudanças grandes

Reintroduzir banco, fila, Redis, OpenID ou multiusuário muda decisões da
arquitetura — **perguntar antes**, não implementar direto.
