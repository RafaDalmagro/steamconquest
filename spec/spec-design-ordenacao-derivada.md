---
title: Ordenação Derivada — Raridade no Detalhe e "Quase lá" na Biblioteca
version: 1.0
date_created: 2026-07-19
last_updated: 2026-07-19
owner: rafa.limadalmagro
tags: [frontend, react, ordenacao, raridade, engagement, custo-zero]
---

# Introduction

Especificação de dois eixos de ordenação que o app pode oferecer **sem nenhuma
chamada nova** à Steam, porque o dado já está carregado e renderizado na tela:

1. **Raridade no detalhe** — ordenar as conquistas de um jogo por `global_percent`,
   nas duas direções. Responde a duas perguntas distintas com um controle só: *"qual
   pendente eu consigo hoje?"* (mais comuns primeiro) e *"quais das minhas são
   raras?"* (mais raras primeiro).
2. **"Quase lá" na biblioteca** — um eixo de ordenação que traz para o topo os jogos
   com progresso alto e ainda não concluído.

As duas são **frontend-only**: nenhuma rota nova, nenhum campo novo, nenhum arquivo
de `app/` alterado. O `global_percent` já vem no `GameDetail` e já é exibido em
`AchievementItem`; o `percent` já vem no `Game` e já alimenta o selo `isQuaseLa()`.
O que falta é **poder ordenar por eles**.

## 1. Purpose & Scope

**Propósito:** definir, sem ambiguidade, os dois eixos de ordenação novos — o
vocabulário, o comportamento com dados ausentes, o que vai para a URL e o efeito
sobre o `include` enviado à API.

**No escopo:**
- Um controle de ordenação de conquistas na página de detalhe, com três opções.
- Um valor novo (`quase_la`) no vocabulário de ordenação da biblioteca.
- A consequência do item anterior sobre `includesFor()`.
- Correção de duas afirmações **desatualizadas** na documentação (§7.4).

**Fora de escopo:**
- Qualquer alteração no backend (`app/`). Ordenar é trabalho do cliente — decisão
  já registrada no REQ-002/REQ-003 da spec de arquitetura e reafirmada aqui.
