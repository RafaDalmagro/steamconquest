---
title: Guia de Conquista Pendente — Especificação de Comportamento
version: 1.0
date_created: 2026-07-17
last_updated: 2026-07-17
owner: rafa.limadalmagro
tags: [frontend, backend, steam, achievements, guides, detalhe]
---

# Introduction

Especificação do caminho **da conquista pendente até a orientação de como
obtê-la**. O detalhe do jogo hoje diz *que* falta uma conquista e não diz *como*
consegui-la; o usuário sai do app e procura à mão. Esta iteração fecha essa
lacuna com dois links determinísticos — um por conquista (vídeo) e um por jogo
(guias da comunidade) — e com o insumo de backend que ambos exigem: o **nome
canônico em inglês** da conquista.

A decisão de partida (entrevista de arquitetura de 2026-07-17) é que **não há IA
nesta iteração**. O pedido original descrevia um agente de IA que busca na web;
a entrevista o reclassificou como implementação, não como problema. O problema é
"não sei como pegar esta conquista", e ele tem uma resposta de dez linhas, sem
dependência nova, sem chave nova e sem custo por clique. O agente (doravante
**Fase B**) permanece na mira e herda o `name_en` desta spec como insumo.

Estende os REQ-030..033 (detalhe do jogo) da spec de arquitetura; ocupa a
numeração REQ-090+ no mesmo espaço.

## 1. Purpose & Scope

**Propósito:** definir o comportamento observável do acesso à orientação de
conquista, de forma não ambígua, suficiente para implementação via TDD sem novas
perguntas.

**No escopo:**
- Campo `name_en` no modelo `Achievement` (contrato da API).
- Segunda chamada `GetSchemaForGame` com `l=english`, cacheada em
  `schema_en:{appid}`.
- Link "Como conseguir" por conquista **pendente** no `AchievementItem`.
- Link para os guias da comunidade Steam por **jogo** no cabeçalho do
  `GameDetail`.

**Fora do escopo (não implementar nesta iteração):**
- **Qualquer IA**: SDK de LLM, chave de provedor, busca web sintetizada, painel
  in-app, streaming de resposta, prompt. Ver §7 e a Fase B.
- Mudança na biblioteca (`list_library`), no fan-out ou no `player_ach`.
- Link em conquista **obtida** — não há problema a resolver ali.
- Busca por `searchText` nos guias do Steam — comprovadamente quebrada, ver §7.
- Tradução, i18n ou troca do idioma de exibição (o app é pt-BR e continua).
- Persistência de qualquer natureza (proibido pela arquitetura: não há banco).

**Audiência:** o desenvolvedor/agente que implementará a mudança.

**Premissas:**
- `game_detail` já busca `schema:{appid}` e `global_pct:{appid}` em paralelo via
  `asyncio.gather` (`app/services/achievements.py:174`). A chamada em inglês
  entra **nesse mesmo gather**.
- `GameDetail.name` vem do `GetOwnedGames`, que devolve o **nome de loja** —
  já em inglês (ex.: "Nioh: Complete Edition"). Nenhum trabalho novo é
  necessário para o nome do jogo.
- `SteamClient` já recebe `language` no construtor (`app/steam/client.py:62`,
  default `"brazilian"`) e o repassa como `l=` ao schema.

## 2. Definitions

- **Conquista pendente**: `Achievement.achieved == false`. Não é estado novo — é
  o que o selo "Pendente" já exibe.
- **`display_name`**: nome da conquista **em pt-BR**, vindo de
  `schema:{appid}` (`l=brazilian`). É o que o card mostra. Continua sendo.
- **`name_en`**: nome **canônico em inglês** da conquista, vindo de
  `schema_en:{appid}` (`l=english`). Nunca é exibido; existe para ser
  pesquisável. Ver §7 para o porquê de não ser derivável do `display_name`.
- **Guia da comunidade**: item de `steamcommunity.com/sharedfiles/` publicado por
  jogadores. Não há API pública da Steam para guias — o acesso é por URL de
  navegação, não por endpoint.
