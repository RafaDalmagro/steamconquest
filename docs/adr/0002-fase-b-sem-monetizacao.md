# ADR-0002 — A Fase B entrega o agente de IA sem monetização

- **Status:** aceito
- **Data:** 2026-07-18
- **Contexto da decisão:** planejamento da v0.0.4 (grilling da Fase B)

## Contexto

A §10.1 da `spec-design-guia-conquista-pendente.md`, escrita em 2026-07-17,
registrou a Fase B — o agente de IA que sintetiza como obter uma conquista
pendente — como **serviço pago, só para assinantes, cobrança via Stripe**. Aquela
nota foi explícita quanto ao preço arquitetural: monetizar por assinatura reabre
três decisões que o projeto fechou de propósito.

1. **Identidade persistente.** "Quem é o assinante?" só tem resposta com conta.
   O `steamid` vem da URL pública, é forjável, e não autentica ninguém.
2. **Estado durável.** Assinatura ativa/cancelada/inadimplente não cabe no
   `TTLCache` volátil com teto de despejo. É banco.
3. **Webhook do Stripe.** Superfície de entrada nova, fora do request do usuário,
   com verificação HMAC obrigatória.

Ao planejar a v0.0.4 a pergunta ficou concreta: construir isso agora, ou depois?

O app tem **um** usuário. Não há telemetria, não há segundo usuário, não há
ninguém pedindo acesso. Implementar cobrança primeiro constrói a catraca antes do
show — e a maior parte do trabalho não seria IA, seria cobrança:

| | Só o agente | Agente + Stripe |
|---|---|---|
| Invariantes reabertos | nenhum | login, multiusuário, banco |
| Superfície de entrada nova | 1 endpoint, atrás de gate | + webhook público |
| Proporção do trabalho que é IA | quase todo | minoria |
| Pré-requisito de negócio | nenhum | alguém disposto a pagar |
| Reversível? | sim, é uma feature | não, são três invariantes |

Há também o custo que **não** desaparece sem Stripe: a chave paga de LLM precisa
ser protegida de qualquer jeito. O gate de assinante teria sido, de quebra, o gate
de abuso. Sem ele, é preciso outro — e é preciso mesmo, porque `appid` e `apiname`
vêm da URL pública.

## Decisão

**Entregar a Fase B sem monetização.** A v0.0.4 traz o agente de IA operando
single-user, com a `ANTHROPIC_API_KEY` só em env, **sem** login, **sem**
multiusuário, **sem** banco e **sem** webhook. Os três invariantes do projeto
permanecem fechados.

O gate de abuso, que a monetização teria fornecido de graça, é construído
explicitamente e é **boundary de segurança**, não otimização:

- Validação de que a conquista é **pendente** num jogo **da biblioteca** do
  `steamid` — limita *o que* pode ser pedido, e sai de graça porque os dados já
  estão no cache para renderizar o detalhe.
- Token bucket global para as chamadas ao LLM, espelhando o padrão que já protege
  a `STEAM_API_KEY` — limita *quão rápido*.

A monetização não é rejeitada: é **adiada sem data**, e deixa de ser pré-requisito
da Fase B.

## Consequências

- Os três invariantes (single-user, sem banco, sem login) seguem valendo, e o
  `CLAUDE.md` não precisa ser reescrito.
- A `ANTHROPIC_API_KEY` entra no rol de segredos só-env, mesma disciplina da
  `STEAM_API_KEY`. É a primeira vez que o projeto tem **custo marginal em dinheiro
  por request** — antes, o pior caso de abuso era 429; agora é fatura.
- O gate duplo é código novo que a monetização teria dispensado. É trabalho que
  **não** se perde se a assinatura chegar depois: um gate de assinante somaria a
  ele, não o substituiria.
- O cache `dica:{appid}:{apiname}` é volátil e guarda dado pago — todo restart
  descarta Dicas já compradas. Aceito conscientemente no volume de um usuário
  (ver `spec-design-dica-conquista-ia.md` §7).
- A §10.1 da spec anterior fica **parcialmente revertida**. Ela continua correta
  sobre *o que a monetização exigiria*; deixa de valer como plano da Fase B.

## Gatilho para reabrir

Reabrir a monetização quando existir um **segundo usuário pedindo acesso** — não
antes, e não por projeção. Nesse momento a ordem da §10.1 volta a valer
integralmente: novo ciclo SDD reabrindo login, multiusuário e estado durável,
**antes** de qualquer código. O gate de assinante entra como camada adicional
sobre o gate de abuso já existente.

Gatilho secundário, independente do primeiro: se a fatura de LLM passar a incomodar
com um usuário só, o problema não é monetização — é cache volátil sobre dado pago,
e a decisão a revisitar é a persistência, não a cobrança.