- Ordenação cruzada entre jogos por raridade ("minhas conquistas mais raras de toda
  a biblioteca"): exigiria uma chamada de detalhe por jogo. Ver §7.5.
- Um eixo "horas sem conquista" na biblioteca. Considerado e **recusado** — ver §7.5.
- Filtro por faixa de raridade ("só as abaixo de 5%"). O selo "Rara" e a ordenação
  já cobrem a intenção; um filtro a mais custaria um controle a mais.

**Audiência:** o agente ou pessoa que implementa o ciclo RED/GREEN/REFACTOR
seguinte. Assume familiaridade com `frontend/src/pages/Library.tsx`,
`frontend/src/pages/GameDetail.tsx`, `frontend/src/components/SortBar.tsx` e
`frontend/src/api/client.ts`.

## 2. Definitions

| Termo | Definição |
|---|---|
| **`global_percent`** | % de **todos** os jogadores da Steam que obteve a conquista. Campo de `Achievement`. `null` quando a Steam não devolveu raridade para o jogo (é decoração — CON-041 da spec de arquitetura). |
| **Mais fácil** | Conquista com `global_percent` **maior**: mais gente tem, logo presumivelmente menos difícil. É uma proxy, não uma medida de dificuldade — ver §7.2. |
| **Mais rara** | Conquista com `global_percent` **menor**. |
| **"Quase lá"** | Jogo cujo percentual **exibido** (arredondado) está em `[80, 100)`. Definição já existente em `frontend/src/lib/progress.ts` (`isQuaseLa`), fixada pela `spec-quase-la-completion-loop.md`. Esta spec **reusa** a função, não redefine o limiar. |
| **Eixo de ordenação** | Um valor do tipo `Sort` (biblioteca) ou `OrdemAch` (detalhe), com um comparador correspondente. |
| **Estado da URL** | Parâmetro de query do SPA que sobrevive ao refresh e ao compartilhamento do link. |

## 3. Requirements, Constraints & Guidelines

### Detalhe — ordenação por raridade

- **REQ-160**: A página de detalhe oferece um controle de **ordenação das
  conquistas** com exatamente três opções, nesta ordem:

  | Valor | Rótulo | Critério |
  |---|---|---|
  | `desbloqueio` (default) | "Desbloqueio" | comportamento atual (`porDesbloqueio`) |
  | `faceis` | "Mais fáceis" | `global_percent` decrescente |
  | `raras` | "Mais raras" | `global_percent` crescente |

- **REQ-161**: O controle é **independente** do filtro por status (abas
  obtidas/pendentes/todas), e os dois se combinam livremente. É essa
  independência que faz **um** controle servir aos dois casos de uso: `Pendentes` +
  `faceis` responde "qual eu consigo hoje?"; `Obtidas` + `raras` é a vitrine.

- **REQ-162**: A direção **não** é derivada da aba ativa. Ver §7.1 — é a decisão
  de desenho mais consequente desta spec.

- **REQ-163**: Conquista com `global_percent == null` vai para o **fim** da lista
  em `faceis` e em `raras`, nunca para o topo, e a ordem relativa entre elas é
  preservada (o `Array.prototype.sort` do JS é estável). Tratar `null` como `0`
  jogaria as sem-raridade para o topo de `raras` como se fossem as mais raras do
  jogo — uma afirmação falsa apresentada como resultado de ordenação.

- **REQ-164**: A ordenação escolhida vai para a **URL**, como parâmetro `ordem`,
  junto do `filter` que já está lá. O default (`desbloqueio`) é **omitido** da URL.
  Valor desconhecido em `?ordem=` degrada para o default, sem erro — mesma
  tolerância que `filter` e `sort` já praticam.

- **REQ-165**: Num jogo em que **nenhuma** conquista tem `global_percent` (a Steam
  devolveu 403 ou não tem stats globais), o controle de ordenação **não é
  renderizado**. Oferecer "Mais raras" onde ordenar não muda nada é um controle que
  mente. O mesmo princípio já governa o selo "Rara" e o `ContinuarComo` da Home:
  o que não tem o que dizer **some em silêncio**.

### Biblioteca — eixo "Quase lá"

- **REQ-166**: O vocabulário `Sort` de `frontend/src/components/SortBar.tsx` ganha
  o valor `quase_la`, com rótulo **"Quase lá"**, posicionado **imediatamente após
  `percent`** — é o vizinho semântico, e a ordem dos botões é a ordem de declaração
  das chaves do `Record` (comportamento já documentado no arquivo).

- **REQ-167**: O comparador de `quase_la` ordena em dois níveis:
  1. jogos "quase lá" (`isQuaseLa(percent)`) vêm **antes** de todos os outros;
  2. dentro do grupo "quase lá", o **maior** percentual primeiro (mais perto de
     fechar = mais no topo).

  Fora do grupo, a ordem relativa é preservada pela estabilidade do `sort`. Jogos
  com `percent == null` nunca são "quase lá" (garantido por `isQuaseLa`) e portanto
  caem no segundo grupo.

- **REQ-168**: `includesFor()` (`frontend/src/api/client.ts`) passa a pedir
  `include=achievements` **também** para `sort === "quase_la"`. Sem isto o
  `percent` vem `null` para todos os jogos, `isQuaseLa` devolve `false` para todos,
  e o eixo novo não reordena nada — um botão que não faz nada. Esta é a única
  consequência da feature sobre o tráfego com a API.

- **REQ-169**: O eixo `quase_la` é do **SPA**, não da API. A rota
  `GET /api/users/{steamid}/games` **não** ganha `quase_la` no seu `Literal` de
  `sort`. Ver §7.3.

### Restrições

- **CON-160**: Nenhum arquivo sob `app/` é modificado. Se a implementação parecer
  exigir isso, a implementação está errada — reler o §7.3.

- **CON-161**: `frontend/src/lib/progress.ts` é **reusado**, não reescrito. O
  limiar de 80% pertence à `spec-quase-la-completion-loop.md`; alterá-lo aqui
  mudaria calada uma decisão de produto de outra spec, e afetaria também o selo do
  card e a contagem do resumo, que leem a mesma função.

- **CON-162**: `npm run generate:api` **não** precisa ser rodado: nenhum modelo do
  backend muda, e tanto `Sort` quanto `OrdemAch` são vocabulário do SPA declarado à
  mão (como o `Group` já é).

- **CON-163**: Ordenação continua **client-side**, sobre a lista inteira já
  carregada. Isto só é correto porque a biblioteca vem de uma vez; se um dia ela
  for paginada, os dois eixos precisam ser reavaliados — o aviso já está no
  comentário de `Library.tsx` e vale igual aqui.

- **CON-164**: `Sort` e `OrdemAch` são declarados como `Record<T, string>`, não
  como array, para que o TypeScript **exija** uma entrada por valor. Um eixo novo
  sem comparador vira erro de compilação, não um botão morto. O padrão já existe em
  `SortBar.tsx` — segui-lo, não inventar outro.

### Diretrizes

- **GUD-160**: Ao acrescentar um eixo de ordenação, a pergunta é "que pergunta do
  usuário esta ordem responde?". Se a resposta for "ele consegue ver isso
  olhando a lista ordenada por outra coisa", o eixo não se paga — foi o que
  eliminou "horas sem conquista" (§7.5).

## 4. Interfaces & Data Contracts

### Novo vocabulário do detalhe

```ts
// frontend/src/pages/GameDetail.tsx (ou um componente irmão do SortBar)
export type OrdemAch = "desbloqueio" | "faceis" | "raras";
```

### Vocabulário da biblioteca — alterado

```ts
// frontend/src/components/SortBar.tsx
export type Sort =
  | "playtime"
  | "name"
  | "percent"
  | "quase_la"   // novo (REQ-166)
  | "ach_count"
  | "last_played";
```

### Contrato da URL

| Página | Parâmetro | Valores | Default (omitido da URL) |
|---|---|---|---|
| `/u/{steamid}` | `sort` | `playtime`, `name`, `percent`, `quase_la`, `ach_count`, `last_played` | `playtime` |
| `/u/{steamid}` | `group` | `none`, `genre` | `none` |
| `/u/{steamid}` | `q` | texto livre | vazio |
| `/u/{steamid}/{appid}` | `filter` | `all`, `achieved`, `pending` | `all` |
| `/u/{steamid}/{appid}` | `ordem` | `desbloqueio`, `faceis`, `raras` | `desbloqueio` |

Só a linha `ordem` é nova. As outras quatro **já existem em produção** e estão aqui
porque a documentação atual as descreve errado (§7.4).

### Efeito sobre a chamada à API

| `sort` | `include` enviado |
|---|---|
| `playtime`, `name`, `last_played` | — |
| `percent`, `ach_count`, **`quase_la`** | `achievements` |
| (qualquer) + `group=genre` | adiciona `genres` |

## 5. Acceptance Criteria

- **AC-160**: Given um jogo com conquistas de raridade 2%, 50% e 90%, When a ordem
  é `faceis`, Then a lista sai 90%, 50%, 2%.
- **AC-161**: Given o mesmo jogo, When a ordem é `raras`, Then a lista sai 2%, 50%,
  90%.
- **AC-162**: Given um jogo em que parte das conquistas tem `global_percent: null`,
  When a ordem é `raras`, Then **todas** as com raridade vêm antes de **todas** as
  sem, e as sem mantêm entre si a ordem em que chegaram.
- **AC-163**: Given a aba `Pendentes` ativa e a ordem `faceis`, When a página
  renderiza, Then só pendentes são exibidas, ordenadas da mais comum para a mais
  rara — filtro e ordem se combinam sem um sobrescrever o outro.
- **AC-164**: Given a ordem `raras` selecionada, When a URL é lida, Then ela contém
  `ordem=raras`; e When a ordem volta para `desbloqueio`, Then o parâmetro
  **desaparece** da URL.
- **AC-165**: Given uma URL com `?ordem=xpto`, When a página carrega, Then a lista
  usa `desbloqueio` e nada quebra.
- **AC-166**: Given um jogo em que **nenhuma** conquista tem `global_percent`, When
  a página renderiza, Then o controle de ordenação **não** aparece.
- **AC-167**: Given uma biblioteca com jogos em 100%, 95%, 85% e 30%, When o sort é
  `quase_la`, Then a ordem é 95%, 85%, e depois os demais (100% e 30%) na ordem em
  que chegaram — o 100% **não** é "quase lá".
- **AC-168**: Given jogos sem dados de conquista (`percent: null`), When o sort é
  `quase_la`, Then eles ficam depois dos "quase lá" e nada quebra.
- **AC-169**: Given o sort `quase_la` selecionado, When o SPA chama a API, Then a
  query inclui `include=achievements`.
- **AC-170**: Given o sort `quase_la` na URL, When a página é recarregada, Then a
  ordenação é preservada (o eixo é estado de URL como os demais).

## 6. Test Automation Strategy

- **Níveis:** unitário nos comparadores (funções puras) e de componente nas duas
  páginas.
- **Framework:** Vitest + Testing Library, como o restante de `frontend/src`.
- **Fixtures:** os *builders* já usados em `Library.test.tsx` e `GameDetail.test.tsx`.
  Não criar fábrica nova.
- **Sem rede:** os hooks do React Query são alimentados por dados de teste, como já
  se faz hoje. Nenhum teste desta spec toca `fetch`.
- **Interface pública:** os ACs são verificados pelo que o usuário vê — a ordem dos
  itens renderizados —, não chamando o comparador direto quando ele é detalhe
  interno da página. O comparador de `quase_la` é exceção legítima: ele vive num
  `Record` exportado e ordenar é a sua interface.
- **AC-169** é verificado pelo argumento passado ao hook/`fetchGames` (é um
  contrato com a API, não um pixel).
- **Ordem RED/GREEN:** um AC por ciclo, na ordem AC-160 → AC-170.
- **Regressão obrigatória:** a suíte existente de `GameDetail.test.tsx` cobre a
  ordenação por desbloqueio. Ela **não pode ser alterada** — o default não muda.

## 7. Rationale & Context

### 7.1 Por que a direção é explícita, e não derivada da aba

A tentação é derivar: na aba `Pendentes`, ordenar por raridade só pode significar
"mais fáceis primeiro"; na aba `Obtidas`, "mais raras primeiro". Um controle a
menos, e o certo por default.

Foi recusado por três motivos:

1. **A aba `Todas` não tem resposta.** Ela mistura obtidas e pendentes, e nenhuma
   das duas direções é obviamente a certa. Uma regra que precisa de exceção no
   terceiro caso de três não é uma regra.
2. **O mesmo controle passaria a significar coisas diferentes** conforme uma aba
   distante dele. O usuário que ordena, troca de aba e vê a ordem **inverter** sem
   ter tocado no controle não descobriu um atalho — encontrou um bug.
3. **A intenção cruzada é legítima.** "Quais pendentes são as mais raras?" é uma
   pergunta boa (o troféu difícil que vale a pena caçar), e a derivação a tornaria
   inexprimível.

Três opções explícitas custam um controle e não escondem nada.

### 7.2 "Mais fácil" é uma proxy, e a spec assume isso

`global_percent` alto significa "muita gente tem", não "é fácil". Uma conquista de
tutorial e uma conquista que se obtém só jogando 40 h têm percentuais altos por
razões diferentes. A ordenação continua útil — a correlação é forte o bastante para
guiar a escolha do próximo alvo —, mas o rótulo é **"Mais fáceis"** e não "Dificuldade",
porque prometer uma medida de dificuldade seria prometer o que o dado não entrega.

### 7.3 Por que `quase_la` não entra no `Literal` da API

O REQ-003 da spec de arquitetura já fixa que `sort` só ordena e nunca dispara
chamada extra. Levar `quase_la` para a API não traria benefício nenhum — o backend
teria de fazer exatamente a mesma comparação sobre exatamente os mesmos campos que
já envia — e traria dois custos: um valor a mais no contrato público (que é
versionado pelo OpenAPI e consumido pelos tipos gerados) e a duplicação do limiar de
80%, que hoje vive num lugar só (`progress.ts`) e passaria a viver em dois, em
linguagens diferentes, livres para divergir.

O precedente já existe e é explícito: `group` é do SPA, não da API.

### 7.4 A documentação está errada sobre a URL, e esta spec corrige

Ao verificar o código para escrever esta spec, apareceu uma **deriva de
documentação** que precisa ser corrigida no mesmo ciclo:

| Afirmação | Onde | Realidade no código |
|---|---|---|
| a busca "não vai para a URL" | `ROADMAP.md` | está na URL como `q` (`Library.tsx`) |
| a busca "**não** entra na URL" | `REQ-031`, spec de arquitetura | idem |

O código passou dessas afirmações — e passou **bem**: a busca na URL usa
`replace: true`, para digitar não empilhar uma entrada de histórico por tecla, e
omite o default para manter a URL limpa. O que existe é melhor do que o que está
escrito; o defeito é só o registro.

Corrigir importa porque o REQ-031 é citado como fonte de verdade pelo `CLAUDE.md`,
e uma spec que descreve o oposto do código induz a próxima pessoa (ou agente) a
"consertar" um comportamento correto.

### 7.5 O que foi recusado, e por quê

- **"Horas sem conquista"** (eixo que cruzaria muito playtime com % baixo):
  recusado. Ordenar por `playtime` já mostra o percentual em cada card, então o
  usuário faz o cruzamento no olho imediatamente. Custaria um sexto botão numa
  barra que já tem cinco para economizar um olhar. GUD-160.
- **Conquistas mais raras de toda a biblioteca** (cross-game): recusado **agora**.
  Exigiria uma chamada de detalhe por jogo — a feature mais cara já cogitada — e
  quebraria a regra que rege todo o resto desta spec (custo zero de quota).
  Registrado para poder ser cobrado, não esquecido.
- **Filtro por faixa de raridade**: recusado. A ordenação `raras` põe as mais raras
  no topo, que é o que o filtro entregaria, sem um controle a mais.
- **Ordenar por data de desbloqueio crescente** ("minhas primeiras conquistas"):
  recusado por falta de pergunta. Ninguém abre um jogo para saber o que
  desbloqueou primeiro; quem quer isso rola até o fim da lista atual.

## 8. Dependencies & External Integrations

### Sistemas Externos
- **EXT-001**: Steam Web API — **nenhuma chamada nova**. `quase_la` reusa o
  `include=achievements` que `percent` e `ach_count` já disparam; se o usuário
  chegar por um desses eixos, o React Query serve do cache e o custo é zero.

### Dependências de Plataforma
- **PLT-001**: React 19, React Router (`useSearchParams`), TypeScript. Nenhuma
  dependência nova no `package.json`.

### Dependências de Dados
- **DAT-001**: `Achievement.global_percent` e `Game.percent`, ambos já existentes
  no contrato da API e já renderizados. Esta spec não pede campo nenhum.

## 9. Examples & Edge Cases

### Combinação de filtro e ordem no detalhe

```
?filter=pending&ordem=faceis   → "o que eu consigo hoje"
?filter=achieved&ordem=raras   → a vitrine
?filter=pending&ordem=raras    → o troféu difícil que vale caçar
?filter=all                    → estado inicial (nenhum parâmetro na URL)
```

### Raridade ausente

```
entrada:  [A: 12%, B: null, C: 3%, D: null]
ordem=raras   → C (3%), A (12%), B, D
ordem=faceis  → A (12%), C (3%), B, D
```

`B` e `D` nunca sobem, e mantêm entre si a ordem de entrada nos dois casos.

### `quase_la` na biblioteca

```
entrada:  [Alpha 100%, Beta 95%, Gama 85%, Delta 30%, Épsilon null]
saída:    Beta (95%), Gama (85%), Alpha, Delta, Épsilon
```

`Alpha` está em 100% — fechado, não "quase". `Épsilon` não tem dado de conquista.
Os dois caem no segundo grupo, na ordem em que chegaram.

### Jogo sem raridade nenhuma

Detalhe de um jogo cujo `GetGlobalAchievementPercentagesForApp` devolveu 403: todas
as conquistas com `global_percent: null`. O controle de ordenação **não aparece**
(REQ-165); a lista renderiza por desbloqueio, como hoje.

## 10. Validation Criteria

1. Todos os AC-160..170 têm teste correspondente e `npm run test` passa.
2. `npm run typecheck` (`tsc -b`) passa. ⚠️ **Nunca** validar com `tsc --noEmit`
   neste projeto — o `tsconfig.json` é só *references* com `"files": []`, então
   `--noEmit` checa zero arquivos e passa sempre (aviso do `CLAUDE.md`, já custou
   um deploy).
3. Nenhum arquivo sob `app/` foi modificado (CON-160).
4. `package.json` não ganhou dependência (PLT-001).
5. `frontend/src/lib/progress.ts` não foi alterado (CON-161).
6. Nenhum teste existente foi deletado; os de ordenação por desbloqueio seguem
   passando sem edição (o default não mudou).
7. A correção documental do §7.4 foi aplicada: `ROADMAP.md` e o REQ-031 da spec de
   arquitetura passam a descrever a busca como estado de URL.
8. A lista de eixos de ordenação no **§1 "No escopo"** da spec de arquitetura passa
   a incluir "quase lá", e o REQ-002 ganha uma nota de que este eixo é **do SPA** e
   deliberadamente **não** entra no `Literal` da API (REQ-169). Sem isso a spec de
   arquitetura passa a mentir por omissão sobre um eixo visível na tela — o mesmo
   defeito que o §7.4 corrige.
8. `/verify` no app real: com um perfil de biblioteca grande, `sort=quase_la`
   reordena de fato, e o detalhe de um jogo popular ordena por raridade nas duas
   direções. Um jogo **sem** stats globais abre sem o controle e sem erro.

## 11. Related Specifications / Further Reading

- `spec/spec-architecture-steam-achievements.md` — REQ-002/003 (`sort` só ordena),
  REQ-007 (filtro client-side), REQ-031 (busca e estado de URL — **a corrigir**,
  §7.4), REQ-040/041 (raridade global).
- `spec/spec-quase-la-completion-loop.md` — dona do limiar de 80% e do selo; esta
  spec **consome** `isQuaseLa()` e não redefine nada dela.
- `spec/spec-home-conversao.md` — origem do princípio "o que não tem o que dizer
  some em silêncio", aplicado aqui no REQ-165.
- `frontend/src/api/client.ts` — `includesFor()`, o ponto que o REQ-168 altera.
