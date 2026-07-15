---
title: Loop de Completude "Quase lá" — Especificação de Comportamento
version: 1.0
date_created: 2026-07-14
last_updated: 2026-07-14
owner: rafa.limadalmagro
tags: [frontend, react, engagement, zeigarnik, library]
---

# Introduction

Especificação de uma feature **frontend-only** que dá destaque aos jogos
**quase concluídos** (progresso alto, mas ainda não 100%) na biblioteca. O
objetivo de produto é abrir o *loop de completude* (efeito Zeigarnik): hoje o app
celebra apenas o loop **fechado** (selo `✦ 100%`) e trata "42%" e "96%" de forma
idêntica. Esta feature marca o loop **quase-fechado**, que é o que mais puxa a
próxima sessão.

É derivação pura do payload já carregado (`percent` por jogo) — **sem** chamada à
API, **sem** backend, **sem** persistência. Estende os REQ-032 (resumo agregado) e
REQ-033 (badge do card) da spec de arquitetura; herda a numeração REQ-070/071 no
mesmo espaço.

Fonte da decisão de limiar (percentual, e não conquistas restantes) e das
superfícies (card + resumo, sem sort): entrevista de produto de 2026-07-14.

## 1. Purpose & Scope

**Propósito:** definir o comportamento observável do destaque "Quase lá" de forma
não ambígua, suficiente para implementação via TDD sem novas perguntas.

**No escopo:**
- Um **selo visual** no card do jogo (`GameCard`) para jogos quase concluídos.
- Uma **contagem agregada** na linha de resumo da biblioteca (`Library`).

**Fora do escopo (não implementar nesta iteração):**
- Opção de **ordenação** "Quase lá" no `SortBar` — ordenação é server-side
  (REQ-002/003); exigiria mudança de API e está deliberadamente adiada.
- Qualquer mudança na **API/backend**, no payload ou nos endpoints.
- Persistência, histórico ou snapshot de progresso (proibido pela arquitetura).
- Limiar **configurável** pelo usuário — o valor é constante de produto.
- Animação de celebração, som, confete ou qualquer motion novo.
- Mudança nos selos existentes **`✦ 100%`** (REQ-033 complete) e **"Recente"**
  (REQ-033 recém-jogado), ou na página de **detalhe** do jogo.

**Audiência:** o desenvolvedor/agente que implementará a feature.

**Premissas:**
- O payload da biblioteca (REQ-001) já expõe, por jogo, `percent` (número ou
  `null`), `achieved_count` e `total_count`. Nenhum dado novo é necessário.
- A UI já arredonda o progresso exibido com `Math.round(game.percent)`
  (`GameCard.tsx`), e `complete` é definido como `percent === 100` sobre esse
  valor arredondado.

## 2. Definitions

- **percent exibido**: `Math.round(game.percent)` — o mesmo inteiro já mostrado no
  card e derivado no `resumo()`. Toda a lógica desta spec usa este valor
  arredondado, **não** o `game.percent` cru, para garantir consistência entre o
  número mostrado e o selo (um card nunca mostra "80%" sem selo, nem "100%" com o
  selo "Quase lá").
- **Quase lá**: um jogo cujo *percent exibido* satisfaz `80 ≤ percent < 100`.
  Requer `game.percent != null` — jogo sem sistema de conquistas ou sem dados
  (`percent == null`, REQ-008) **nunca** é "Quase lá".
- **Completo**: *percent exibido* `=== 100` (definição pré-existente). "Completo" e
  "Quase lá" são **mutuamente exclusivos** por construção do intervalo.

## 3. Requirements, Constraints & Guidelines

### Funcionais — selo no card

- **REQ-070**: O `GameCard` exibe um selo **"Quase lá"** quando, e somente quando,
  o jogo é *Quase lá* (Definitions). Regras:
  - O selo é **mutuamente exclusivo** com o selo `✦ 100%` (REQ-033/complete):
    como os intervalos não se sobrepõem, um card nunca mostra os dois. O selo
    "Quase lá" ocupa a **mesma posição** do `✦ 100%` (canto superior direito).
  - O selo **"Recente"** (REQ-033, canto superior esquerdo) é independente e
    **pode coexistir** com o "Quase lá".
  - Rótulo é o **texto fixo "Quase lá"**, sem número. Justificativa: o gatilho é
    percentual; um "Faltam N" ficaria incoerente num jogo grande (ex.: 480/500 =
    96% entra como Quase lá, e "Faltam 20" contradiz a ideia de "quase"). *(Escolha
    de rótulo reversível; confirmar no REVIEW.)*
  - O selo é **decoração informativa**: sua ausência de dados (`percent == null`)
    nunca quebra o card — simplesmente não renderiza.

