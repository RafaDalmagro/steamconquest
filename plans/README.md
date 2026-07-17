# Planos de animação — steamconquest

Auditoria de motion do frontend (React 19 + Tailwind v4 CSS-first, sem lib de
motion). Cada plano é self-contained: valores exatos, sem referência a discussão
externa. Executáveis por qualquer agente, inclusive modelo mais barato.

Commit-base da auditoria: `f7a1f47`.

## Planos

| # | Título | Severidade | Categoria | Status |
|---|--------|-----------|-----------|--------|
| 001 | Escopar o hover do GameCard e respeitar reduced-motion | MEDIUM | Performance + Acessibilidade | TODO |
| 002 | Escopar a transição da barra de Progress | LOW | Performance | TODO |
| 003 | Feedback de press nos botões | MEDIUM | Física | TODO |

> Os 4 achados da auditoria viram 3 planos: os achados **1** (perf) e **4**
> (reduced-motion) compartilham a mesma linha (`GameCard.tsx:21`), então foram
> unidos no plano **001** para evitar edição conflitante da mesma `className`.

## Ordem de execução recomendada

`001 → 003 → 002` (por alavancagem: card de grid → tato global dos botões →
polimento da barra). A ordem **não é obrigatória** — os planos são independentes.

## Dependência compartilhada: token `--ease-snappy`

Os três planos usam o token de easing `--ease-snappy: cubic-bezier(0.23, 1,
0.32, 1)` em `frontend/src/index.css` (`:root` + `@theme inline`, gerando a
utility `ease-snappy`). Cada plano tem, como **passo 1 idempotente**, "adicionar
o token se ainda não existir". Portanto:

- O **primeiro** plano executado cria o token;
- Nos seguintes, o passo 1 é no-op (não duplicar a definição).

Não há outra dependência entre os planos.

> ⚠️ **Atualização de 17/07/2026** — o token **já existe no `:root`**, criado fora
> destes planos pela animação do `<details>` (a gaveta "Não sei meu Steam ID" no
> `Home.tsx`), que precisou da mesma curva. **Só a metade `:root` existe**: a
> entrada em `@theme inline` **não** foi adicionada, então a utility
> `ease-snappy` ainda **não** é gerada. Quem executar 001/002/003 e precisar da
> *utility* (e não do `var(--ease-snappy)` em CSS puro) tem de acrescentar a
> entrada no `@theme inline` — o passo 1 "criar o token" vai parecer pronto e
> não está, para esse uso.

## Fora de escopo (missed opportunities não convertidas)

Levantadas na auditoria, mas **não** viraram plano (aguardam decisão):

- Entrada em stagger do grid de `GameCard` (`Library.tsx`) — deleite decorativo,
  on-brand arcade.
- Crossfade na troca de filtro do detalhe (`GameDetail.tsx`) — reflow de lista é
  caro de fazer certo; baixa prioridade.
