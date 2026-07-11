# Roadmap — App de Conquistas Steam

Análise do estado atual e backlog para implementação posterior. Cada item segue
o ciclo do `CLAUDE.md`: `/update-specification` → `/tdd` → RED/GREEN/REFACTOR →
REVIEW → SHIP.

## Estado atual

O projeto está **completo em relação à spec v1.0**
(`spec/spec-architecture-steam-achievements.md`):

- Arquitetura invariante OK: `web/` sem `httpx`, `services/` sem `fastapi`,
  `steam/` como único ponto HTTP. Wiring no `lifespan` de `main.py`.
- 27 testes em 4 arquivos, todos verdes.
- Cache TTL, retry com backoff, Docker (usuário não-root, worker único).

Não há bug grave. O que segue são correções pequenas, features de custo quase
zero e direcionamentos de processo.

## Correções (prioridade)

1. **Commit do baseline** — o repositório não tem nenhum commit; todo o código
   está untracked e pode ser perdido. Passo zero. Usar `/git-commit-assistant`
   ou `/caveman-commit`.
2. **Ícone quebrado quando `img_icon_url` vem vazio** —
   `app/services/achievements.py:36` monta a URL mesmo com hash `""`, gerando
   `…/apps/{appid}/.jpg` (imagem quebrada). O template testa
   `{% if game.icon_url %}`, mas a URL nunca é vazia. Fix: `icon_url=None`
   quando `img_icon_url` for falsy. Teste: jogo sem ícone → `icon_url is None`.
3. **`<h1>` vazio no detalhe quando o schema não tem `gameName`** —
   `game_detail` usa só o schema para o nome; jogo sem schema renderiza título
   vazio. Fix: fallback para o nome vindo de `owned_games` (já em cache) ou,
   em último caso, `f"App {appid}"`.
4. *(opcional, micro)* Detalhe não semeia o cache `ach_counts:{appid}` — visitar
   um jogo e depois ordenar por % refaz a chamada. Só vale se incomodar.

## Features de custo quase zero (sem endpoint novo)

1. **Data de desbloqueio das conquistas** — `GetPlayerAchievements` já retorna
   `unlocktime` (`Steam_Web_API_Documentation.md:101`). Exibir "obtida em
   dd/mm/aaaa" no detalhe e ordenar obtidas por data. Melhor relação
   valor/custo do backlog.
2. **Busca por nome na index** — filtro client-side (JS), mesmo padrão do
   filtro de status do detalhe (REQ-007). Zero chamadas extras.
3. **Resumo no topo da index** — nº de jogos, horas totais; em `sort=percent`,
   contagem de jogos 100% ("perfect games"). Só agregação do que já está na
   lista.
4. **Badge "jogado recentemente"** — `playtime_2weeks` já vem no
   `GetOwnedGames` (o campo só aparece se houve jogo recente; conferir no
   payload).

## Features médias (exigem atualizar doc + spec antes)

5. **Raridade global das conquistas** — endpoint
   `ISteamUserStats/GetGlobalAchievementPercentagesForApp/v2` ("só X% dos
   jogadores têm essa"). **Não consta** no `Steam_Web_API_Documentation.md`
   (fonte de verdade) — adicionar ao doc e à spec antes de implementar.
6. **Ordenação por "última vez jogado"** — `rtime_last_played` do
   `GetOwnedGames`; também precisa entrar no doc.

## Direcionamentos (processo/infra)

- **CI mínimo** quando o repo subir para GitHub: workflow com `uv sync` +
  `uv run pytest`.
- **Manter o escopo fechado**: nada de banco/histórico/multiusuário. Qualquer
  feature de "evolução no tempo" (ex.: gráfico de progresso) exige persistência
  e abre um novo ciclo de arquitetura — recusar por ora.

## Sequência recomendada

1. Commit do baseline (correção nº 1).
2. Correções 2 e 3 (um ciclo TDD curto cada).
3. Feature 1 (unlocktime) — nova iteração SDD via `/update-specification`.
4. Features 2–3 conforme apetite.

## Verificação

- `uv run pytest` verde após cada ciclo.
- `/verify` no app real: index com jogo sem ícone não mostra imagem quebrada;
  detalhe de jogo sem schema mostra nome de fallback; datas de desbloqueio
  visíveis nas conquistas obtidas.
