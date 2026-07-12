# Roadmap — App de Conquistas Steam

Controle do que já foi entregue e do que falta. Cada item aberto segue o ciclo do
`CLAUDE.md`: `/update-specification` → `/tdd` → RED/GREEN/REFACTOR → REVIEW → SHIP.

## Estado atual

O app não é mais o server-rendered da spec v1.0: virou **API JSON (FastAPI) +
SPA React**, com o `steamid` vindo da URL (multiusuário de leitura, sem login).

- Arquitetura invariante OK: `web/` sem `httpx`, `services/` sem `fastapi`,
  `steam/` como único ponto HTTP. Wiring no `lifespan` de `main.py`.
- **77 testes no backend** (pytest) + **41 no frontend** (Vitest), verdes.
- Cache TTL com teto de entradas, retry com backoff, token bucket global na
  saída para a Steam, `Semaphore` no fan-out, validação do Steam ID na entrada.
- Deploy: SPA na Vercel (rewrite `/api/*`), API pelo `Dockerfile`.

Não há bug grave conhecido.

## Correções

- [x] **Commit do baseline.**
- [x] **Ícone quebrado quando `img_icon_url` vem vazio** (commit `70b5436`):
      `icon_url=None` quando o hash é falsy, com teste.
- [x] **Nome vazio no detalhe quando o schema não tem `gameName`**: `game_detail`
      cai em `gameName` → nome da biblioteca em cache → `App {appid}`.
- [ ] *(micro, opcional)* **Detalhe não semeia o cache `ach_counts:{steamid}:{appid}`**
      — `game_detail` chama o client direto, fora do `_cached()`. Visitar um jogo
      e depois ordenar por % refaz a chamada. Só vale se incomodar na prática.

## Features de custo zero de quota (REQ-030 a REQ-033)

Todas entregues. Nenhuma tocou `steam/client.py`: derivam de campos que já vinham
nos payloads existentes.

- [x] **Data de desbloqueio das conquistas** — `Achievement.unlocked_at` (ISO-8601)
      vem do `unlocktime`; o detalhe mostra "Obtida em dd/mm/aaaa" e ordena obtidas
      da mais recente para a mais antiga (pendentes por último).
- [x] **Busca por nome na biblioteca** — filtro client-side em `Library.tsx`, estado
      local (não vai para a URL).
- [x] **Resumo no topo da biblioteca** — nº de jogos · horas totais · nº de jogos
      100% (este só quando há dados de conquista, i.e. `sort=percent`/`ach_count`).
      Reflete a lista já filtrada pela busca.
- [x] **Badge "jogado recentemente"** — `Game.playtime_2weeks_minutes` do
      `playtime_2weeks`.
- [ ] ⚠️ **Confirmar `playtime_2weeks` no payload real.** Nunca foi verificado com
      uma `STEAM_API_KEY` de verdade. Se a Steam não mandar o campo, o badge só
      não aparece (degrada sozinho) — mas é uma incógnita aberta. Cai no `/verify`.

## Features médias (REQ-040 a REQ-042)

Exigiram documentar campo/endpoint no `Steam_Web_API_Documentation.md` e na spec
antes de implementar — feito.

- [x] **Raridade global das conquistas** (REQ-040/041) —
      `ISteamUserStats/GetGlobalAchievementPercentagesForApp/v2` (parâmetro
      `gameid`, não `appid`). O detalhe mostra "4,1% dos jogadores" e um badge
      "Rara" abaixo de 10%. Best-effort: jogo sem stats globais renderiza sem
      raridade, nunca quebra. Cache `global_pct:{appid}` — por **jogo**, não por
      jogador, então é compartilhado entre visitantes. É a **única** feature
      pós-v1.0 que custa quota: +1 chamada por jogo no detalhe.
- [x] **Ordenação por "última vez jogado"** (REQ-042) — `sort=last_played`, do
      `rtime_last_played` do `GetOwnedGames`. Custo zero: o campo já vinha no
      payload. Nunca jogado (`0`/ausente) vai para o fim. O card exibe a data.
- [ ] ⚠️ **Confirmar `rtime_last_played` no payload real** — mesma incógnita do
      `playtime_2weeks`. Se a Steam não mandar, a ordenação empata tudo e a
      feature precisa ser repensada. Cai no `/verify`.

## Dívida / processo

- [ ] **A spec está estruturalmente defasada.** Recebeu REQ-030..033 e REQ-040..042
      em atualizações pontuais, mas as seções antigas ainda descrevem o app
      server-rendered (rota `GET /`, template Jinja) em vez da API
      `/api/users/...` + SPA. Um rewrite v2 é um ciclo SDD próprio.
- [ ] **O doc da Steam não cobre 2 endpoints que o client já chama**:
      `ISteamUser/GetPlayerSummaries/v2` e o `store/appdetails` (gêneros, sem key).
      O doc é a fonte de verdade — a lacuna é anterior às features médias.
- [ ] **CI mínimo** quando o repo subir para GitHub: workflow com `uv sync` +
      `uv run pytest` e `npm ci` + `npm run test`.
- [ ] **Manter o escopo fechado**: nada de banco/histórico/multiusuário. Qualquer
      feature de "evolução no tempo" (ex.: gráfico de progresso) exige persistência
      e abre um novo ciclo de arquitetura — recusar por ora.

## Verificação

- `uv run pytest` e `npm run test` verdes após cada ciclo.
- `/verify` no app real, onde caem as incógnitas de payload acima:
  - `?sort=last_played` ordena de verdade (⇒ `rtime_last_played` existe);
  - badge "Recente" aparece em jogo das últimas 2 semanas (⇒ `playtime_2weeks`);
  - detalhe de um jogo popular traz `global_percent`; um jogo obscuro **sem**
    stats globais abre normalmente, sem raridade e **sem 500**.
