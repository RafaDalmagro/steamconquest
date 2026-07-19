# Ordenação Derivada — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dar ao usuário dois eixos de ordenação que o dado já carregado permite — raridade das conquistas no detalhe e "quase lá" na biblioteca — sem nenhuma chamada nova à Steam.

**Architecture:** Tudo client-side. No detalhe, um `Record<OrdemAch, ...>` de comparadores e um controle de três opções, com `ordem` na URL ao lado do `filter` que já está lá. Na biblioteca, um valor novo no `Record<Sort, ...>` existente — que o TypeScript já usa para cobrar exaustividade — mais uma linha em `includesFor()`. Nenhum arquivo de `app/` é tocado.

**Tech Stack:** React 19, React Router (`useSearchParams`), TypeScript, Vitest + Testing Library. Nenhuma dependência nova.

**Spec:** `spec/spec-design-ordenacao-derivada.md` (v1.0). Divergência entre plano e spec ⇒ **a spec vence**; pare e reporte.

**Baseline:** branch `feat/ordenacao-derivada`, criada a partir da `main`.

## Global Constraints

- **Nenhum arquivo sob `app/` é modificado** (CON-160). Se um passo parecer exigir, o passo está errado.
- **`frontend/src/lib/progress.ts` não é alterado** (CON-161). `isQuaseLa()` é consumido como está; o limiar de 80% pertence a outra spec.
- **Nenhuma dependência nova** no `package.json` (PLT-001).
- **`npm run generate:api` não é rodado** (CON-162): nenhum modelo do backend muda.
- ⚠️ **Nunca validar com `tsc --noEmit`.** O `tsconfig.json` é só *references* com `"files": []` — `--noEmit` checa **zero** arquivos e passa sempre, inclusive com erro de tipo. Usar `npm run typecheck` (`tsc -b`). Já custou um deploy neste projeto.
- **Um teste por ciclo RED/GREEN.** Proibido escrever dois testes antes de implementar.
- **Nenhum teste existente é deletado.** O default de ordenação não muda, então a suíte atual de `GameDetail.test.tsx` deve passar **sem edição** — se ela quebrar, a mudança saiu do escopo.
- **Vocabulário como `Record`, nunca array** (CON-164): é o `Record` que faz o TS cobrar um comparador por eixo.
- **Idioma:** comentários, nomes de teste e rótulos de UI em **pt-BR**.
- O valor da aba "Pendentes" é **`locked`**, não `pending`.

---

## File Structure

| Arquivo | Responsabilidade | Ação |
|---|---|---|
| `frontend/src/components/SortBar.tsx` | Vocabulário `Sort` + rótulos; ganha `quase_la` | Modificar |
| `frontend/src/pages/Library.tsx` | Comparador de `quase_la` no `COMPARADORES` | Modificar |
| `frontend/src/api/client.ts` | `includesFor()` passa a cobrir `quase_la` | Modificar |
| `frontend/src/pages/GameDetail.tsx` | `OrdemAch`, comparadores, controle, `ordem` na URL | Modificar |
| `frontend/src/pages/Library.test.tsx` | Testes de `quase_la` | Modificar (append) |
| `frontend/src/pages/GameDetail.test.tsx` | Testes de raridade e URL | Modificar (append) |
| `spec/spec-architecture-steam-achievements.md` | §1 e REQ-002 registram o eixo do SPA | Modificar |
| `ROADMAP.md` | Item da feature | Modificar |

Nenhum arquivo novo. O controle de ordenação do detalhe fica **dentro** de `GameDetail.tsx`, e não num componente próprio: ele tem três botões e um `onChange`, é usado num lugar só, e extraí-lo agora criaria um arquivo para evitar quinze linhas. Se um segundo consumidor aparecer, extrai-se então.

---

### Task 1: Eixo `quase_la` na biblioteca

Cobre **AC-167**, **AC-168**, **AC-169**, **AC-170**. Começa pela biblioteca porque é a metade menor e independente — o detalhe não depende dela.

