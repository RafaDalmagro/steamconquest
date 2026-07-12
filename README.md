# Steam Conquest

App web pessoal para acompanhar conquistas, biblioteca e tempo de jogo de uma
conta Steam. Single-user, consulta em tempo real (sem banco de dados).

- **Biblioteca**: jogos + playtime, ordenação por nome/playtime/% de
  conquistas, agrupamento por gênero.
- **Detalhe do jogo**: conquistas obtidas × pendentes, progresso % e filtro
  por status.

## Stack

- **Backend**: Python 3.12 · FastAPI · httpx (async) · pydantic-settings ·
  pytest. Gerenciador: [uv](https://docs.astral.sh/uv/).
- **Frontend**: React 19 · Vite · TypeScript · Tailwind v4 · shadcn/ui ·
  TanStack React Query. Gerenciador: npm.

O backend expõe uma API JSON sob `/api` (a única camada que fala com a Steam);
o frontend é um SPA que consome essa API. Em produção o FastAPI serve o build
estático do frontend; em dev o Vite serve o SPA com proxy `/api` → FastAPI.

## Como rodar

### 1. Configurar a chave da Steam

```bash
cp .env.example .env
# edite .env e informe STEAM_API_KEY (https://steamcommunity.com/dev/apikey)
```

O SteamID64 da conta a consultar é informado na Home do app, não no `.env`.
Mantenha `ENVIRONMENT=dev` localmente (é o default).

### 2. Backend

```bash
uv sync
uv run uvicorn app.main:app --reload   # http://localhost:8000
uv run pytest                          # testes
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev            # http://localhost:5173 (proxy /api -> :8000)
npm run test           # testes (Vitest)
npm run generate:api   # regenera tipos TS a partir do /openapi.json (backend up)
```

### Docker (app completo, simulando produção)

```bash
docker compose up --build   # http://localhost:8000 (ENVIRONMENT=prod: sem /docs)
```

## Ambientes

| Variável | Onde vive | Dev | Prod |
| --- | --- | --- | --- |
| `STEAM_API_KEY` | backend (`.env` / painel do host) | sua chave | sua chave |
| `ENVIRONMENT` | backend | `dev` (default) | `prod` |
| `CORS_ORIGINS` | backend | vazio | vazio (ver abaixo) |
| `UVICORN_LOG_LEVEL` | backend | `debug` se precisar | `info` |
| `VITE_API_BASE_URL` | frontend (`frontend/.env`) | vazio | vazio (ver abaixo) |

Em **dev**, o proxy do Vite (`vite.config.ts`) encaminha `/api` → `:8000`.
Em **prod**, o rewrite do `frontend/vercel.json` encaminha `/api` → a API
hospedada. Nos dois casos o browser vê **same-origin**: por isso `CORS_ORIGINS` e
`VITE_API_BASE_URL` ficam vazios. Só preencha os dois (origem exata da Vercel e
URL absoluta da API) se remover o rewrite e falar cross-origin direto.

`ENVIRONMENT=prod` desliga `/docs`, `/redoc` e `/openapi.json` — em dev eles
ficam ativos porque `npm run generate:api` lê o schema.

### Deploy

- **Frontend** → Vercel, root directory `frontend/`. O rewrite do `vercel.json`
  aponta para a URL da API; atualize-o se a API mudar de host.
- **Backend** → qualquer host que builde o `Dockerfile`. Configure
  `STEAM_API_KEY` e `ENVIRONMENT=prod` no painel do host (nunca commitados).

## Fora de escopo

Multiusuário, login Steam OpenID, comparação entre jogos, histórico/snapshots
e qualquer persistência relacional.
