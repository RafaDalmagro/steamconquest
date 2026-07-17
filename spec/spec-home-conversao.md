---
title: Home — Conversão para Tráfego Morno — Especificação de Comportamento
version: 1.0
date_created: 2026-07-16
last_updated: 2026-07-16
owner: rafa.limadalmagro
tags: [frontend, react, conversion, zeigarnik, home]
---

# Introduction

Especificação de uma mudança **frontend-only** na `Home`: fazer do input o herói
da página, provar o produto antes de pedir o perfil, e alinhar a promessa do
título ao mecanismo que o app de fato explora — o **loop de completude** (efeito
Zeigarnik), já especificado em `spec-quase-la-completion-loop.md`.

A decisão de partida (entrevista de produto de 2026-07-16) é que o visitante é
**product-aware** e chega de contexto Steam/gaming: ele não precisa ser
convencido de que o problema existe, precisa do caminho mais curto até o pedido
e de prova de que o app vale o clique. Logo a mudança **subtrai** página — o
oposto do reflexo "marqueteiro" de acrescentar.

Estende os REQ-060..062 (identificação do perfil) da spec de arquitetura; herda
a numeração REQ-080/081 no mesmo espaço.

## 1. Purpose & Scope

**Propósito:** definir o comportamento observável da `Home` de forma não ambígua,
suficiente para implementação via TDD sem novas perguntas.

**No escopo:**
- Remoção da seção "Como funciona" (`PASSOS`) e promoção da linha de confiança.
- Um **link de demonstração** para um perfil real e público.
- O **ângulo** do título (loop de completude), sem travar redação exata.

**Fora do escopo (não implementar nesta iteração):**
- Qualquer mudança na **API/backend**, no payload ou nos endpoints.
- **Prova social** de qualquer forma (contadores, depoimentos, estrelas) — ver §6.
- Mudança no `<details>` "Não sei meu Steam ID" (REQ-062), no `ContinuarComo`
  (REQ-061) ou na validação de entrada (REQ-060).
- Motion novo, animação de entrada ou celebração.
- Persistência, analytics ou telemetria de conversão (proibido pela arquitetura:
  não há banco, e não se introduz um para medir).

**Audiência:** o desenvolvedor/agente que implementará a mudança.

**Premissas:**
- `usePlayerSummary(steamid)` já existe e degrada em silêncio (`ContinuarComo`
  devolve `null` quando o perfil não resolve) — o link de demo reusa o mesmo hook
  e o mesmo padrão, sem código novo de rede.
- O perfil de demo é **público e vivo**, verificado contra a API real da Steam em
  2026-07-16: `communityvisibilitystate=3`, 155 jogos, com progresso de conquistas
  real (inclui um jogo em 43/43 = 100%).

## 2. Definitions

- **Visitante novo**: sem `lastSteamId` no `localStorage`. Tem a objeção de
  confiança ("por que este site quer meu perfil?") e nenhuma prova.
- **Visitante recorrente**: com `lastSteamId` gravado. Já passou pela objeção de
  confiança — converteu ao menos uma vez. Para ele, o `ContinuarComo` (REQ-061)
  **é** o evento de conversão.
- **Perfil de demo**: o SteamID64 público fixo exibido como prova. É uma
  **constante de produto**, não configuração — ver CON-081.
- **Linha de confiança**: a frase que responde à objeção de confiança
  (sem login, sem senha, só dados públicos). Hoje existe, mas está sepultada no
  passo 1 de `PASSOS` — isto é, **depois** do pedido que ela deveria destravar.

## 3. Requirements, Constraints & Guidelines

### Funcionais — herói e linha de confiança

- **REQ-080**: A `Home` remove a seção "Como funciona" (`PASSOS`) e promove a
  linha de confiança para **junto do formulário**, onde a objeção ocorre. Regras:
  - A linha de confiança é visível **sem interação** (não vive dentro do
    `<details>` do REQ-062, que segue sendo fallback recolhido).
  - O título passa a nomear o **loop de completude** — "o que falta para o
    próximo 100%" — em vez de agregação ("tudo em um lugar"). A redação exata é
    **reversível** e não é critério de aceite; o ângulo é.
  - **Invariante de promessa↔prova (CON-080)**: o título do loop de completude só
    é honesto porque o REQ-081 o prova. A `Home` **não** exibe contagem "quase
    100%" — esse dado vive na `Library`, atrás da conversão.