**Files:**
- Modify: `frontend/src/components/SortBar.tsx`, `frontend/src/pages/Library.tsx`, `frontend/src/api/client.ts`
- Test: `frontend/src/pages/Library.test.tsx`

**Interfaces:**
- Consumes: `isQuaseLa(percent)` de `@/lib/progress`; `Game` de `@/api/client`.
- Produces: o valor `"quase_la"` no tipo `Sort` (exportado de `SortBar.tsx`) — Task 2 não depende disto, mas testes futuros sim.

---

- [ ] **Step 1: Escrever o teste que falha (AC-167)**

Adicionar ao final de `frontend/src/pages/Library.test.tsx`, seguindo os *builders* já usados no arquivo:

```tsx
it("ordena os quase-concluídos primeiro, do mais perto de fechar", async () => {
  // 100% não é "quase": o loop está fechado. Ele e o 30% caem no segundo
  // grupo, na ordem em que a Steam devolveu.
  renderLibrary([
    jogo({ appid: 1, name: "Fechado", percent: 100 }),
    jogo({ appid: 2, name: "Noventa", percent: 95 }),
    jogo({ appid: 3, name: "Oitenta", percent: 85 }),
    jogo({ appid: 4, name: "Longe", percent: 30 }),
  ]);

  await userEvent.click(screen.getByRole("button", { name: /quase lá/i }));

  expect(nomesNaOrdem()).toEqual(["Noventa", "Oitenta", "Fechado", "Longe"]);
});
```

> **Ajuste ao arquivo real:** `renderLibrary`, `jogo` e `nomesNaOrdem` são os nomes que este plano usa para os helpers do arquivo. Abra `Library.test.tsx` e **use os helpers que já existem lá**, com os nomes que já têm. Não crie helpers novos se os equivalentes existirem — e se não existirem, extraia dos testes vizinhos o mesmo padrão de render.

- [ ] **Step 2: Rodar e confirmar que falha**

```bash
cd frontend && npm run test -- Library
```

Esperado: **FAIL**. O botão "Quase lá" não existe, então o `getByRole` não encontra nada.

- [ ] **Step 3: Acrescentar o eixo ao vocabulário**

Em `frontend/src/components/SortBar.tsx`, no tipo e no `Record`, **imediatamente após `percent`**:

```ts
export type Sort =
  | "playtime"
  | "name"
  | "percent"
  | "quase_la"
  | "ach_count"
  | "last_played";

const ROTULOS: Record<Sort, string> = {
  playtime: "Tempo de jogo",
  name: "Nome",
  percent: "% concluído",
  quase_la: "Quase lá",
  ach_count: "Nº de conquistas",
  last_played: "Última vez jogado",
};
```

Neste ponto `npm run typecheck` **deve falhar** em `Library.tsx`: o `Record<Sort, …>` de `COMPARADORES` ficou sem a chave `quase_la`. É o comportamento desejado (CON-164) — o tipo cobrou o comparador que falta.

- [ ] **Step 4: Escrever o comparador**

Em `frontend/src/pages/Library.tsx`, dentro de `COMPARADORES`, após `percent`:

```ts
  // Dois níveis: primeiro o grupo "quase lá", depois o mais perto de fechar.
  // Fora do grupo a ordem de entrada é preservada (sort estável), então 100% e
  // jogos sem dado de conquista caem para baixo sem critério inventado.
  quase_la: (a, b) =>
    Number(isQuaseLa(b.percent)) - Number(isQuaseLa(a.percent)) ||
    (b.percent ?? 0) - (a.percent ?? 0),
```

`isQuaseLa` já está importado no arquivo (é usado no `resumo()`) — não duplicar o import.

- [ ] **Step 5: Rodar o teste e o typecheck**

```bash
cd frontend && npm run test -- Library && npm run typecheck
```

Esperado: teste **PASS**, typecheck **limpo**.

- [ ] **Step 6: Escrever o teste do `include` (AC-169)**

