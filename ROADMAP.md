# Roadmap — App de Conquistas Steam

Análise do estado atual e backlog para implementação posterior. Cada item segue
o ciclo do `CLAUDE.md`: `/update-specification` → `/tdd` → RED/GREEN/REFACTOR →
REVIEW → SHIP.

## Estado atual

O app não é mais o server-rendered da spec v1.0: virou **API JSON (FastAPI) +
SPA React**, com o `steamid` vindo da URL (multiusuário de leitura, sem login).

- Arquitetura invariante OK: `web/` sem `httpx`, `services/` sem `fastapi`,
  `steam/` como único ponto HTTP. Wiring no `lifespan` de `main.py`.
- **68 testes no backend** (pytest) + **31 no frontend** (Vitest), verdes.
- Cache TTL com teto de entradas, retry com backoff, token bucket global na
  saída para a Steam, `Semaphore` no fan-out, validação do Steam ID na entrada.
- Deploy: SPA na Vercel (rewrite `/api/*`), API pelo `Dockerfile`.

Não há bug grave. O que segue são correções pequenas, features de custo quase
zero e direcionamentos de processo.

## Correções (prioridade)

1. ~~**Commit do baseline**~~ — ✅ feito.
2. ~~**Ícone quebrado quando `img_icon_url` vem vazio**~~ — ✅ feito (commit
   `70b5436`): `icon_url=None` quando o hash é falsy, com teste.
3. ~~**Nome vazio no detalhe quando o schema não tem `gameName`**~~ — ✅ feito:
   `game_detail` cai em `gameName` → nome da biblioteca em cache → `App {appid}`.
4. *(opcional, micro)* Detalhe não semeia o cache `ach_counts:{steamid}:{appid}`
   — `game_detail` chama o client direto, fora do `_cached()`. Visitar um jogo e
   depois ordenar por % refaz a chamada. Só vale se incomodar.

## Features de custo quase zero (sem endpoint novo) — ✅ entregues

Todas as quatro estão implementadas (REQ-030 a REQ-033 na spec). Nenhuma tocou
`steam/client.py`: custo de quota zero, como previsto.

1. ~~**Data de desbloqueio das conquistas**~~ — `Achievement.unlocked_at` (ISO-8601)
   vem do `unlocktime`; o detalhe mostra "Obtida em dd/mm/aaaa" e ordena obtidas
   da mais recente para a mais antiga (pendentes por último).
2. ~~**Busca por nome na index**~~ — filtro client-side em `Library.tsx`, estado
   local (não vai para a URL).
3. ~~**Resumo no topo da index**~~ — nº de jogos · horas totais · nº de jogos
   100% (este só quando há dados de conquista, i.e. `sort=percent`/`ach_count`).
   Reflete a lista já filtrada pela busca.
4. ~~**Badge "jogado recentemente"**~~ — `Game.playtime_2weeks_minutes` do
   `playtime_2weeks`. ⚠️ **Falta confirmar no payload real** que a Steam manda o
   campo; se não mandar, o badge só não aparece (degrada sozinho).

## Features médias (exigem atualizar doc + spec antes)

5. **Raridade global das conquistas** — endpoint
   `ISteamUserStats/GetGlobalAchievementPercentagesForApp/v2` ("só X% dos
   jogadores têm essa"). **Não consta** no `Steam_Web_API_Documentation.md`
   (fonte de verdade) — adicionar ao doc e à spec antes de implementar.
6. **Ordenação por "última vez jogado"** — `rtime_last_played` do
   `GetOwnedGames`; também precisa entrar no doc.

## Direcionamentos (processo/infra)

- **Dívida: a spec está estruturalmente defasada.** Recebeu os REQ-030 a REQ-033
  em atualização pontual, mas as seções antigas ainda descrevem o app
  server-rendered (rota `GET /`, template Jinja) em vez da API `/api/users/...`
  + SPA. Um rewrite v2 é um ciclo SDD próprio.
- **CI mínimo** quando o repo subir para GitHub: workflow com `uv sync` +
  `uv run pytest`.
- **Manter o escopo fechado**: nada de banco/histórico/multiusuário. Qualquer
  feature de "evolução no tempo" (ex.: gráfico de progresso) exige persistência
  e abre um novo ciclo de arquitetura — recusar por ora.

## Sequência recomendada

1. `/verify` no app real — em especial confirmar o `playtime_2weeks` no payload.
2. Features médias 5–6, cada uma abrindo seu ciclo SDD (doc + spec antes).
3. Correção 4 (micro) só se o refetch incomodar na prática.

## Verificação

- `uv run pytest` e `npm run test` verdes após cada ciclo.
- `/verify` no app real: datas de desbloqueio visíveis e ordenadas; busca
  filtrando o grid e o resumo; badge "Recente" em jogo jogado nas últimas 2
  semanas.
