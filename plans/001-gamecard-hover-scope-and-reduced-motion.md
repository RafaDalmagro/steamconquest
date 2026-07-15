# 001 — Escopar o hover do GameCard e respeitar reduced-motion

- **Status**: TODO
- **Commit**: f7a1f47
- **Severity**: MEDIUM
- **Category**: Performance (#5) + Acessibilidade (#6)
- **Estimated scope**: 2 arquivos (`index.css`, `GameCard.tsx`), ~5 linhas

## Problema

O card de jogo usa `transition-all` no hover e não tem gating de
`prefers-reduced-motion` para o deslocamento vertical.

```tsx
/* frontend/src/components/GameCard.tsx:21 — atual */
<Card className="overflow-hidden p-0 transition-all duration-150 group-hover:-translate-y-0.5 group-hover:border-primary group-hover:shadow-[0_0_12px_rgb(247_37_133/0.35)]">
```

Dois defeitos de craft nessa mesma string:

1. **`transition-all`** (AUDIT #5 — é sempre achado): anima *todas* as
   propriedades, não só as três que mudam no hover. Em um item de grid, com
   hover dezenas de vezes/dia, isso significa animar `box-shadow` e
   `border-color` fora da GPU sem necessidade. A curva usada é o default fraco
   do Tailwind, não uma `ease-out` deliberada.
2. **Sem `prefers-reduced-motion`** (AUDIT #6): o `group-hover:-translate-y-0.5`
   é uma mudança de posição. Usuários com "reduzir movimento" ligado devem
   continuar recebendo o feedback de borda/brilho, mas **sem** o deslocamento.

## Target

Trocar `transition-all` pela utility `transition` do Tailwind (que cobre um
conjunto curado — `color, background-color, border-color, opacity, box-shadow,
transform, translate, scale, rotate, filter` — e **exclui** propriedades de
layout como `width`/`height`), aplicar a curva `ease-snappy` (token novo, ver
abaixo) e neutralizar o lift sob reduced-motion.

```tsx
/* target */
<Card className="overflow-hidden p-0 transition duration-150 ease-snappy group-hover:-translate-y-0.5 group-hover:border-primary group-hover:shadow-[0_0_12px_rgb(247_37_133/0.35)] motion-reduce:group-hover:translate-y-0">
```

- `transition` (sem `-all`) → só as propriedades que realmente mudam animam.
- `ease-snappy` → `cubic-bezier(0.23, 1, 0.32, 1)`, ease-out forte (AUDIT #2).
- `motion-reduce:group-hover:translate-y-0` → sob reduced-motion o lift zera; a
  borda e o brilho (não são movimento) permanecem como feedback.

## Repo conventions to follow

- **Não há `tailwind.config`** — é Tailwind v4 CSS-first via `@tailwindcss/vite`.
  Tokens de tema vivem em `frontend/src/index.css`, com o valor cru em `:root` e
  o registro no bloco `@theme inline` (mesmo padrão das cores: `:root` define
  `--card: #16161f;` e `@theme inline` faz `--color-card: var(--card);`).
- O namespace de easing do Tailwind v4 é `--ease-*`; registrar `--ease-snappy`
  no `@theme` gera automaticamente a utility `ease-snappy`.
- Classes são compostas via `cn()`/string literal direto no `className` — não há
  CSS-in-JS. Edite a string de classes, não crie CSS novo.

## Steps

1. **Adicionar o token de easing (idempotente).** Em
   `frontend/src/index.css`, se `--ease-snappy` ainda **não** existir:
   - No bloco `:root` (após a linha `--font-sans: …;`, por volta da linha 26),
     adicione:
     ```css
     --ease-snappy: cubic-bezier(0.23, 1, 0.32, 1);
     ```
   - No bloco `@theme inline` (junto das outras `var()`, ex. após
     `--font-sans: var(--font-sans);`), adicione:
     ```css
     --ease-snappy: var(--ease-snappy);
     ```
   Se já existir (outro plano rodou antes), **não duplique** — pule este passo.

2. **Escopar e gating no card.** Em `frontend/src/components/GameCard.tsx:21`,
   substitua a `className` do `<Card>`:
   - `transition-all duration-150` → `transition duration-150 ease-snappy`
   - acrescente ao final `motion-reduce:group-hover:translate-y-0`

   Resultado exato:
   ```tsx
   <Card className="overflow-hidden p-0 transition duration-150 ease-snappy group-hover:-translate-y-0.5 group-hover:border-primary group-hover:shadow-[0_0_12px_rgb(247_37_133/0.35)] motion-reduce:group-hover:translate-y-0">
   ```

## Boundaries

- NÃO toque em nenhum arquivo além de `frontend/src/index.css` e
  `frontend/src/components/GameCard.tsx`.
- NÃO altere a estrutura/JSX do card, o `<img>`, os badges ou o `<Progress>`.
  Apenas a string de classes do `<Card>` e o token no CSS.
- NÃO mude as durações (`duration-150` fica) nem os valores de translate/shadow.
- NÃO adicione dependências.
- Se a `className` do `<Card>` na linha 21 não bater com o excerto atual acima
  (drift desde o commit `f7a1f47`), PARE e reporte em vez de improvisar.

## Verification

- **Mecânico**: na pasta `frontend/`, rode `npm run build` — deve compilar sem
  erros de Tailwind/TS. Rode `npm run test` — a suíte (incl.
  `GameCard.test.tsx`) deve continuar verde.
- **Feel check**: `npm run dev`, abra a biblioteca de um perfil, passe o mouse
  sobre um card e confirme:
  - o card sobe 2px, ganha borda rosa e o brilho neon — igual a antes;
  - no painel **Rendering** do DevTools, ative *Emulate CSS
    prefers-reduced-motion: reduce* e refaça o hover: a borda e o brilho ainda
    aparecem, mas o card **não sobe** mais.
  - no painel **Animations**, reduza o playback para 10% e confirme que só
    transform/borda/sombra transicionam (nada de reflow de largura/altura).
- **Done when**: `transition-all` não aparece mais em `GameCard.tsx`, o lift
  some sob reduced-motion, e build + testes passam.