Este é o passo que impede o "botão que não faz nada".

```tsx
it("pede os dados de conquista ao ordenar por quase lá", () => {
  // Sem include=achievements o percent vem null para todos, isQuaseLa devolve
  // false para todos, e o eixo não reordena nada.
  expect(includesFor("quase_la", "none")).toContain("achievements");
});
```

Se `Library.test.tsx` não for o lugar dos testes de `includesFor`, procure o arquivo que já os cobre (provavelmente junto de `api/client`) e acrescente lá.

- [ ] **Step 7: Rodar e confirmar que falha**

```bash
cd frontend && npm run test
```

Esperado: **FAIL** — `includesFor` ainda não conhece `quase_la`.

- [ ] **Step 8: Corrigir o `includesFor`**

Em `frontend/src/api/client.ts`:

```ts
export const includesFor = (sort: Sort, group: Group): Include[] => [
	...(sort === "percent" || sort === "ach_count" || sort === "quase_la"
		? (["achievements"] as const)
		: []),
	...(group === "genre" ? (["genres"] as const) : []),
];
```

- [ ] **Step 9: Escrever o teste dos jogos sem dado (AC-168)**

```tsx
it("não quebra com jogos sem dados de conquista", async () => {
  renderLibrary([
    jogo({ appid: 1, name: "SemDado", percent: null }),
    jogo({ appid: 2, name: "Quase", percent: 90 }),
  ]);

  await userEvent.click(screen.getByRole("button", { name: /quase lá/i }));

  expect(nomesNaOrdem()).toEqual(["Quase", "SemDado"]);
});
```

- [ ] **Step 10: Rodar tudo**

```bash
cd frontend && npm run test && npm run typecheck
```

Esperado: **tudo PASS**. AC-170 (o eixo sobrevive ao refresh) já é satisfeito de graça: `sort` lê da URL e o valor novo entra na validação `SORTS.some(...)` sem código adicional. Confirme que existe teste cobrindo isso para algum sort; se sim, não duplicar para `quase_la`.

- [ ] **Step 11: Commit**

```bash
git add frontend/src
git commit -m "feat(biblioteca): ordenar por \"quase lá\"

O eixo entra no includesFor: sem include=achievements o percent vem
null para todos e o botão não reordenaria nada.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: `ordem` na URL, sem apagar o `filter`

Cobre **AC-164**, **AC-165**, **AC-165b**. Vem **antes** dos comparadores de propósito: o AC-165b é uma regressão que o código atual introduziria, e é mais barato acertar o estado da URL com a lista ainda ordenada do jeito antigo.

**Files:**
- Modify: `frontend/src/pages/GameDetail.tsx`
- Test: `frontend/src/pages/GameDetail.test.tsx`

**Interfaces:**
- Produces: `type OrdemAch = "desbloqueio" | "faceis" | "raras"` e o `Record<OrdemAch, string>` de rótulos, consumidos pela Task 3.

---

- [ ] **Step 1: Escrever o teste que falha (AC-165b)**

```tsx
it("preserva a ordenação ao trocar de aba", async () => {
  // setParams({ filter }) substituiria a querystring inteira e apagaria a
  // ordem — trocar de aba não pode desfazer uma escolha de ordenação.
  renderGameDetail(detalhe(), { rota: "?filter=locked&ordem=raras" });

  await userEvent.click(screen.getByRole("tab", { name: /obtidas/i }));

  expect(urlAtual().search).toContain("ordem=raras");
  expect(urlAtual().search).toContain("filter=achieved");
});
```

> **Ajuste ao arquivo real:** use os helpers de render e de leitura da URL que `GameDetail.test.tsx` já tem. Se ele ainda não expõe um jeito de ler a querystring, os testes de `filter` existentes já resolvem isso de alguma forma — siga aquele mesmo caminho.

- [ ] **Step 2: Rodar e confirmar que falha**

```bash
cd frontend && npm run test -- GameDetail
```

Esperado: **FAIL** — `ordem=raras` desaparece ao clicar na aba.

- [ ] **Step 3: Trocar o `setFilter` por um atualizador combinado**

Em `frontend/src/pages/GameDetail.tsx`, substituir o bloco de leitura/escrita da URL:

```ts
  const [params, setParams] = useSearchParams();
  const raw = params.get("filter");
  const filter: Filter = isFilter(raw) ? raw : "all";
  const rawOrdem = params.get("ordem");
  const ordem: OrdemAch = isOrdem(rawOrdem) ? rawOrdem : "desbloqueio";

  // Um atualizador só para os dois parâmetros, como a Library já faz: escrever
  // um sem reler o outro apagaria o vizinho (setParams substitui a query
  // inteira). Defaults omitidos para manter a URL limpa; replace para o botão
  // Voltar não virar um desfazer de cliques em aba.
  const update = (next: { filter?: Filter; ordem?: OrdemAch }) => {
    const f = next.filter ?? filter;
    const o = next.ordem ?? ordem;
    const p: Record<string, string> = {};
    if (f !== "all") p.filter = f;
    if (o !== "desbloqueio") p.ordem = o;
    setParams(p, { replace: true });
  };