### Funcionais — link de demonstração

- **REQ-081**: A `Home` exibe um link para a biblioteca do **perfil de demo**,
  rotulado como exemplo, apontando para `/u/{demo}`. Regras:
  - Renderiza **quando, e somente quando**, o visitante é **novo** (Definitions).
    Para o recorrente o link **não** renderiza: seria um alvo concorrendo com o
    `ContinuarComo`, levando **para longe** do que ele veio buscar.
  - Renderiza **somente** se o perfil de demo resolve. Falhou (404/429/502/rede)
    ⇒ **some em silêncio**, sem erro e sem espaço reservado — mesmo padrão do
    `ContinuarComo` e da raridade (CON-011 da spec-mãe): prova é decoração; sua
    ausência nunca quebra a página.
  - Exibe o **nome e o avatar** do perfil resolvido: é o que separa uma prova viva
    de um link hardcoded que ninguém verificou.
  - `lastSteamId` é um **proxy** de "já converteu", não prova: quem limpa o
    browser ou usa aba anônima é tratado como novo e revê a demo. Aceito — a
    falha é inócua (link redundante), e o erro inverso (recorrente sem sua
    biblioteca) não existe.

### Não-funcionais / Restrições

- **CON-080**: A promessa do título (REQ-080) é **acoplada** à existência da prova
  (REQ-081). Se o link de demo for removido no futuro, o título **deve** regredir
  para o ângulo de agregação. Nada no código expressa este acoplamento — esta
  linha é o único artefato que o carrega.
- **CON-081**: O SteamID de demo é **constante hardcoded** no `Home.tsx`, com
  comentário justificando a escolha do perfil. **Não** é variável de ambiente: não
  varia entre deploys, não é segredo (vai no `href`, e todo `VITE_*` é público de
  qualquer forma), e um var não-setada criaria um modo de falha indistinguível de
  "o perfil ficou privado".
- **CON-082**: Zero mudança no backend, zero dependência nova, zero endpoint novo.
  O link reusa `usePlayerSummary`.
- **CON-083** *(reversão consciente — ver §6)*: a `Home` passa a fazer **uma**
  chamada de perfil para o **visitante novo** (o `/profile` do demo). O
  comportamento anterior — zero chamadas sem `lastSteamId` — é **revogado** de
  propósito: sem a chamada não há como saber que a demo quebrou, e um 404 na cara
  do visitante novo é pior que a chamada. Custo real: 1 requisição à **própria
  API**; a chave `player_summary:{demo}` é fixa e compartilhada entre todos os
  visitantes, então o custo de quota Steam no regime é ≈ 0.
- **GUD-001**: Comentários e textos de UI em pt-BR (REQ da spec-mãe).

## 4. Acceptance Criteria

| # | Estado | Comportamento esperado |
|---|---|---|
| AC-1 | Sem `lastSteamId`, perfil de demo resolve | Link para `/u/{demo}` visível, com nome e avatar do perfil |
| AC-2 | Sem `lastSteamId`, perfil de demo **falha** | **Nenhum** link de demo; nenhuma mensagem de erro; formulário funcional |
| AC-3 | Com `lastSteamId` | **Nenhum** link de demo; `ContinuarComo` renderiza (REQ-061 intacto) |
| AC-4 | Qualquer estado | A seção "Como funciona"/`PASSOS` **não existe** na página |
| AC-5 | Qualquer estado | A linha de confiança é visível **sem** abrir o `<details>` |
| AC-6 | Com `lastSteamId` | **Nenhuma** chamada ao `/profile` do demo (só a do perfil salvo) |

Critérios herdados que **não podem regredir**:
- **AC-7**: AC-060..062 seguem válidos — a validação de entrada, o `<details>` de
  fallback e o `ContinuarComo` não mudam de comportamento.

## 5. Test Strategy (guia para o RED)

