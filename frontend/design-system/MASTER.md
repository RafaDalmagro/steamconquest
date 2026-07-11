# Design System — Steam Achievements

Fonte de verdade visual do SPA. Antes de estilizar qualquer página/componente,
leia este arquivo. Regras aqui valem para todas as telas salvo override em
`design-system/pages/<pagina>.md`.

**Identidade:** dark mode único (OLED-friendly), estética de companion app de
jogos. Paleta é a **marca Steam** (não inventar cores novas). Denso em dados,
legível, sem decoração que atrapalhe a leitura de números.

---

## 1. Tokens de cor (tema escuro único)

Já vivem em `src/index.css` (padrão shadcn). Mantidos como estão — são a marca
Steam correta:

| Token | Hex | Uso |
|---|---|---|
| `--background` | `#1b2838` | fundo da página (casco Steam) |
| `--foreground` | `#c7d5e0` | texto padrão |
| `--card` / `--secondary` / `--muted` | `#2a475e` | superfícies elevadas |
| `--muted-foreground` | `#8f98a0` | texto secundário, labels, **estado pendente** |
| `--primary` | `#66c0f4` | ação primária, links, foco, barra de progresso |
| `--primary-foreground` | `#171a21` | texto sobre primário |
| `--accent` / `--border` / `--input` | `#335b7d` | bordas, divisórias, hover sutil |
| `--ring` | `#66c0f4` | anel de foco (teclado) |
| `--destructive` | `#e05a47` | erro |
| `--header` | `#171a21` | barra de topo |

### Adicionar (lacuna real — conquista obtida × pendente)

O detalhe de jogo precisa distinguir **obtida × pendente** e hoje não há token
para isso. Cor sozinha não basta (§7), mas o token é necessário:

```css
:root {
  --achieved: #a4d007;            /* lime Steam — conquista obtida, fill de progresso "completo" */
  --achieved-foreground: #171a21;
  /* pendente reusa --muted-foreground (#8f98a0) + ícone de cadeado, nunca só cor */
}
@theme inline {
  --color-achieved: var(--achieved);
  --color-achieved-foreground: var(--achieved-foreground);
}
```

Contraste `#a4d007` sobre `#1b2838` ≈ 9:1 (AAA). `#c7d5e0` sobre `#1b2838` ≈
9.5:1 (AAA). `#66c0f4` sobre `#1b2838` ≈ 7:1 (AAA). Paleta passa em AAA — não
degradar ao ajustar.

---

## 2. Tipografia

- **UI / corpo:** `system-ui, sans-serif` (já no `body`). Mantido — zero peso de
  rede, legível. Não trocar por Orbitron: é display, ilegível em dado corrido.
- **Números:** usar a utility `tabular-nums` do Tailwind (figuras tabulares sobre
  a própria system-ui) para não pular de largura ao ordenar/atualizar. **Já
  aplicado** no `GameCard`. Replicar em qualquer coluna numérica nova. Fonte mono
  dedicada é desnecessária — `tabular-nums` já resolve o jitter.

### Escala de tipo
`12 · 14 · 16 · 18 · 24 · 32` px. Corpo base **16px** (evita zoom automático iOS).
Peso: título 600–700, corpo 400, label 500. Line-height corpo 1.5.

---

## 3. Espaçamento & layout

- Ritmo **4/8px**. Gutters de seção: `16 / 24 / 32`.
- Container desktop: `max-w-6xl` centralizado, gutter horizontal `px-4 md:px-6`.
- Grid da biblioteca: `grid gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4`.
- Breakpoints: 375 / 768 / 1024 / 1440. Mobile-first, sem scroll horizontal.
- `radius`: `--radius: 0.5rem` (já definido) para cards/botões/badges.

---

## 4. Estrutura por página

> O gerador sugeriu um pattern de *landing/newsletter* — **descartado**. Isto é
> um dashboard pessoal de 2 rotas.

### Library (`/`)
`Header` (título + brand) → `SortBar` (playtime · nome · % · nº conquistas) →
grid de `GameCard`. Empty state quando a conta não tem jogos. Skeleton no load.

`SortBar`: 1 controle segmentado; opção ativa destacada por cor+peso (não só cor).
`percent`/`achieved_count` só existem quando `sort=percent|ach_count` → o GameCard
**só mostra %** nesses modos (o backend só preenche aí — não renderizar `NaN`).

### GameDetail (`/game/{appid}`)
`Header` com back previsível → resumo (nome, ícone, **anel/barra de %**,
`obtidas / total`) → `Tabs` de filtro (Todas · Obtidas · Pendentes) → lista de
`AchievementItem`. Se `supports_achievements=false`: mensagem informativa, sem
quebrar, sem tabs.

---

## 5. Componentes (specs)

**GameCard** — card `--card`; ícone do jogo (declarar width/height p/ evitar CLS,
`loading="lazy"`); nome (trunca com ellipsis, título completo em `title`);
playtime `.tabular` ("N h" ou "N min"); barra de % só em modo percent/ach_count.
Card inteiro clicável → detalhe; `cursor-pointer`; hover: leve elevação de
`--accent`, transição 150–300ms; foco visível.

**AchievementItem** — ícone (pendente = `opacity-50` no card), `display_name` (600),
`description` (`--muted-foreground`), e **Badge de texto** "Obtida"/"Pendente"
(variantes `achieved` = verde `--achieved` / `locked` = muted). Estado transmitido
por texto **e** cor — nunca só cor. **Já implementado.**

**Progress** — fill `--achieved` quando 100%, senão `--primary`. Sempre com label
textual `%` ao lado (não depender só da barra). `aria-valuenow`.

**Tabs de filtro** — aba ativa por cor+peso+indicador. Contagem por aba opcional.

---

## 6. Interação & movimento

- Micro-interações 150–300ms, `ease-out` entrando. Respeitar
  `prefers-reduced-motion`.
- Só `transform`/`opacity` em hover/press (sem animar width/height/top/left).
- Loading > 300ms → `Skeleton` (já existe `ui/skeleton`), não spinner longo.
- Estados de botão: hover/press/disabled distintos; disabled com opacidade
  reduzida + `cursor` alterado + `disabled`.

---

## 7. Acessibilidade (checklist de entrega)

- [ ] Cor nunca é o único sinal: obtida/pendente usa **ícone + cor**; sort ativo
      usa **peso + cor**.
- [ ] Contraste ≥ 4.5:1 texto normal (paleta já em AAA — manter).
- [ ] Foco visível (`--ring`) em todo clicável; ordem de tab = ordem visual.
- [ ] Alvos de toque ≥ 44px no mobile (SortBar, tabs, card).
- [ ] `alt`/`aria-label` em ícones e imagens com significado; back button rotulado.
- [ ] `img` com width/height (CLS < 0.1); `loading="lazy"` fora da dobra.
- [ ] `prefers-reduced-motion` respeitado.
- [ ] Sem scroll horizontal em 375px; testar 375/768/1024/1440.

---

## 8. Evitar

Emoji como ícone (usar Lucide/SVG) · Orbitron em texto corrido · animar
layout (CLS) · números sem figuras tabulares (jitter ao ordenar) · renderizar
`%` quando o backend não preencheu · estado só por cor · remover foco.