```

E o vocabulário novo, junto de `FILTROS`:

```ts
// Três opções explícitas, e não uma direção derivada da aba ativa: a aba
// "Todas" não teria resposta óbvia, e o mesmo controle mudaria de significado
// ao trocar de aba. Ver §7.1 da spec.
const ORDENS = {
  desbloqueio: "Desbloqueio",
  faceis: "Mais fáceis",
  raras: "Mais raras",
} as const;

type OrdemAch = keyof typeof ORDENS;

const isOrdem = (v: string | null): v is OrdemAch => v != null && v in ORDENS;
```

Trocar a chamada da aba de `setFilter(v as Filter)` para `update({ filter: v as Filter })`.

- [ ] **Step 4: Rodar e confirmar**

```bash
cd frontend && npm run test -- GameDetail && npm run typecheck
```

Esperado: **PASS**, e os testes de `filter` pré-existentes continuam passando sem edição.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/GameDetail.tsx frontend/src/pages/GameDetail.test.tsx
git commit -m "refactor(detalhe): atualizador combinado de filter e ordem na URL

setParams({ filter }) substituía a query inteira. Com dois parâmetros
isso apagaria a ordenação ao trocar de aba.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Ordenação por raridade

Cobre **AC-160**, **AC-161**, **AC-162**, **AC-163**.

**Files:**
- Modify: `frontend/src/pages/GameDetail.tsx`
- Test: `frontend/src/pages/GameDetail.test.tsx`

**Interfaces:**
- Consumes: `OrdemAch`, `ORDENS`, `update()` da Task 2.

---

- [ ] **Step 1: Escrever o teste que falha (AC-160)**

```tsx
it("ordena da mais comum para a mais rara em \"mais fáceis\"", async () => {
  renderGameDetail(
    detalhe({
      achievements: [
        conquista({ apiname: "a", display_name: "Rara", global_percent: 2 }),
        conquista({ apiname: "b", display_name: "Media", global_percent: 50 }),
        conquista({ apiname: "c", display_name: "Comum", global_percent: 90 }),
      ],
    }),
  );

  await userEvent.click(screen.getByRole("button", { name: /mais fáceis/i }));

  expect(nomesNaOrdem()).toEqual(["Comum", "Media", "Rara"]);
});
```

- [ ] **Step 2: Rodar e confirmar que falha**

```bash
cd frontend && npm run test -- GameDetail
```

Esperado: **FAIL** — o botão não existe.

- [ ] **Step 3: Implementar comparadores e controle**

Junto dos comparadores existentes em `GameDetail.tsx`:

```ts
// `null` (a Steam não devolveu raridade) vai sempre para o fim, nos dois
// sentidos — nunca para o topo de "raras". Tratá-lo como 0 afirmaria que a
// conquista sem dado é a mais rara do jogo, o que é falso e não é ordenação.
const porRaridade = (dir: 1 | -1) => (a: Achievement, b: Achievement) => {
  const x = a.global_percent;
  const y = b.global_percent;
  if (x == null) return y == null ? 0 : 1;
  if (y == null) return -1;
  return (x - y) * dir;
};

