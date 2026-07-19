# Roadmap — App de Conquistas Steam

Controle do que já foi entregue e do que falta. Cada item aberto segue o ciclo do
`CLAUDE.md`: `/update-specification` → `/tdd` → RED/GREEN/REFACTOR → REVIEW → SHIP.

## Estado atual

O app não é mais o server-rendered da spec v1.0: virou **API JSON (FastAPI) +
SPA React**, com o `steamid` vindo da URL (multiusuário de leitura, sem login).

- Arquitetura invariante OK: `web/` sem `httpx`, `services/` sem `fastapi`,
  `steam/` como único ponto HTTP. Wiring no `lifespan` de `main.py`.
- **94 testes no backend** (pytest) + **52 no frontend** (Vitest), verdes.
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
- [x] **Busca por nome na biblioteca** — filtro client-side em `Library.tsx`.
      ⚠️ **Corrigido em 19/07/2026:** esta linha dizia "estado local (não vai para a
      URL)". Era verdade quando foi escrita e deixou de ser. A busca **está na URL**
      como `q`, com `replace: true` (digitar não empilha uma entrada de histórico
      por tecla) e o default omitido (URL limpa) — junto de `sort` e `group`. O
      REQ-031 da spec de arquitetura carregava o mesmo erro e foi corrigido no
      mesmo commit.
- [x] **Resumo no topo da biblioteca** — nº de jogos · horas totais · nº de jogos
      100% (este só quando há dados de conquista, i.e. `sort=percent`/`ach_count`).
      Reflete a lista já filtrada pela busca.
- [x] **Badge "jogado recentemente"** — `Game.playtime_2weeks_minutes` do
      `playtime_2weeks`.
- [x] **`playtime_2weeks` confirmado no payload real** (`/verify` de 12/07/2026):
      o campo simplesmente **não vem** quando não houve jogo nas últimas 2
      semanas — nem como `0`. A ausência é o caso normal e o badge degrada
      sozinho, como previsto. Falta ver o badge **aceso** num jogo recente.
- [x] **Ordenação por raridade no detalhe e "quase lá" na biblioteca**
      (`spec-design-ordenacao-derivada.md`). Zero chamada nova: os dois eixos
      ordenam dado que já estava na tela. Três opções explícitas no detalhe
      (Desbloqueio / Mais fáceis / Mais raras) em vez de derivar a direção da aba
      ativa — a aba "Todas" não teria resposta óbvia, e "quais pendentes são as
      mais raras" é pergunta legítima que a derivação apagaria.
      Três achados que só a leitura do código deu:
      (1) o `includesFor()` precisou incluir `quase_la` — sem `include=achievements`
      o `percent` vem `null` para todos e o botão não reordenaria nada;
      (2) o `setParams` do detalhe substituía a **querystring inteira**, então com
      um segundo parâmetro trocar de aba apagaria a ordenação. Virou um `update()`
      combinado, como o da Library. O teste dessa regressão foi escrito **antes**
      de os comparadores existirem, quando ela ainda não era visível ao usuário;
      (3) nenhum teste do projeto lia a URL após uma interação (o `MemoryRouter`
      não toca `window.location`) — daí o `capturaUrl()` novo em `test/utils.tsx`.
      ⚠️ Duas fixtures de teste **não** podem se chamar "Rara": o `AchievementItem`
      renderiza um badge com esse texto abaixo de 10%, e a busca por texto acha dois.
- [x] **`/verify` da ordenação derivada** (19/07/2026, perfil de demonstração):
      biblioteca com `sort=quase_la` traz os três "quase lá" no topo — Paladins
      47/58, Tribes of Midgard 21/26, Tails of Iron 29/36. Todos exibem "81%", mas
      os valores reais (81,03 > 80,77 > 80,56) confirmam que a ordem **dentro** do
      grupo está certa; o arredondamento é que a esconde. Os 100% ficam fora do
      grupo, como deve. O resumo do topo já dizia "3 jogos quase 100%" e bate
      exatamente: resumo e eixo leem a mesma `isQuaseLa()` (CON-161 se pagando).
      Detalhe de Tails of Iron, `filter=locked&ordem=raras`: 4,5% → 13,1% → 13,1%
      → 15,0% → 15,4% → 15,8% → 17,6%, com o badge "Rara" na do topo. Trocar para
      a aba Obtidas levou a URL a `?filter=achieved&ordem=faceis` — **a ordenação
      sobreviveu**, que é a regressão da Task 2 confirmada fora do jsdom.
      A dúvida visual ("duas barras empilhadas ficariam apertadas?") **não se
      confirmou**: o rótulo "Ordenar:" separa bem a barra nova das abas, e os seis
      botões da biblioteca cabem numa linha em desktop.
      ⚠️ **Não verificado no app real:** jogo sem stats globais, onde o controle
      deve sumir (AC-166). Varri 14 appids da biblioteca e **nenhum** tem todas as
      conquistas sem raridade, então a condição não ocorre neste perfil. O caso
      segue coberto só por teste unitário. Fica registrado para quem topar com um.

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

