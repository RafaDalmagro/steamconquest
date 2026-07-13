# Roadmap — App de Conquistas Steam

Controle do que já foi entregue e do que falta. Cada item aberto segue o ciclo do
`CLAUDE.md`: `/update-specification` → `/tdd` → RED/GREEN/REFACTOR → REVIEW → SHIP.

## Estado atual

O app não é mais o server-rendered da spec v1.0: virou **API JSON (FastAPI) +
SPA React**, com o `steamid` vindo da URL (multiusuário de leitura, sem login).

- Arquitetura invariante OK: `web/` sem `httpx`, `services/` sem `fastapi`,
  `steam/` como único ponto HTTP. Wiring no `lifespan` de `main.py`.
- **80 testes no backend** (pytest) + **41 no frontend** (Vitest), verdes.
- Cache TTL com teto de entradas, retry com backoff, token bucket global na
  saída para a Steam, `Semaphore` no fan-out, validação do Steam ID na entrada.
- Deploy: SPA na Vercel (rewrite `/api/*`), API pelo `Dockerfile`.
- **CI no GitHub Actions**: testes do backend e do frontend + build (`tsc -b`).
- Docs em dia: a spec (v2.0) e o `Steam_Web_API_Documentation.md` descrevem o app
  que existe de verdade — os dois são fonte de verdade citada pelo `CLAUDE.md`.

Não há bug grave conhecido.

## Correções

- [x] **Commit do baseline.**
- [x] **Ícone quebrado quando `img_icon_url` vem vazio** (commit `70b5436`):
      `icon_url=None` quando o hash é falsy, com teste.
- [x] **Nome vazio no detalhe quando o schema não tem `gameName`**: `game_detail`
      tem fallback triplo até `App {appid}`.
- [x] **Codinome interno no lugar do nome do jogo** (achado pelo `/verify`): o
      `gameName` do schema às vezes é o codinome do estúdio — o detalhe do
      Remnant II exibia **"GFREMP2"**. A ordem do fallback foi invertida: a
      biblioteca (nome da loja) vem primeiro, o schema só vale para deep-link.
- [x] ~~*(micro, opcional)* **Detalhe não semeia o cache `ach_counts`**~~ —
      **decidido: não fazer.** Semear a tupla economizaria 1 chamada em 155, e só
      na ordem detalhe→biblioteca. A ordem inversa (a comum) o cache não resolve:
      `game_detail` precisa da lista crua, que a tupla não reconstrói — e cachear
      a lista crua por `steamid × appid` significaria 155 payloads gordos por
      visitante (o client pede `l=brazilian`, então vêm `name` e `description`)
      num `TTLCache` cujo teto conta entradas, não bytes. A tupla é decisão de
      design, não pendência.
- [x] **Decisão acima revertida** (revisão de arquitetura, jul/2026): `ach_counts`
      virou `player_ach:{steamid}:{appid}` e passou a ser a **única** porta para o
      `GetPlayerAchievements` — biblioteca e detalhe leem a mesma entrada. O que
      derrubou a objeção de memória foi notar que o app **descarta** o `name` e a
      `description` do payload do jogador (o texto exibido vem do `schema:{appid}`,
      cacheado por jogo): a entrada guarda só `apiname`/`achieved`/`unlocktime`, e
      o cache deixa de inflar. Sai a tupla, sai o sentinela `(0, 0)`, sai o método
      `_ach_counts` — e o detalhe aberto após `include=achievements` não paga mais
      uma segunda ida à Steam. Invariante travada em
      `test_cache_de_conquistas_nao_guarda_o_payload_gordo_da_steam`.
- [x] **Jogo sem conquistas nunca entrava no cache** (achado ao investigar o item
      acima): `_ach_counts` devolvia `None`, que é o próprio sinal de miss do
      `_cached()` — então **todo** load com `?sort=percent` re-consultava a Steam
      para **todos** os jogos sem conquistas da biblioteca, para sempre. Agora
      devolve `(0, 0)` e o cache negativo pega, como já era em `genres` e
      `global_pct`. O jogo segue sem % na tela (nada de 0/0).

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
- [x] **`playtime_2weeks` confirmado no payload real** (`/verify` de 12/07/2026):
      o campo simplesmente **não vem** quando não houve jogo nas últimas 2
      semanas — nem como `0`. A ausência é o caso normal e o badge degrada
      sozinho, como previsto. Falta ver o badge **aceso** num jogo recente.

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
- [x] **`rtime_last_played` confirmado no payload real** (`/verify` de 12/07/2026):
      vem nos **155 jogos** da biblioteca, com valor em 134 e `0` em 21 (nunca
      jogados). A ordenação foi verificada ponta a ponta contra a Steam.