const COMPARADORES: Record<OrdemAch, (a: Achievement, b: Achievement) => number> = {
  desbloqueio: porDesbloqueio,
  faceis: porRaridade(-1), // maior % primeiro
  raras: porRaridade(1), // menor % primeiro
};
```

Trocar `.sort(porDesbloqueio)` por `.sort(COMPARADORES[ordem])`.

E o controle, **acima** do `<Tabs>` (é ortogonal às abas, e ficar dentro de um `TabsContent` o esconderia por aba):

```tsx
{data.achievements.some((a) => a.global_percent != null) && (
  <div className="mb-4 flex flex-wrap items-center gap-2">
    <span className="font-display text-xs uppercase tracking-widest text-muted-foreground">
      Ordenar:
    </span>
    {Object.entries(ORDENS).map(([value, label]) => (
      <Button
        key={value}
        size="sm"
        variant={ordem === value ? "active" : "default"}
        aria-pressed={ordem === value}
        onClick={() => update({ ordem: value as OrdemAch })}
        className="font-display text-xs uppercase tracking-wide"
      >
        {label}
      </Button>
    ))}
  </div>
)}
```

Acrescentar `import { Button } from "@/components/ui/button";` se ainda não houver. A guarda `some(...)` já entrega o **AC-166** (REQ-165) — o controle some quando não há raridade nenhuma.

- [ ] **Step 4: Rodar e confirmar**

```bash
cd frontend && npm run test -- GameDetail && npm run typecheck
```

Esperado: **PASS**.

- [ ] **Step 5: Teste da direção inversa (AC-161)**

```tsx
it("ordena da mais rara para a mais comum em \"mais raras\"", async () => {
  renderGameDetail(
    detalhe({
      achievements: [
        conquista({ apiname: "a", display_name: "Rara", global_percent: 2 }),
        conquista({ apiname: "b", display_name: "Media", global_percent: 50 }),
        conquista({ apiname: "c", display_name: "Comum", global_percent: 90 }),
      ],
    }),
  );

  await userEvent.click(screen.getByRole("button", { name: /mais raras/i }));

  expect(nomesNaOrdem()).toEqual(["Rara", "Media", "Comum"]);
});
```

- [ ] **Step 6: Rodar; deve passar direto**

```bash
cd frontend && npm run test -- GameDetail
```

Esperado: **PASS** (o Step 3 já implementou). Teste legítimo mesmo nascendo verde: `porRaridade(1)` e `porRaridade(-1)` são caminhos distintos, e um sinal trocado passaria despercebido com só um deles coberto.

- [ ] **Step 7: Teste da raridade ausente (AC-162)**

```tsx
it("manda as conquistas sem raridade para o fim, nos dois sentidos", async () => {
  renderGameDetail(
    detalhe({
      achievements: [
        conquista({ apiname: "a", display_name: "Doze", global_percent: 12 }),
        conquista({ apiname: "b", display_name: "SemA", global_percent: null }),
        conquista({ apiname: "c", display_name: "Tres", global_percent: 3 }),
        conquista({ apiname: "d", display_name: "SemB", global_percent: null }),
      ],
    }),
  );

  await userEvent.click(screen.getByRole("button", { name: /mais raras/i }));
  // As sem raridade nunca sobem, e mantêm entre si a ordem de entrada.
  expect(nomesNaOrdem()).toEqual(["Tres", "Doze", "SemA", "SemB"]);
});
```

- [ ] **Step 8: Teste da combinação com o filtro (AC-163)**

```tsx
it("combina o filtro de aba com a ordenação", async () => {
  renderGameDetail(
    detalhe({
      achievements: [
        conquista({ apiname: "a", display_name: "PendRara", achieved: false, global_percent: 5 }),
        conquista({ apiname: "b", display_name: "Obtida", achieved: true, global_percent: 50 }),
        conquista({ apiname: "c", display_name: "PendFacil", achieved: false, global_percent: 80 }),
      ],
    }),
  );

  await userEvent.click(screen.getByRole("tab", { name: /pendentes/i }));
  await userEvent.click(screen.getByRole("button", { name: /mais fáceis/i }));

  expect(nomesNaOrdem()).toEqual(["PendFacil", "PendRara"]);
});
```

- [ ] **Step 9: Teste do controle ausente (AC-166)**

```tsx
it("não mostra o controle de ordenação em jogo sem raridade nenhuma", () => {
  renderGameDetail(
    detalhe({
      achievements: [
        conquista({ apiname: "a", display_name: "Uma", global_percent: null }),
      ],
    }),
  );

  expect(screen.queryByRole("button", { name: /mais raras/i })).toBeNull();
});
```

- [ ] **Step 10: Rodar tudo**

```bash
cd frontend && npm run test && npm run typecheck
```

Esperado: **tudo PASS**, incluindo a suíte pré-existente sem edição.

- [ ] **Step 11: Commit**

```bash
git add frontend/src/pages/GameDetail.tsx frontend/src/pages/GameDetail.test.tsx
git commit -m "feat(detalhe): ordenar conquistas por raridade