- **Fase B**: iteração futura, não especificada aqui, em que um agente de IA faz
  busca web e sintetiza o passo-a-passo. Fora de escopo.
- **Decoração**: dado cuja ausência não pode derrubar a tela. `global_percent` já
  é decoração no projeto; `name_en` passa a ser a segunda.

## 3. Requirements, Constraints & Guidelines

### Backend

- **REQ-090**: `Achievement` expõe `name_en: str | None`, o nome canônico em
  inglês da conquista.
- **REQ-091**: `game_detail` obtém o schema em inglês via `GetSchemaForGame` com
  `l=english`, cacheado sob a chave `schema_en:{appid}`.
- **REQ-092**: A chamada do schema inglês executa **dentro do `asyncio.gather`
  existente**, em paralelo com `schema:{appid}` e `global_pct:{appid}`. O
  cold-start do detalhe permanece uma ida à Steam em tempo de parede, não duas.
- **REQ-093**: `name_en` é `None` quando o schema inglês não contém a conquista
  (`apiname` ausente em `availableGameStats.achievements`).
- **REQ-094**: Falha ao obter o schema inglês **não derruba o detalhe**: o erro é
  engolido pelo service, `name_en` vem `None` em todas as conquistas, e o resto
  do payload é servido normalmente.
- **REQ-095**: Jogo sem conquistas (`supports_achievements == false`, branch
  `if not player`) **não** paga a chamada do schema inglês.

### Frontend

- **REQ-096**: Conquista **pendente** com `name_en` não nulo exibe um link
  "Como conseguir" apontando para a busca do YouTube (formato em §4).
- **REQ-097**: O link **não é renderizado** quando a conquista é obtida
  (`achieved == true`) **ou** quando `name_en` é `null`.
- **REQ-098**: O cabeçalho do `GameDetail` exibe, uma única vez por jogo, um link
  para os guias da comunidade Steam filtrados pela tag `Achievements` (formato em
  §4).
- **REQ-099**: O link de guias **não é renderizado** quando
  `supports_achievements == false`.

### Segurança

- **SEC-004**: Todo link externo usa `target="_blank"` **e**
  `rel="noopener noreferrer"`. Sem `noopener`, a página aberta recebe
  `window.opener` e pode redirecionar a aba de origem. É boundary de segurança,
  não preferência de estilo.
- **SEC-005**: `display_name` e `name_en` entram na URL **codificados**
  (`encodeURIComponent`). Nomes de conquista contêm apóstrofo, `&`, `#` e acento.

### Constraints

- **CON-090**: Nenhuma dependência nova, em nenhum dos dois `package`/`project`.
  Nem `anthropic`, nem SDK de LLM, nem cliente de busca.
- **CON-091**: A URL externa é montada **no frontend**. `web/` devolve modelo de
  domínio, nunca apresentação — invariante do projeto (`CLAUDE.md`).
- **CON-092**: `schema_en:{appid}` é chaveada por **jogo**, não por jogador —
  o nome em inglês é o mesmo para todo mundo, e a entrada é compartilhada entre
  visitantes. Usa o helper `_cached()`, não `_cached_ou_ausente()`: a sentinela de
  ausência não se aplica, porque quem absorve a falha é o próprio `buscar()`
  (§9) e o que chega ao cache já é um `{}` legítimo com TTL curto.
- **CON-093**: `_MAXSIZE` conta **entradas**, e esta mudança dobra as de schema.
  Aceito conscientemente e reversível. Não aumentar `_MAXSIZE` nesta iteração
  sem medir.
- **CON-094**: `CLAUDE.md` documenta a lista de chaves de cache. `schema_en:{appid}`
  entra lá **no mesmo diff** — a doc não é opcional.
- **CON-095**: `npm run generate:api` roda após a mudança do modelo. Sem isso o
  SPA não enxerga `name_en`.

### Padrões