### Funcionais — contagem no resumo

- **REQ-071**: A linha de resumo da biblioteca (REQ-032, `resumo()` em `Library`)
  acrescenta a contagem de jogos *Quase lá* presentes **na lista já filtrada em
  tela** (`jogos`, pós-busca do REQ-031). Regras:
  - Aparece sob a **mesma condição** da contagem de 100% já existente: só quando
    `games.some((g) => g.percent != null)` (há progresso a exibir).
  - Posiciona-se **imediatamente antes** da parte "M jogos 100%", lendo, por
    exemplo: `12 jogos · 340,0 h · 3 jogos quase 100% · 1 jogo 100%`.
  - Usa o helper de pluralização existente: `${plural(quase, "jogo")} quase 100%`
    (⇒ "1 jogo quase 100%" / "3 jogos quase 100%").
  - Quando a contagem é **zero**, a parte é **omitida** (não exibir "0 jogos quase
    100%"), espelhando o estilo enxuto do resumo atual.

### Não-funcionais / Restrições

- **CON-001**: Zero chamadas à API. Toda a lógica deriva do payload já em memória
  (mesmo princípio dos REQ-007/031/032).
- **CON-002**: O limiar `80` e o teto `100` são **constantes de produto** no
  frontend, nomeadas (ex.: `QUASE_LA_MIN = 80`), não valores mágicos espalhados.
- **CON-003**: A feature não introduz dependência, motion novo, nem toca no
  backend, na página de detalhe ou nos selos existentes.
- **GUD-001**: Comentários e textos de UI em pt-BR (REQ da spec-mãe).

## 4. Acceptance Criteria

Cenários observáveis (percent = *percent exibido*, arredondado):

| # | Estado do jogo | Selo no card | Contado no resumo |
|---|---|---|---|
| AC-1 | `percent = 85` | **"Quase lá"** (sup. direito) | em "quase 100%" |
| AC-2 | `percent = 80` (borda inferior) | **"Quase lá"** | em "quase 100%" |
| AC-3 | `percent = 99` | **"Quase lá"** | em "quase 100%" |
| AC-4 | `percent = 100` | **`✦ 100%`** (não "Quase lá") | em "100%", não em "quase" |
| AC-5 | `percent = 79` | nenhum | não contado |
| AC-6 | `percent = null` (sem conquistas) | nenhum | não contado |
| AC-7 | `percent = 85` **e** jogado nas 2 semanas | "Recente" (esq.) **+** "Quase lá" (dir.) | em "quase 100%" |

Critérios de tela:
- **AC-8**: Com 3 jogos *Quase lá* e 1 completo visíveis, o resumo lê
  `… · 3 jogos quase 100% · 1 jogo 100%`, nessa ordem.
- **AC-9**: Sem nenhum jogo *Quase lá*, a parte "quase 100%" **não** aparece no
  resumo (não há "0 jogos quase 100%").
- **AC-10**: A busca (REQ-031) que estreita a lista **recalcula** a contagem
  "quase 100%" sobre o resultado filtrado.
- **AC-11**: Agrupado por gênero (REQ-004), os cards continuam exibindo o selo
  "Quase lá" normalmente (o selo é por-card, independe do agrupamento).
- **AC-12**: Nenhuma requisição de rede nova é disparada ao renderizar/atualizar
  os selos ou a contagem (verificável na aba Network).

## 5. Test Strategy (guia para o RED)

Testes de frontend (Vitest + Testing Library), pela **interface pública** (o que o
usuário vê), com dados de jogo montados à mão — sem rede:

- `GameCard`: renderiza selo "Quase lá" para `percent` 80/85/99; **não** renderiza
  para 79, 100 e `null`; coexiste com "Recente"; nunca junto de `✦ 100%`.
- `Library`/`resumo()`: monta a parte "N jogos quase 100%" na ordem e plural
  corretos; omite quando zero; recalcula sob filtro de busca.

Cada comportamento é um ciclo RED→GREEN→REFACTOR (um teste por vez).
