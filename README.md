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

### Docker (app completo)

```bash
docker compose up --build   # http://localhost:8000
```

## Fora de escopo

Multiusuário, login Steam OpenID, comparação entre jogos, histórico/snapshots
e qualquer persistência relacional.
