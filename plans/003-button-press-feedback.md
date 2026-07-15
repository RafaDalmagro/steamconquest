# 003 — Feedback de press nos botões

- **Status**: TODO
- **Commit**: f7a1f47
- **Severity**: MEDIUM
- **Category**: Física (#3)
- **Estimated scope**: 2 arquivos (`index.css`, `button.tsx`), ~2 linhas

## Problema

Os botões não têm nenhum feedback de pressionar. `Button` é usado nos filtros de
ordenação (`SortBar`), agrupamento (`GroupBar`) e no submit do Home — elementos
clicados o tempo todo. AUDIT #3: elemento pressável sem feedback de `:active` é
achado; um `scale` sutil no press dá tato e combina com a personalidade arcade
do "Pixel Ember".

```tsx
/* frontend/src/components/ui/button.tsx:6-7 — atual */
const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:pointer-events-none disabled:opacity-50",
```

O `transition-colors` só cobre cor; para animar o `scale` no press é preciso uma
`transition-property` que inclua `transform`.

## Target

Adicionar `active:scale-[0.97]` com uma transição que cubra cor **e** transform,
duração de 100ms (faixa de press-feedback do AUDIT #3: 100–160ms), curva
`ease-snappy`, e gating de reduced-motion para não escalar quando o usuário pede
menos movimento.

```tsx
/* target — base string do cva */
const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-[color,background-color,transform] duration-100 ease-snappy active:scale-[0.97] motion-reduce:active:scale-100 cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:pointer-events-none disabled:opacity-50",
```

- `transition-[color,background-color,transform]` substitui `transition-colors`
  (mantém o fade de hover **e** habilita o scale).
- `duration-100 ease-snappy` → press rápido e responsivo.
- `active:scale-[0.97]` → afunda 3% ao pressionar (sutil, faixa 0.95–0.98).
- `motion-reduce:active:scale-100` → sob reduced-motion não há scale.

## Repo conventions to follow

- Tailwind v4 CSS-first; token `--ease-snappy` registrado em
  `frontend/src/index.css` (`:root` + `@theme inline`) — ver plano 001, passo 1.
- `button.tsx` usa `cva(...)` (class-variance-authority); a string base é o
  **primeiro argumento** de `cva`. As variantes (`variant`/`size`) ficam intactas.
- O mesmo padrão de press vale para `Button`; não replicar em cada uso — mudar só
  a base do `cva` já cobre SortBar, GroupBar e Home.

## Steps

1. **Garantir o token `ease-snappy` (idempotente).** Se `--ease-snappy` não
   existir em `frontend/src/index.css`, adicione conforme o plano 001, passo 1.
   Se já existir, pule.

2. Em `frontend/src/components/ui/button.tsx:7`, na string base do `cva`,
   substitua `transition-colors` por:
   ```
   transition-[color,background-color,transform] duration-100 ease-snappy active:scale-[0.97] motion-reduce:active:scale-100
   ```
   Mantenha todo o restante da string (flex, rounded, focus-visible, disabled)
   inalterado e na mesma ordem.

## Boundaries

- NÃO toque em `SortBar.tsx`, `GroupBar.tsx`, `Home.tsx` nem em qualquer outro
  consumidor — a mudança é só na base do `cva` em `button.tsx` (+ token no CSS).
- NÃO altere os `variants` (`default`/`active`/`ghost`), os `size`, os
  `defaultVariants` nem a assinatura do componente.
- NÃO adicione dependências.
- Se a string base do `cva` não contiver `transition-colors` como no excerto
  (drift desde `f7a1f47`), PARE e reporte.

## Verification

- **Mecânico**: em `frontend/`, `npm run build` compila; `npm run test` verde
  (incl. testes que renderizam botões).
- **Feel check**: `npm run dev`:
  - clique e segure um botão de filtro em SortBar/GroupBar — ele afunda ~3% e
    volta ao soltar; o hover de cor continua funcionando;
  - o botão "Ver biblioteca" no Home também afunda ao pressionar;
  - painel **Rendering** → *prefers-reduced-motion: reduce*: pressionar **não**
    escala mais (a cor ainda responde);
  - painel **Animations** a 10%: só `transform` anima no press, sem reflow.
- **Done when**: pressionar qualquer `Button` dá scale sutil, some sob
  reduced-motion, e build + testes passam.