Testes de frontend (Vitest + Testing Library), pela **interface pública** (o que o
usuário vê), com `fetch` stubado — sem rede. Um ciclo RED→GREEN→REFACTOR por
comportamento, um teste por vez:

1. AC-1 — sem id salvo, demo resolve ⇒ link `/u/{demo}` com o nome do perfil.
2. AC-2 — sem id salvo, demo 404 ⇒ nenhum link, nenhum erro na tela.
3. AC-3 — com id salvo ⇒ `ContinuarComo` sim, demo não.
4. AC-4 — a seção `PASSOS` some (nenhum teste atual a cobre; a asserção é nova).

**Testes reescritos (CON-083) — três, não um.** A revogação tem raio maior do que
esta spec previu na v1.0: a chamada do perfil de demo acontece no **mount** de
todo visitante novo, então ela contamina toda asserção sobre *quantidade* ou
*ordem* de chamadas — não só a que falava explicitamente de "zero chamadas".
Nenhum dos três é deletado: cada um é **estreitado** para o que de fato protegia.

1. `"não busca perfil quando não há id salvo"` → `"não busca perfil salvo quando
   não há id salvo"`. Asseria `fetchSpy` **nunca** chamado; a propriedade morre
   com o REQ-081. Protegia: não buscar um perfil salvo que não existe.
2. `"recusa o id incompleto sem gastar chamada"`. Asseria zero chamadas.
   Protegia: **validar id incompleto não gasta quota** — o que segue verdadeiro.
3. `"resolve o nome do perfil na API e navega com o id devolvido"`. Asseria
   `urls[0]` = `/resolve`; o demo agora ocupa o índice 0. Protegia: um vanity
   passa pelo `/resolve` — a posição era incidental.

Padrão adotado: o helper `semDemo(urls)` filtra a chamada do demo, que é **ruído
de fundo** para quem testa o *submit*. Quem quiser asserir sobre o fluxo de
submit filtra; quem testa o próprio demo (AC-1) não.

**Tipagem**: `vi.fn()` sem assinatura tipa `mock.calls` como tupla vazia, e
`([url]) => …` não compila (TS2493). Stubs cujas URLs são inspecionadas precisam
de `vi.fn(async (_url: string) => …)`. O `npm run test` **não** pega isto — quem
pega é o `tsc -b` do `npm run build`, que roda no CI.

## 6. Decisões registradas (para poder ser cobrado)

**Decidido não fazer**, com o motivo:

- **Prova social** (contadores, depoimentos, "junte-se a N jogadores"): o app não
  tem banco, analytics nem usuários a citar — qualquer número seria **fabricado**.
  O visitante é um usuário Steam sendo convidado a colar seu perfil: ser pego
  inventando "3.000 jogadores" custa exatamente a confiança que a página existe
  para construir. **A demo é a prova** — demonstração no lugar de asserção é a
  única prova que este app produz honestamente.
- **Estrelas do GitHub como prova**: honesto e real, mas prova que o código
  existe, não que a ferramenta é boa — e mira desenvolvedor, que não é o público
  escolhido (tráfego morno, product-aware).
- **`VITE_DEMO_STEAMID`**: ver CON-081.
- **Screenshot da biblioteca no herói**: já rejeitado no projeto ("print da UI da
  Valve envelhece, e print velho é pior que texto nenhum", `Home.tsx`, e no
  ROADMAP). A demo viva substitui com vantagem.
- **Perfil do Gabe Newell (`76561197960287930`) como demo**: **verificado contra a
  API real em 2026-07-16 — a biblioteca é privada.** `GetPlayerSummaries` devolve
  o perfil (`personaname='Rabscuttle'`), mas `GetOwnedGames` levanta
  `SteamDataUnavailable`. O id segue válido como **fixture de teste** (lá ele só
  precisa ser parseado, nunca resolvido). Registrado para poupar a próxima pessoa
  de refazer a chamada.
- **Auto-redirect do recorrente para `/u/{lastSteamId}`**: sequestraria a página
  de quem quer consultar **outro** perfil. O `ContinuarComo` já entrega o atalho
  em um clique, sem tirar a escolha.
