# 002 — Escopar a transição da barra de Progress

- **Status**: TODO
- **Commit**: f7a1f47
- **Severity**: LOW
- **Category**: Performance (#5)
- **Estimated scope**: 1–2 arquivos (`progress.tsx`, `index.css` só se o token faltar), ~1 linha

## Problema

O indicador da barra de progresso usa `transition-all`, mas a única coisa que
muda no elemento é o `transform` (o `translateX` que revela o preenchimento).

```tsx
/* frontend/src/components/ui/progress.tsx:30-36 — atual */
<ProgressPrimitive.Indicator
  className={cn(
    "h-full transition-all",
    complete ? "bg-achieved" : "bg-primary",
  )}
  style={{ transform: `translateX(-${100 - (value ?? 0)}%)` }}
/>
```

AUDIT #5: `transition-all` é sempre achado. Aqui ele também animaria a troca de
`background-color` (primary → achieved ao completar), fade de cor que não é
intencional — o preenchimento deve deslizar, não desbotar de cor.

## Target

Escopar para `transition-transform` e aplicar a curva `ease-snappy` (mesmo token
do plano 001), mantendo a duration default do Tailwind (150ms — apropriada para
um indicador de estado).

```tsx
/* target */
<ProgressPrimitive.Indicator
  className={cn(
    "h-full transition-transform ease-snappy",
    complete ? "bg-achieved" : "bg-primary",
  )}
  style={{ transform: `translateX(-${100 - (value ?? 0)}%)` }}
/>
```

Efeito colateral desejado: ao virar 100%, a cor troca instantaneamente (sem
crossfade de cor) enquanto só a barra desliza — comportamento correto.

## Repo conventions to follow

- Tailwind v4 CSS-first; o token `--ease-snappy` é registrado em
  `frontend/src/index.css` (`:root` + `@theme inline`) — ver plano 001, passo 1.
- Classes compostas via `cn(...)`; edite só o primeiro argumento string.

## Steps

1. **Garantir o token `ease-snappy` (idempotente).** Se `--ease-snappy` **não**
   existir em `frontend/src/index.css`, adicione-o exatamente como no plano 001,
   passo 1 (valor cru em `:root`, `var()` no `@theme inline`). Se já existir,
   pule.

2. Em `frontend/src/components/ui/progress.tsx:32`, troque
   `"h-full transition-all"` por `"h-full transition-transform ease-snappy"`.
   Nenhuma outra alteração no arquivo.

## Boundaries

- NÃO toque em outros arquivos além de `frontend/src/components/ui/progress.tsx`
  e (só se o token faltar) `frontend/src/index.css`.
- NÃO mexa no `style={{ transform: … }}`, nas classes condicionais de cor, na
  `Root`, no overlay `SEGMENTED` nem na assinatura do componente.
- NÃO adicione dependências.
- Se a linha 32 não bater com `"h-full transition-all"` (drift desde `f7a1f47`),
  PARE e reporte.

## Verification

- **Mecânico**: em `frontend/`, `npm run build` compila; `npm run test` verde.
- **Feel check**: `npm run dev`, abra o detalhe de um jogo com progresso parcial
  e a biblioteca:
  - a barra desliza suave ao carregar (transform), sem animar largura/layout;
  - num jogo 100%, a barra fica dourada (achieved) sem crossfade de cor —
    troca seca de cor, deslize contínuo.
  - painel **Animations** a 10%: apenas `transform` transiciona no indicador.
- **Done when**: `transition-all` não aparece mais em `progress.tsx` e
  build + testes passam.