- **PAT-007**: `name_en` segue o padrão de **decoração** já estabelecido por
  `global_percent`: o service engole o erro e o campo vem vazio. Não inventar
  política de erro nova.
- **PAT-008**: O fallback de `name_en` **diverge** do de `display_name`
  (`achievements.py:189`, que cai para `apiname`) **de propósito**: ali o
  fallback existe para *mostrar alguma coisa*; aqui existe para *buscar*, e
  buscar `ACH_SPA_HEALER` no YouTube não acha nada. Link ausente é honesto; link
  que não acha nada é ruído.

### Guidelines

- **GUD-003**: O link por conquista é **texto** ("Como conseguir"), não ícone
  solto. Ícone-só exigiria `aria-label` inventado num card que já carrega dois
  selos.
- **GUD-004**: O card **não** vira clicável por inteiro. Envolver `<img>`/`<time>`
  num anchor de card quebra a navegação por leitor de tela.

## 4. Interfaces & Data Contracts

### Modelo — `Achievement` (delta)

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `name_en` | `str \| None` | Não (default `None`) | Nome canônico em inglês. `None` = schema inglês não trouxe a conquista, ou a chamada falhou. Nunca exibido. |

Nenhum outro campo muda. `display_name` continua pt-BR.

### Chave de cache (delta)

| Chave | Escopo | TTL | Helper |
|---|---|---|---|
| `schema_en:{appid}` | Jogo (compartilhada entre jogadores) | `SCHEMA_TTL` (24h) em sucesso; `SCHEMA_EN_MISS_TTL` (1h) quando `{}` | `_cached()` com TTL por callable |

O TTL de miss curto segue `global_pct:{appid}`/`genres:{appid}`: `{}` aqui é
sempre falha transitória (jogo sem schema já cai no branch sem conquistas), e
cachear o vazio por 24h sumiria com o link "Como conseguir" por um dia inteiro
por causa de um 429 de dez segundos.

### Steam — `GetSchemaForGame` (segunda chamada)

```
GET /ISteamUserStats/GetSchemaForGame/v2/?appid={appid}&l=english&key={KEY}
→ game.availableGameStats.achievements[] com name / displayName / description / icon
```

Só `name` (= `apiname`) e `displayName` são consumidos. O resto é descartado.

### URL externa — busca de vídeo (por conquista)

```
https://www.youtube.com/results?search_query={game}+{name_en}+achievement
```

`{game}` = `GameDetail.name`; `{name_en}` = `Achievement.name_en`. Ambos passam
por `encodeURIComponent` (SEC-005).

Exemplo (Nioh, conquista "Descanso no Spa"):

```
https://www.youtube.com/results?search_query=Nioh%3A%20Complete%20Edition%20Spa%20Healer%20achievement
```

### URL externa — guias da comunidade (por jogo)

```
https://steamcommunity.com/app/{appid}/guides/?requiredtags%5B%5D=Achievements
```

Exemplo (Nioh): `https://steamcommunity.com/app/485510/guides/?requiredtags%5B%5D=Achievements`

## 5. Acceptance Criteria

### Backend

- **AC-090**: Dado um schema inglês contendo `ACH_SPA` → `"Spa Healer"` e um
  schema pt-BR contendo `ACH_SPA` → `"Descanso no Spa"`, Quando `game_detail` é
  chamado, Então a conquista `ACH_SPA` vem com `display_name == "Descanso no Spa"`
  **e** `name_en == "Spa Healer"`.
- **AC-091**: Dado um schema inglês que **não** contém o `apiname` presente no
  `player_ach`, Quando `game_detail` é chamado, Então a conquista vem com
  `name_en == None` e o restante do payload íntegro.
- **AC-092**: Dado um client falso cuja chamada de schema inglês levanta exceção,
  Quando `game_detail` é chamado, Então a resposta é servida com sucesso, todas
  as conquistas têm `name_en == None`, e `display_name`/`global_percent`
  permanecem preenchidos.