Três opções explícitas em vez de direção derivada da aba: \"quais
pendentes são as mais raras\" é pergunta legítima e a derivação a
tornaria inexprimível.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Documentação

Cobre os itens 7 e 8 dos critérios de validação da spec.

**Files:**
- Modify: `spec/spec-architecture-steam-achievements.md` (§1 "No escopo"; REQ-002)
- Modify: `ROADMAP.md`

---

- [ ] **Step 1: Atualizar o §1 da spec de arquitetura**

Na lista "No escopo", trocar a linha de ordenação por:

```markdown
- Ordenação da biblioteca: playtime, nome, % concluído, **quase lá**, nº de
  conquistas, última vez jogado. O eixo "quase lá" é **do SPA** e não existe no
  contrato da API (ver REQ-002 e REQ-169 da `spec-design-ordenacao-derivada.md`).
- Ordenação das conquistas no detalhe: desbloqueio (default), mais fáceis, mais
  raras — client-side, sobre a lista já carregada.
```

- [ ] **Step 2: Acrescentar a nota ao REQ-002**

Ao final do REQ-002:

```markdown
  ⚠️ O eixo **`quase_la` do SPA não entra neste `Literal`**, deliberadamente: o
  backend faria a mesma comparação sobre os mesmos campos que já envia, e o limiar
  de 80% passaria a viver em dois lugares e duas linguagens, livres para divergir.
  Mesmo precedente do `group`. Ver REQ-169 da `spec-design-ordenacao-derivada.md`.
```

- [ ] **Step 3: Registrar no ROADMAP**

Acrescentar à seção de features de custo zero:

```markdown
- [x] **Ordenação por raridade no detalhe e "quase lá" na biblioteca**
      (`spec-design-ordenacao-derivada.md`). Zero chamada nova: os dois eixos
      ordenam dado que já estava na tela. Três opções explícitas no detalhe em vez
      de derivar a direção da aba — a aba "Todas" não teria resposta, e "quais
      pendentes são as mais raras" é pergunta legítima que a derivação apagaria.
      Dois achados de leitura de código: o `includesFor()` precisou incluir
      `quase_la` (senão o botão não reordenaria nada, por falta de `percent`), e o
      `setParams` do detalhe substituía a querystring inteira — com dois
      parâmetros, trocar de aba apagaria a ordenação.
```

- [ ] **Step 4: Commit**