- [x] **Um jogo quebrado custa ~4,5s em toda carga da biblioteca** (achado pelo
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
      **Entregue** (19/07/2026, spec
      `spec/spec-design-cache-negativo-falha-transitoria.md`). A guarda vive no
      `_cached()` **compartilhado**, não em `_player_achievements`: assim vale de
      graça para `owned_games` e `schema`, e o próximo chamador não nasce quebrado
      por omissão. A falha vira sentinela com TTL **próprio** de 60s (`FALHA_TTL`)
      e volta como exceção **nova** — não como valor, porque `[]` já significa
      "jogo sem conquistas" e o detalhe passaria a afirmar isso sobre um jogo que
      só está fora do ar.
      Dois achados que só apareceram fazendo:
      (1) a spec v1.0 mandava guardar as falhas de IA alegando que eram
      retentadas — **não são** (a camada `ai/` só tem token bucket, sem backoff), e
      guardar `AiRateLimitError` *prolongaria* um bloqueio que o bucket resolve em
      ~30s. Corrigido na v1.1 e travado por teste + verificação por mutação;
      (2) `_name()` lê o cache **direto**, sem passar pelo helper, e recebia a
      sentinela — que é `NamedTuple`, logo truthy e iterável, então o `or []` não
      protegia. Pego por **teste pré-existente**
      (`test_falha_ao_buscar_o_nome_de_loja_nao_derruba_o_detalhe`), não por teste
      novo. Registrado no CON-142 e no `CLAUDE.md`.
      Latência medida no `/verify` de 19/07/2026, biblioteca de 155 jogos com o
      1966720 presente: carga quente de **4,7s → 0,006–0,068s**. O detalhe do jogo
      quebrado devolve **502 em 0,003s** (não 200 com `supports_achievements:false`
      — AC-145 vale no app real, não só no teste).
      A prova de que o ganho é da guarda, e não do cache que já existia: esperar os
      60s do `FALHA_TTL` e repetir devolve **502 em 5,33s** (o backoff de verdade);
      a chamada seguinte volta a **0,003s**. Três ordens de grandeza, ligadas e
      desligadas pelo TTL da sentinela.

## Identificação do perfil (REQ-060 a REQ-062)

O usuário **não sabe** o próprio SteamID64 — ele tem o link ou o nome do perfil.
Hoje o campo exige 17 dígitos, então colar `steamcommunity.com/id/<nome>` dá
"Informe um SteamID64 válido": um beco sem saída disfarçado de validação OK.

Nasceu como "um tutorial passo a passo para o usuário achar o ID dele" e virou
outra coisa no grilling: **ensinar o usuário a extrair 17 dígitos de uma URL é
pedir que ele faça no olho o que uma regex faz numa linha** — e para o link
`/id/<nome>` nem no olho dá, porque o ID não está lá. O tutorial caiu de feature
a fallback de três frases (REQ-062), e a feature virou "aceitar o que o usuário
já tem na mão".

- [x] **Fase 0 — docs primeiro** (como nas features médias acima):
      `Steam_Web_API_Documentation.md` §7 (`ISteamUser/ResolveVanityURL/v1`),
      spec (REQ-060..062, AC-060..065) e este item.
- [x] **Ciclo 1 — `SteamClient.resolve_vanity_url()`**: devolve o steamid; ⚠️
      `success: 42` vem com **HTTP 200** — quem olhar o status acha que deu certo
      e estoura no `KeyError`. Levanta `SteamVanityNotFound` (novo em `errors.py`).
      Herda retry, backoff e token bucket do `_get()`: zero código de quota.
- [x] **Ciclo 2 — `AchievementsService.resolve_vanity()`**: cache `vanity:{nome}`,
      positivo (300s) **e negativo** (60s, sentinela `_NAO_EXISTE`, igual ao
      `player_summary`). TTL curto no negativo porque nome livre hoje pode ser
      registrado amanhã.
- [x] **Ciclo 3 — `GET /api/resolve?vanity=`**: 200 `{"steamid"}` (modelo novo —
      o `PlayerSummary` **continua sem steamid**); 422 fora do formato (2–32,
      `[A-Za-z0-9_-]`) **antes** de virar chave de cache; 404 com mensagem própria
      (a atual manda "conferir os 17 dígitos" para quem digitou um nome).
      Depois: `npm run generate:api`.
- [x] **Ciclo 4 — `normalizeSteamId()`** (front, função pura, zero rede): as 6
      linhas da gramática do REQ-060. `isSteamId64` **fica** — é a guarda do
      `enabled:` dos hooks, e `/u/:steamid` é editável à mão.
- [x] **Ciclo 5 — submit do `Home`**: URL `/profiles/…` navega sem tocar no
      `/resolve`; vanity resolve e navega; 16 dígitos dá erro local sem rede.
- [x] **Ciclo 6 — `<details>` de fallback** no Home: como achar o **link** do
      perfil (não o ID), sem screenshot (print da UI da Valve envelhece), + a
      linha do perfil privado — a única falha que o app não conserta sozinho.

**Decidido não fazer** (registrado para poder ser cobrado): rate limit por IP no
`/resolve`, partição do cache por prefixo, `@radix-ui/react-dialog` para exibir
três frases, screenshots, steamid dentro do `PlayerSummary`, apertar a regex do
steamid para `^7656…`. Motivo do primeiro par: `GET /api/users/<17 dígitos
aleatórios>/profile` **já** custa o mesmo que um vanity (1 req ⇒ 1 chamada Steam
⇒ 1 entrada de cache negativo). O vanity não cria classe nova de risco — abre
outra porta do mesmo tamanho. Blindar uma e deixar a irmã aberta é teatro.

**Custo de quota:** zero para 17 dígitos ou URL `/profiles/…`; +1 chamada só no
primeiro vanity de cada nome, depois é cache (positivo ou negativo).

## Conversão da Home (REQ-080/081)

Spec própria: `spec/spec-home-conversao.md`. Público decidido na entrevista de
16/07/2026: **tráfego morno, product-aware** — quem chega já quer as próprias
conquistas. Logo a mudança **subtrai** página, ao contrário do reflexo de
acrescentar: o input é o herói e a prova é o produto.

- [x] **"Como funciona" (`PASSOS`) removido** (REQ-080): explicava um problema que
      quem chega já tem. O que ali fazia trabalho real era **uma linha** — "nada de
      senha nem login" —, sepultada no passo 1: respondia à objeção de confiança
      **depois** do pedido que ela deveria destravar. Subiu para junto do campo,
      visível sem interação, onde a dúvida de fato acontece.
- [x] **Título passou de agregação para o loop de completude** (REQ-080): "cada
      troféu em um lugar" é o que todo tracker promete — arquivo morto. O que puxa
      é o loop aberto (Zeigarnik), o mesmo mecanismo do "Quase lá". ⚠️ **CON-080**:
      a promessa só é honesta porque o perfil de exemplo a prova; se o link de demo
      cair, o título **volta** para agregação.
- [x] **Perfil de exemplo** (REQ-081): prova antes do pedido, com nome e avatar
      reais. Só para **visitante novo** (sem `lastSteamId`) — para quem já
      converteu, o "Continuar como" é a conversão, e a demo seria o único outro
      link da página, apontando para longe. Não resolve ⇒ **some em silêncio**,
      como o `ContinuarComo` e a raridade.
- [x] **Reversão consciente (CON-083)**: a Home passa a fazer **1 chamada** de
      perfil para o visitante anônimo — o comportamento "zero chamadas sem id
      salvo" foi **revogado**. Sem buscar o perfil não há como saber que a demo
      quebrou, e 404 na cara de quem chega agora é pior. Custo: 1 requisição à
      própria API; `player_summary:{demo}` é chave fixa e compartilhada ⇒ quota
      Steam no regime ≈ 0. **Três** testes reescritos (não deletados), não um.
- [x] **`/verify` no app real (16/07/2026)**: a biblioteca do perfil de demo lê
      `155 jogos · 3.732,0 h · 3 jogos quase 100% · 9 jogos 100%` — a promessa do
      título provada a um clique, com dado vivo. Visitante recorrente renderiza
      **só** o "Continuar como". Achado que só o app pegou: sem o `PASSOS`, o herói
      encostava no topo e sobrava meia tela morta — centrado na vertical.

**Decidido não fazer** (registrado para poder ser cobrado): **prova social** de
qualquer forma — sem banco, sem analytics e sem usuários a citar, todo número
seria fabricado, e ser pego inventando "3.000 jogadores" custa exatamente a
confiança que a página existe para construir; **estrelas do GitHub** (provam que o
código existe, não que a ferramenta é boa, e miram dev, não o público escolhido);
**`VITE_DEMO_STEAMID`** (não varia entre deploys nem é segredo — ver CON-081);
**screenshot no herói** (já rejeitado no projeto; a demo viva substitui);
**auto-redirect** do recorrente para `/u/{lastSteamId}` (sequestraria quem quer
consultar outro perfil).

⚠️ **Perfil do Gabe (`76561197960287930`) não serve de demo**: verificado contra a
API real em 16/07/2026 — `GetPlayerSummaries` devolve o perfil
(`personaname='Rabscuttle'`), mas `GetOwnedGames` levanta `SteamDataUnavailable`:
a **biblioteca é privada**. Segue válido como *fixture* de teste, onde o id só
precisa ser parseado. Registrado para poupar a próxima pessoa da chamada.

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