- **AC-093**: Dado um jogo sem conquistas (`player_ach` vazio), Quando
  `game_detail` é chamado, Então o client **não** registra nenhuma chamada de
  schema com `l=english`.
- **AC-094**: Dado dois `game_detail` consecutivos para o mesmo `appid`, Quando o
  segundo executa, Então o client registra **uma** única chamada de schema inglês
  (a segunda leu `schema_en:{appid}` do cache).

### Frontend

- **AC-095**: Dada uma conquista com `achieved: false` e `name_en: "Spa Healer"`,
  Quando o `AchievementItem` renderiza, Então existe um link acessível por nome
  "Como conseguir" cujo `href` contém `youtube.com/results` e `Spa+Healer` ou
  `Spa%20Healer`.
- **AC-096**: Dada uma conquista com `achieved: true` e `name_en` preenchido,
  Quando o `AchievementItem` renderiza, Então **não** existe link "Como conseguir".
- **AC-097**: Dada uma conquista com `achieved: false` e `name_en: null`, Quando
  o `AchievementItem` renderiza, Então **não** existe link "Como conseguir".
- **AC-098**: Dado qualquer link externo desta feature, Quando renderizado, Então
  possui `target="_blank"` e `rel` contendo `noopener` e `noreferrer`.
- **AC-099**: Dado um `GameDetail` com `supports_achievements: true` e
  `appid: 485510`, Quando a página renderiza, Então existe **exatamente um** link
  para `steamcommunity.com/app/485510/guides/` com a tag `Achievements`.
- **AC-100**: Dado um `GameDetail` com `supports_achievements: false`, Quando a
  página renderiza, Então não existe link de guias.

## 6. Test Automation Strategy

- **Test Levels**: Unit (service + componentes). Sem E2E — a feature não tem
  fluxo multi-tela.
- **Frameworks**: `pytest` + `pytest-asyncio` (backend); `vitest` +
  Testing Library (frontend). Nada novo.
- **Test Data Management**: client falso escrito à mão, no padrão de
  `tests/test_service.py`. **Proibido** `mock.patch` em dependência interna —
  boundary externo real apenas. O falso registra as chamadas recebidas, o que é o
  que torna AC-093 e AC-094 verificáveis sem rede.
- **Ordem TDD** (um comportamento por ciclo, RED antes de qualquer implementação):
  1. AC-090 — `name_en` preenchido a partir do schema inglês.
  2. AC-091 — conquista ausente do schema inglês → `None`.
  3. AC-092 — falha do schema inglês não derruba o detalhe.
  4. AC-093 — jogo sem conquistas não paga a chamada.
  5. AC-094 — segunda visita lê do cache.
  6. AC-095 — link renderiza na pendente.
  7. AC-096/097 — link some na obtida e sem `name_en`.
  8. AC-099/100 — link de guias no cabeçalho.
- **Coverage Requirements**: sem limiar numérico. Todo AC desta spec tem teste.
- **Performance Testing**: nenhum. A asserção de custo (AC-093/094) é contagem de
  chamadas no client falso, não benchmark.

## 7. Rationale & Context

### Por que não há IA nesta iteração

O pedido original — "um agente de IA que faz buscas na web" — descreve a
implementação, não o problema. O problema é "não sei como pegar esta conquista".
A entrevista comparou os dois caminhos:

| | Links determinísticos | Agente de IA |
|---|---|---|
| Dependência nova | nenhuma | SDK de LLM |
| Segredo novo | nenhum | chave de provedor |
| Custo por clique | zero | por token |
| Latência | zero | segundos |
| Alucinação | impossível | possível (link de vídeo inexistente) |
| Eixo de abuso | nenhum | `steamid`/`appid` são input público → qualquer um queima a conta de API |

O ganho real do agente sobre os links é **sintetizar** — ler o guia 100% de 40
páginas e extrair a seção daquela conquista. Esse ganho é real, mas só se paga se
o clique atual de fato custar tempo. Essa é uma medição que ninguém tem hoje. O
critério de disparo da Fase B está em §9.