```bash
git add spec/spec-architecture-steam-achievements.md ROADMAP.md
git commit -m "docs(ordenacao): registrar os eixos novos na spec e no roadmap

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: `/verify` no app real

Cobre o item 8 dos critérios de validação.

- [ ] **Step 1: Subir backend e frontend**

```bash
uv run uvicorn app.main:app --reload    # terminal 1
cd frontend && npm run dev              # terminal 2
```

Acessar pelo Vite (`http://localhost:5173`), que faz proxy de `/api`.

- [ ] **Step 2: Biblioteca**

Abrir `/u/{steamid}`, clicar em **Quase lá**. Confirmar: os jogos entre 80% e 99% sobem, o 100% **não** está entre eles, e a URL mostra `?sort=quase_la`. Recarregar: a ordem se mantém.

- [ ] **Step 3: Detalhe, jogo popular**

Abrir um jogo com raridade. Confirmar as três ordens; combinar `Pendentes` + `Mais fáceis` e conferir que os percentuais descem. **Trocar de aba e confirmar que a ordenação não se perde** (é a regressão da Task 2, e é a que os olhos pegam melhor que o teste).

- [ ] **Step 4: Detalhe, jogo sem stats globais**

Abrir um jogo cujo `GetGlobalAchievementPercentagesForApp` devolve 403 (o `ROADMAP.md` registra que isso acontece). Confirmar: a página abre, **sem** o controle de ordenação e sem erro.

- [ ] **Step 5: Registrar o resultado**

Acrescentar ao item do `ROADMAP.md` a linha do `/verify`, com o que foi observado. Se algo divergir, **reportar em vez de ajustar o texto** para caber no observado.

```bash
git add ROADMAP.md
git commit -m "docs(roadmap): registrar o /verify da ordenação derivada

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

**1. Cobertura da spec**

| Requisito | Tarefa |
|---|---|
| REQ-160 (três opções) | Task 3, Step 3 |
| REQ-161 (independência filtro/ordem) | Task 3, Step 8 |
| REQ-162 / §7.1 (direção não derivada) | Task 2, Step 3 (comentário) + Task 3 |
| REQ-163 (`null` no fim) | Task 3, Step 7 |
| REQ-164 (`ordem` na URL) | Task 2 |
| REQ-164b (não apagar o vizinho) | Task 2, Step 1 |
| REQ-165 (some sem raridade) | Task 3, Steps 3 e 9 |
| REQ-166 (`quase_la` no vocabulário) | Task 1, Step 3 |
| REQ-167 (comparador de dois níveis) | Task 1, Step 4 |
| REQ-168 (`includesFor`) | Task 1, Steps 6–8 |
| REQ-169 (não vai para a API) | Task 4, Step 2 |
| CON-160..164 | Global Constraints |
| AC-160..170 | Tasks 1–3 |
| Validação 7 e 8 | Task 4 |
| Validação 9 (`/verify`) | Task 5 |

Sem lacunas.

**2. Placeholders**

Nenhum. Há **duas notas de ajuste** (Task 1 Step 1, Task 2 Step 1) instruindo a usar os helpers que já existem nos arquivos de teste em vez dos nomes ilustrativos deste plano. Não são placeholders: a alternativa seria transcrever aqui os helpers de dois arquivos de teste, que envelheceriam no dia em que fossem renomeados.

**3. Consistência de tipos e nomes**

`OrdemAch`, `ORDENS`, `isOrdem`, `update` e `COMPARADORES` são definidos na Task 2 e usados com esses nomes na Task 3. O `Sort` estendido na Task 1 é o mesmo consumido por `includesFor`. O valor da aba pendente é `locked` em todo o plano. `porRaridade(dir)` é usado como `faceis: porRaridade(-1)` / `raras: porRaridade(1)`, coerente com os ACs 160 e 161.

⚠️ **Colisão de nome intencional:** `COMPARADORES` existe em `Library.tsx` (chaveado por `Sort`) e passa a existir em `GameDetail.tsx` (chaveado por `OrdemAch`). São módulos diferentes, sem import cruzado, e o nome é o certo nos dois. Não renomear um para "evitar confusão" — o paralelo é a informação.
