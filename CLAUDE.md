# CLAUDE.md

Instruções de projeto para o Claude Code. Leia antes de editar.

## O que é

App web **pessoal** para acompanhar conquistas, biblioteca e tempo de jogo de
uma conta Steam. **Single-user**, consulta em **tempo real (sem banco)**, render
**server-side** com Jinja2.

Escopo fechado na entrevista de arquitetura — não expandir sem pedir:
- Funcionalidades: biblioteca + playtime; conquistas obtidas × pendentes;
  progresso % por jogo; ordenação (biblioteca) e filtro por status (detalhe).
- **Fora de escopo agora:** multiusuário, login Steam OpenID, comparação entre
  jogos, histórico/snapshots, qualquer persistência relacional.

## Stack

Python 3.12 · FastAPI · uvicorn · httpx (async) · Jinja2 · pydantic-settings ·
pytest. Gerenciador: **uv**. Deploy: Docker.

## Comandos

```bash
uv sync                                      # instala deps
uv run uvicorn app.main:app --reload         # dev server (http://localhost:8000)
uv run pytest                                # testes
docker compose up --build                    # container
```

Terminal alvo: Linux nativo (zsh).

## Arquitetura — invariante (não quebrar)

Dependências apontam sempre para o domínio. Concretamente:

- `web/` (rotas) **não** importa `httpx` nem conhece a Steam direto.
- `services/` **não** importa `Request`/`fastapi`.
- `steam/` é a única camada que fala HTTP com a Steam.

```
app/
├── config.py          # Settings via env (segredos)
├── core/cache.py      # TTLCache em memória — volátil, NÃO é banco
├── steam/             # Infra HTTP (client + exceptions tipadas)
├── services/          # Regra de negócio (achievements.py)
├── schemas/models.py  # Modelos de domínio (pydantic)
├── web/routes.py      # Rotas + templates
├── templates/         # base / index / game
└── main.py            # FastAPI + lifespan (wiring do client/cache/service)
```

Regra prática: lógica nova de negócio vai em `services/`; nova chamada à Steam
vira um método em `steam/client.py` que retorna dict já desembrulhado ou levanta
exceção tipada. Rotas só orquestram e renderizam.

Wiring é feito no `lifespan` (`main.py`): `httpx.AsyncClient` + `TTLCache` +
`AchievementsService` ficam em `app.state`. Injeção por `Depends(get_service)`.

## Integração Steam

Endpoints em uso (fonte de verdade: `Steam_Web_API_Documentation.md` do projeto):

| Endpoint | Uso |
|---|---|
| `IPlayerService/GetOwnedGames/v1` | biblioteca + playtime |
| `ISteamUserStats/GetPlayerAchievements/v1` | obtidas/pendentes + % |
| `ISteamUserStats/GetSchemaForGame/v2` | nome/descrição/ícone das conquistas |

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
- Cache só via `TTLCache` (chaves: `owned_games`, `ach_counts:{appid}`). É
  volátil e por processo; **não** introduzir banco para "guardar histórico"
  sem aprovação explícita.
- Concorrência ao montar a biblioteca limitada por `Semaphore`
  (`steam_concurrency`) — manter, é o que evita 429 em conta grande.
- Comentários e mensagens ao usuário em pt-BR.
- Ao adicionar feature, incluir teste em `tests/` usando um client falso
  (ver `tests/test_service.py`) — domínio é testável sem rede; aproveitar isso.

## Segurança (não negociável)

- `STEAM_API_KEY` e `STEAM_ID` só via env/`.env`. Nunca em template, resposta,
  commit ou log. `.env` está no `.gitignore`.
- A key trafega apenas na querystring server-side. Não habilitar log `DEBUG` do
  `httpx` (vaza a URL com a chave).

## Antes de propor mudanças grandes

Reintroduzir banco, fila, Redis, OpenID ou multiusuário muda decisões da
arquitetura — **perguntar antes**, não implementar direto.