O `name_en` desta spec **não é trabalho descartável**: é exatamente o insumo que
o agente da Fase B precisará mandar para a busca web. Ele é construído agora
porque o link determinístico já o exige.

### Por que `name_en` não é derivável do `display_name`

O `GetSchemaForGame` do projeto envia `l=brazilian`
(`app/steam/client.py:134`). Os nomes pt-BR **não são traduções reconhecíveis**;
são outros textos. Verificado contra a Steam em 2026-07-17 (Nioh, appid 485510):

| `display_name` (pt-BR) | `name_en` (inglês) |
|---|---|
| Descanso no Spa | Spa Healer |
| Obra-prima | Latest Masterpiece |
| Andarilho do Crepúsculo | Twilight Walker |
| O Início de uma Jornada | A Long Journey Begins |

Guia e vídeo de conquista são escritos em inglês. Buscar
`Nioh Descanso no Spa achievement` no YouTube não retorna resultado útil. Sem o
`name_en`, o link principal da feature não funciona — daí a segunda chamada valer
a chamada extra.

### Por que a tag `Achievements` e não `searchText`

Verificado contra a Steam em 2026-07-17 (Nioh, appid 485510):

- `?searchText=Ocean's Deep` (nome de conquista) → **zero resultados**, e a
  Steam **não exibe "nenhum resultado"**: ela cai silenciosamente nos guias
  populares do jogo. O usuário clicaria e veria "Recommended Keyboard & Mouse
  Settings" acreditando ser sobre a conquista. **Um link que mente é pior que
  link nenhum** — é o mesmo princípio que rege PAT-008.
- `?requiredtags[]=Achievements` → 19 guias, entre eles o
  "Nioh 100% conquistas (com DLC)". Funciona, e funciona em qualquer idioma: os
  19 incluem guias em PT, RU, ZH e EN.

A consequência aceita é que **o corpus de guias do Steam é por jogo, não por
conquista** — não existe guia da "Ocean's Deep", existe o guia 100% do Nioh. Por
isso o link de guias é do **jogo** e vive no cabeçalho (REQ-098), enquanto o link
por conquista aponta para o YouTube (REQ-096), onde a granularidade por conquista
de fato existe.

### Custos assumidos conscientemente

1. **+1 chamada Steam por jogo**, só na primeira visita ao detalhe, cacheada e
   compartilhada. Cai no caminho barato: o detalhe é **uma tela**, não o fan-out
   da biblioteca (que não toca o schema — a contagem vem do `player_ach`).
2. **Dobro de entradas de schema** sob o `_MAXSIZE` (CON-093). Em biblioteca
   grande com muita navegação, o schema pt-BR pode ser despejado mais cedo.
3. **~90 tab stops novos** na aba "Pendentes" de um jogo grande. A alternativa
   "aparece só no hover" resolveria o tab stop e **quebraria no touch** — logo
   não é alternativa.
4. **`GetOwnedGames` no cold-start do detalhe** (`_ensure_library`), descoberto
   no `/verify`: `GameDetail.name` alimenta a busca de vídeo, e com o cache da
   biblioteca frio ele caía em `App {appid}` — um token que **envenena a query**,
   não só um título feio. `OWNED_TTL=300` torna isso comum (qualquer reload após
   5 min), não um caso de deep-link. A chamada entra no `gather` (sem latência de
   parede), é best-effort (falha → fallback antigo, detalhe não cai) e semeia
   `owned_games:` para as próximas. Reverte a decisão original de "não pagar
   chamada só pelo título" — que valia quando o título só aparecia no `<h1>`.

## 8. Dependencies & External Integrations

### External Systems
- **EXT-001**: Steam Web API — `ISteamUserStats/GetSchemaForGame/v2` com
  `l=english`. Já integrada; esta spec só adiciona um segundo idioma.
- **EXT-002**: Steam Community (`steamcommunity.com`) — destino de link de
  navegação. **Não é integração de API**: o app não faz requisição, apenas emite
  um `href`. Não há API pública de guias.