- [x] **Raridade verificada contra a Steam**: 65/65 conquistas com percentual num
      jogo real; jogo sem stats globais devolve **403** → detalhe abre sem
      raridade, sem 500. ⚠️ A Steam manda `percent` como **string** (`"49.9"`) —
      o client converte na fronteira (commit `2e27719`).

## Correções pendentes

- [ ] **Um jogo quebrado custa ~4,5s em toda carga da biblioteca** (achado pelo
      `/verify` da revisão de arquitetura, jul/2026). O `GetPlayerAchievements` do
      **appid 1966720 (Lethal Company)** devolve 5xx de forma consistente. O client
      retenta 4× com backoff exponencial (0,5 + 1 + 2 = **3,5s dormindo**) e só
      então levanta; o fan-out engole o erro (best-effort, correto) — mas a
      **latência** não é engolida: `asyncio.gather` espera o jogo quebrado. Medido
      com o cache quente: **4,7s** de resposta, dos quais ~4,5s são esse único jogo
      (154 dos 155 jogos vêm do cache).
      Falha **não** é cacheada, e isso está certo: 5xx pode ser transitório. A saída
      provável é um **cache negativo curto para a falha** (~60s), no mesmo espírito
      do CON-011 que já vale para gênero e raridade — "falhou agora há pouco, não
      re-pague o backoff neste load". Deixaria a carga quente em ~0,1s.
      Pré-existente: o antigo `_ach_counts` também não cacheava falha. Precisa de
      ciclo SDD próprio (muda CON-011 e a tabela de TTLs).

## Dívida / processo

- [x] **Spec reescrita para v2.0.** As seções antigas descreviam o app
      server-rendered (rota `GET /`, Jinja2, `STEAM_ID` via env, "exposição só em
      localhost") — tudo morto. Além de corrigir, a v2.0 **escreve os requisitos
      das features que já estavam entregues e nunca especificadas**: REQ-050
      (`group=genre`), REQ-051 (`/profile` + desempate de erro), REQ-052 (steamid
      de 17 dígitos → 422), REQ-053 (token bucket) e REQ-054 (teto do `TTLCache`).
      Mentir por omissão era metade da dívida.
- [x] **Doc da Steam completo**: §5 `ISteamUser/GetPlayerSummaries/v2` (com a nota
      que faltava: `players: []` **só** ocorre com SteamID inexistente — perfil
      privado devolve o player; é isso que separa 404 "não existe" de 404
      "privado") e §6 `store/appdetails` (não-oficial, sem key, `data: []` é
      **lista** e não dict, rate-limita agressivo).
- [x] **CI no GitHub Actions** (`.github/workflows/ci.yml`): dois jobs em paralelo
      — `uv sync` + `uv run pytest`; `npm ci` + `npm run test` + `npm run build`. O
      build entra porque roda `tsc -b`: é o que barra erro de tipagem no CI em vez
      de no deploy da Vercel (ver commit `bee0015`). Sem segredos: os testes não
      tocam a rede, então o job usa `STEAM_API_KEY: dummy-ci-key` — a chave real
      nunca vai para o CI.
- Removido daqui: *"manter o escopo fechado"*. Não é tarefa — é regra permanente,
  um `[ ]` que nunca viraria `[x]`, e já vive no `CLAUDE.md` ("Antes de propor
  mudanças grandes").

## Verificação

- `uv run pytest` e `npm run test` verdes após cada ciclo.
- `/verify` no app real, onde caem as incógnitas de payload acima:
  - `?sort=last_played` ordena de verdade (⇒ `rtime_last_played` existe);
  - badge "Recente" aparece em jogo das últimas 2 semanas (⇒ `playtime_2weeks`);
  - detalhe de um jogo popular traz `global_percent`; um jogo obscuro **sem**
    stats globais abre normalmente, sem raridade e **sem 500**.