- **EXT-003**: YouTube — destino de link de navegação. Mesma natureza: `href`,
  sem requisição, sem chave, sem SDK.

### Third-Party Services
Nenhum novo. Explicitamente **não** há provedor de LLM nesta iteração (CON-090).

### Infrastructure Dependencies
- **INF-001**: `TTLCache` em memória existente. Sem componente novo.

### Data Dependencies
- **DAT-001**: `availableGameStats.achievements[]` do schema inglês. Campos
  consumidos: `name`, `displayName`. Frequência: uma vez por jogo por TTL.

### Technology Platform Dependencies
- **PLT-001**: Nenhuma mudança. Python 3.12/FastAPI e React 19/Vite já em uso.

### Compliance Dependencies
- **COM-001**: `STEAM_API_KEY` permanece server-side (SEC-001 da spec de
  arquitetura). A segunda chamada de schema é backend→Steam como todas as outras;
  nada novo chega ao browser além de `name_en`, que é texto público.

## 9. Examples & Edge Cases

```python
# AC-092 — falha do schema inglês é decoração: engolida, nunca propagada.
# O try/except vai *dentro* do buscar(), como em _global_percentages: assim o {}
# é cacheado com TTL curto. Engolir *fora* do _cached() devolveria {} sem cachear
# e faria cada request re-tentar uma Steam que está em 429 — retry storm contra a
# própria quota que o token bucket existe para proteger.
async def _schema_en(self, appid: int) -> dict:
    async def buscar() -> dict:
        try:
            return await self._client.get_schema(appid, "english")
        except SteamError:
            return {}  # name_en vira None em todas; o detalhe continua de pé.

    return await self._cached(
        f"schema_en:{appid}",
        lambda s: SCHEMA_TTL if s else SCHEMA_EN_MISS_TTL,
        buscar,
    )
```

```tsx
// AC-095/097 — o link existe só quando há o que buscar.
// name_en nulo => sem link (PAT-008): buscar apiname não acha nada.
{!ach.achieved && ach.name_en && (
  <a
    href={`https://www.youtube.com/results?search_query=${encodeURIComponent(
      `${gameName} ${ach.name_en} achievement`,
    )}`}
    target="_blank"
    rel="noopener noreferrer"
  >
    Como conseguir
  </a>
)}
```

### Edge cases

| Caso | Comportamento esperado |
|---|---|
| Jogo sem conquistas | Sem link de guias (REQ-099), sem chamada inglesa (REQ-095) |
| Schema inglês indisponível (429/502) | Detalhe servido, todos `name_en == None`, nenhum link "Como conseguir" (REQ-094) |
| `apiname` no `player_ach` mas ausente do schema inglês | `name_en == None` naquela conquista; as demais intactas (REQ-093) |
| Nome com apóstrofo ("Ocean's Deep") | `encodeURIComponent` (SEC-005) |
| Jogo cujo schema não tem localização pt-BR | A Steam já faz fallback para inglês no `l=brazilian`; `display_name == name_en`. Link funciona. Sem tratamento especial. |
| Deep-link ao detalhe / cache da biblioteca expirado (`OWNED_TTL`) | `game_detail` semeia `owned_games:` antes de montar o nome (`_ensure_library`, best-effort no `gather`), então `GameDetail.name` traz o nome de loja mesmo aqui. Só cai em `App {appid}` se o jogo não estiver na biblioteca (delistado) **ou** se a busca da biblioteca falhar — nunca por cache frio. |
| Conquista oculta sem `displayName` no schema | `display_name` cai para `apiname` (comportamento atual, inalterado); `name_en` → `None` se ausente no schema inglês |

## 10. Validation Criteria

- Todos os AC-090..AC-100 têm teste automatizado e passam.
- `uv run pytest` e `npm run test` verdes.
- `rg -i "anthropic|openai|llm" app/ frontend/src/` não retorna nada — CON-090.
- `rg "requiredtags" frontend/src/` mostra a tag `Achievements`, e
  `rg "searchText" frontend/src/` não retorna nada — §7.
- Todo link externo da feature casa `rel=.*noopener` — SEC-004.
- `CLAUDE.md` lista `schema_en:{appid}` entre as chaves de cache — CON-094.
- `frontend/src/api/types.gen.ts` contém `name_en` — CON-095.
- `/verify`: o detalhe de um jogo real exibe o link na pendente, o link abre a
  busca certa, e o link **não** aparece nas obtidas.

## 10.1. Nota para a Fase B (agente de IA) — NÃO é escopo desta spec

Registrada em 2026-07-17, quando a Fase B ganhou modelo de negócio: **serviço
pago, disponível só para assinantes, cobrança via Stripe.** Isto é uma nota de
intenção, não uma especificação — a Fase B **não pode** começar por código.

**A Fase B é um novo ciclo SDD, e ele reabre a arquitetura — não a estende.**
Monetizar por assinatura arrasta três decisões que este projeto fechou de
propósito (ver "Fora de escopo" na spec de arquitetura e a seção "Antes de propor
mudanças grandes" do `CLAUDE.md`):

1. **Identidade persistente / login / multiusuário.** "Quem é o assinante?" só
   tem resposta se houver conta. Hoje o `steamid` vem da **URL pública** e não
   autentica ninguém — qualquer visitante abre qualquer perfil. Uma assinatura
   exige saber *quem paga*, o que é login + multiusuário, ambos hoje fora de
   escopo. **Não** dá para amarrar assinatura ao `steamid` da URL: ele é forjável,
   e pagante nenhum aceita que outro use sua cota digitando o ID dele.
2. **Estado durável.** Assinatura ativa/cancelada/inadimplente **não** cabe no
   `TTLCache` (volátil, com teto que despeja entradas). É banco — reintrodução que
   o `CLAUDE.md` exige aprovar antes. Alternativa a avaliar no SDD: tratar o
   Stripe como fonte de verdade e consultar/cachear o status, evitando banco
   próprio de assinaturas.
3. **Webhook do Stripe.** Eventos de pagamento chegam **fora** de um request do
   usuário — superfície de entrada nova, com verificação de assinatura HMAC do
   Stripe obrigatória (senão qualquer um forja "pagamento aprovado"). O app hoje
   não tem essa superfície.

**Custo/segredo que se somam ao que a §7 já lista para a IA:**
- `STRIPE_SECRET_KEY` e o segredo de webhook entram no rol de segredos só-env,
  mesma disciplina da `STEAM_API_KEY` (SEC-001 da arquitetura): nunca no bundle,
  no log ou em resposta.
- O gate de autorização (assinante × não-assinante) vira **boundary de segurança**
  no endpoint da IA. Como `steamid`/`appid` são input público (o eixo de abuso já
  anotado na §7), sem o gate qualquer um queima a cota paga de LLM de qualquer um.

**Ordem obrigatória da Fase B:** `/create-specification` reabrindo os invariantes
acima **antes** de qualquer `/tdd`. O `name_en` desta spec continua sendo o insumo
de busca que o agente herda — essa parte não muda.

## 11. Related Specifications / Further Reading

- `spec/spec-architecture-steam-achievements.md` — REQ-030..033 (detalhe do
  jogo), SEC-001 (a chave nunca sai do backend), contrato de erro, e o "Fora de
  escopo" que a Fase B terá de reabrir (multiusuário, login).
- `Steam_Web_API_Documentation.md` — `GetSchemaForGame` e o parâmetro `l`.
- `CLAUDE.md` — invariante de camadas, disciplina de cache, `_MAXSIZE`, e
  "Antes de propor mudanças grandes" (banco/multiusuário → perguntar antes).
- Fase B (não especificada): agente de IA com busca web, **pago via assinatura
  Stripe** (§10.1). Disparo em §7 — implementar somente após evidência de uso de
  que o guia 100% custa tempo real. Começa por SDD, não por código.
