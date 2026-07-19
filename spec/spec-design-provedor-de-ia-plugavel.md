---
title: Provedor de IA Plugável (Anthropic × Gemini) — Especificação de Comportamento
version: 1.0
date_created: 2026-07-19
last_updated: 2026-07-19
owner: rafa.limadalmagro
tags: [backend, ia, custo, anthropic, gemini, configuracao]
---

# Introduction

Especificação da troca de provedor de IA por variável de ambiente. A Dica passa a
poder ser gerada por **Anthropic** ou **Gemini**, com um seletor em `AI_PROVIDER`.

A motivação declarada é **custo**. A pesquisa de preços feita na entrevista de
2026-07-19 mostrou que o gasto atual é dominado pela **busca web**, não pelos
tokens, e que o Gemini é ~10× mais barato neste volume por ter cota gratuita de
grounding. Ver §7 para os números e a correção de uma estimativa anterior.

Estende a `spec-design-dica-conquista-ia.md`; ocupa a numeração REQ-130+.

## 1. Purpose & Scope

**Propósito:** definir o comportamento observável da seleção de provedor, de
forma não ambígua, suficiente para implementação via TDD sem novas perguntas.

**No escopo:**

- Seletor `AI_PROVIDER` com dois valores: `anthropic` e `gemini`.
- Camada `app/ai/` reorganizada: base compartilhada + uma implementação por
  provedor.
- Configuração **por provedor**: chave, modelo, orçamento diário e reserva do
  dono.
- Chave de cache passa a incluir o provedor.
- Tradução das exceções de SDK para as exceções tipadas do domínio (correção de
  defeito existente — ver REQ-136).
- Rótulo da UI passa a nomear o provedor, **sem** perder o marcador de IA.

**Fora do escopo (não implementar nesta iteração):**

- **OpenAI.** Perde no eixo que motiva a mudança: busca web paga, sem cota
  gratuita comparável. A dependência foi adicionada por engano durante a
  exploração e removida.
- **Fallback automático entre provedores.** Feature diferente: exigiria detectar
  falha, escolher substituto e lidar com Dica gerada por provedor diferente do
  configurado. Um provedor ativo por vez.
- **Comparação lado a lado na UI.** A chave de cache por provedor já permite ter
  as duas sínteses vivas; comparar é trocar a env var e recarregar.
- **Troca de provedor em runtime** (por request, por query string). `AI_PROVIDER`
  é lido no boot. Input público não escolhe onde o dinheiro é gasto (CON-110).
- **Migração do cache existente.** Entradas `dica:{appid}:{apiname}` antigas
  simplesmente não são lidas pela chave nova; expiram sozinhas em 7 dias.

**Audiência:** o desenvolvedor/agente que implementará a mudança.

**Premissas:**

- `AiClient` atual (`app/ai/client.py`) funciona e foi verificado ponta a ponta
  com chave real contra Left 4 Dead 2.
- O SDK `google-genai` aceita `httpx.AsyncClient` injetado via
  `HttpOptions.httpx_async_client` — verificado por introspecção do pacote
  instalado. Isso permite testar os dois provedores no **mesmo** seam HTTP.
- `TokenBucket` (`app/core/rate_limit.py`) e `OrcamentoDeIA`
  (`app/core/orcamento.py`) já existem e são agnósticos de provedor.

## 2. Definitions

| Termo | Definição |
|---|---|
| **Provedor** | Fornecedor de IA que gera a Dica: `anthropic` ou `gemini`. |
| **Grounding** | Nome que o Gemini dá à busca web integrada. Equivalente funcional do `web_search` da Anthropic. |
| **Cota gratuita de grounding** | 5.000 buscas/mês que o Gemini não cobra. Acima disso, $14/1.000 — mais caro que a Anthropic. |
| **Seam de teste** | O limite HTTP (`httpx.MockTransport`), onde o corpo real que sai pela rede pode ser inspecionado. Igual para os dois provedores. |
| **Dica**, **Fonte**, **NPC** | Inalterados. Ver `CONTEXT.md`. |

## 3. Requirements, Constraints & Guidelines

### Seleção e configuração

- **REQ-130**: `AI_PROVIDER` seleciona o provedor. Valores aceitos: `anthropic`
  (default) e `gemini`. Valor fora do vocabulário deve falhar no **boot**, não
  na primeira requisição.
- **REQ-131**: Configuração é **por provedor**, com nomes que os SDKs leem por
  convenção:

  | Provedor | Chave | Modelo | Orçamento | Reserva |
  |---|---|---|---|---|
  | Anthropic | `ANTHROPIC_API_KEY` | `ANTHROPIC_MODEL` | `ANTHROPIC_DAILY_BUDGET` | `ANTHROPIC_OWNER_DAILY_BUDGET` |
  | Gemini | `GEMINI_API_KEY` | `GEMINI_MODEL` | `GEMINI_DAILY_BUDGET` | `GEMINI_OWNER_DAILY_BUDGET` |

- **REQ-132**: Apenas a chave do provedor **selecionado** é obrigatória. Ausente
  ⇒ falha no boot com mensagem que nomeia a variável faltante.
- **CON-130**: `AI_RATE_PER_MINUTE` / `AI_RATE_BURST` e `OWNER_STEAMID`
  permanecem **compartilhados**. O bucket é guarda de rajada, não de fatura; um
  número conservador serve aos dois.
- **CON-131**: `AI_PROVIDER` é lido no boot. **Proibido** parâmetro de query,
  header ou campo de request que escolha provedor — mesma regra do CON-110.

### Arquitetura

- **REQ-133**: `app/ai/` passa a ter uma base abstrata e uma implementação por
  provedor. A base concentra o que é **igual**: consumo do token bucket, montagem
  do prompt e contrato de erro. O único método abstrato é o que de fato muda —
  declarar a busca web e ler as fontes de volta.
- **CON-132**: O prompt é **idêntico** entre provedores. O que muda é o
  transporte, nunca o que se pede ao modelo — caso contrário a comparação de
  qualidade compararia prompts, não provedores.
- **CON-133**: `sintetizar(nome_do_jogo, name_en)` mantém a assinatura. Nenhum
  dado do jogador chega a provedor nenhum (AC-118 continua valendo).
- **CON-134**: `services/` e `web/` continuam sem importar SDK de IA. O serviço
  recebe um `ClienteDeIA` por construtor e não sabe qual é.

### Custo

- **REQ-134**: A chave de cache passa a ser `dica:{provedor}:{appid}:{apiname}`.
  Sem o provedor, trocar de provedor não teria efeito no que já está em cache — e
  a comparação de qualidade viraria comparação de estado de cache.
- **REQ-135**: Orçamento diário e reserva do dono são resolvidos a partir do
  provedor **ativo**. Trocar de provedor não pode exigir lembrar de reajustar o
  teto: esquecer é o erro que custa caro.
- **GUD-130**: Defaults sugeridos — Anthropic `3`/`3` (custo linear, ~$0,05 por
  dica); Gemini `100`/`50` (cota gratuita de 5.000 buscas/mês ≈ 1.666 dicas).

### Erros

- **REQ-136**: Cada implementação deve traduzir as exceções do seu SDK para
  `AiRateLimitError` (rate limit do provedor) ou `AiUnavailableError` (demais
  falhas). **Correção de defeito existente:** hoje nenhuma tradução acontece e
  uma exceção de SDK escapa como **500 sem `detail`**, que o frontend não sabe
  exibir. Passou despercebido porque o fake dos testes levantava a exceção já
  mapeada — testava-se um mapeamento que não existe.
- **CON-135**: A tradução mora na implementação do provedor, não no serviço:
  `services/` não conhece exceção de SDK.

### Interface

- **REQ-137**: O rótulo do painel passa a nomear o provedor **sem** perder o
  marcador de IA: `▌ NPC · modelo de IA (Gemini)`.
- **SEC-130**: Trocar "modelo de IA" por "Gemini" é **proibido**. Quem não
  conhece a marca não lê "Gemini" como inteligência artificial, e o SEC-113
  deixaria de ser cumprido. O nome do provedor é informação **adicional**.

### Padrões

- **PAT-130**: Os dois provedores são testados no **mesmo seam**:
  `httpx.MockTransport` injetado no SDK. Permite assertar sobre o corpo real que
  sai pela rede — que é onde moram os requisitos de custo e privacidade.
- **GUD-131**: Comentários e mensagens ao usuário em pt-BR.

## 4. Interfaces & Data Contracts

### Base compartilhada

```python
class ClienteDeIA(ABC):
    def __init__(self, *, model: str, rate_per_minute: float,
                 rate_burst: int, now=time.monotonic): ...

    async def sintetizar(self, nome_do_jogo: str, name_en: str) -> Dica:
        """Consome o bucket, monta o prompt e delega. Igual em todo provedor."""

    @abstractmethod
    async def _gerar(self, prompt: str) -> Dica:
        """Chama o provedor com busca web. Traduz exceção de SDK (REQ-136)."""
```

### Formatos por provedor (verificados nos SDKs instalados)

| | Anthropic | Gemini |
|---|---|---|
| SDK | `anthropic.AsyncAnthropic` | `google.genai.Client(...).aio` |
| Busca | `tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}]` | `config=GenerateContentConfig(tools=[Tool(google_search=GoogleSearch())])` |
| Texto | concatenação dos blocos `text` | `response.text` |
| Fontes | blocos `web_search_tool_result` → `.content[].{url,title}` | `candidates[0].grounding_metadata.grounding_chunks[].web.{uri,title}` |
| Injeção de HTTP | `AsyncAnthropic(http_client=...)` | `HttpOptions(httpx_async_client=...)` |

### Chave de cache

| Chave | TTL |
|---|---|
| `dica:{provedor}:{appid}:{apiname}` | `DICA_TTL` (7 dias), inalterado |

### Configuração (env)

| Variável | Default | Obrigatória? |
|---|---|---|
| `AI_PROVIDER` | `anthropic` | não |
| `ANTHROPIC_API_KEY` | — | só se `AI_PROVIDER=anthropic` |
| `ANTHROPIC_MODEL` | `claude-haiku-4-5` | não |
| `ANTHROPIC_DAILY_BUDGET` / `_OWNER_DAILY_BUDGET` | `3` / `3` | não |
| `GEMINI_API_KEY` | — | só se `AI_PROVIDER=gemini` |
| `GEMINI_MODEL` | `gemini-3.1-flash-lite` | não |
| `GEMINI_DAILY_BUDGET` / `_OWNER_DAILY_BUDGET` | `100` / `50` | não |
| `AI_RATE_PER_MINUTE` / `_BURST` | `2.0` / `5` | não (compartilhado) |
| `OWNER_STEAMID` | vazio | não (compartilhado) |

**Quebra de compatibilidade:** `AI_MODEL` deixa de existir; vira
`ANTHROPIC_MODEL`. Deploy existente precisa renomear.

## 5. Acceptance Criteria

- **AC-130**: Given `AI_PROVIDER=gemini`, When o app sobe, Then o serviço recebe
  a implementação do Gemini e nenhuma chamada é feita à Anthropic.
- **AC-131**: Given `AI_PROVIDER=gemini` sem `GEMINI_API_KEY`, When o app sobe,
  Then falha no **boot** com mensagem nomeando a variável — não no primeiro
  clique.
- **AC-132**: Given `AI_PROVIDER=gemini` sem `ANTHROPIC_API_KEY`, When o app
  sobe, Then sobe normalmente: só a chave do provedor ativo é exigida.
- **AC-133**: Given `AI_PROVIDER=invalido`, When o app sobe, Then falha no boot.
- **AC-134**: Given uma dica já cacheada com `AI_PROVIDER=anthropic`, When o
  provedor muda para `gemini` e a mesma conquista é pedida, Then uma nova síntese
  é gerada — a chave inclui o provedor.
- **AC-135**: Given `AI_PROVIDER=gemini`, When o corpo enviado é inspecionado,
  Then declara a ferramenta `google_search` e **não** contém `steamid` nem dado
  do jogador.
- **AC-136**: Given que o SDK do provedor levanta erro de rate limit, When a dica
  é pedida, Then a resposta é **429** — não 500.
- **AC-137**: Given que o SDK do provedor levanta erro genérico, When a dica é
  pedida, Then a resposta é **502** com `detail` em pt-BR.
- **AC-138**: Given `AI_PROVIDER=gemini`, When o orçamento é consultado, Then usa
  `GEMINI_DAILY_BUDGET`, não o da Anthropic.
- **AC-139**: Given uma dica gerada, When o painel é renderizado, Then exibe o
  nome do provedor **e** a expressão "modelo de IA" (SEC-130).
- **AC-140**: Given os dois provedores, When o prompt enviado é comparado, Then é
  idêntico (CON-132).

## 6. Test Automation Strategy

- **Test Levels**: Unit (base e cada implementação), Integration (rotas),
  Config (boot), Component (frontend).
- **Frameworks**: `pytest`, Vitest.
- **Seam único**: `httpx.MockTransport` injetado nos dois SDKs. O helper
  `make_ai()` de `tests/test_ai_client.py` vira parametrizável por provedor.
- **Custo**: **nenhum teste chama provedor de verdade.** O `conftest.py` já
  garante que env var vence `.env`; deve passar a fixar `GEMINI_API_KEY` também.
- **Coverage**: todo AC-130..AC-140 com teste correspondente.

## 7. Rationale & Context

### Por que dois provedores, e não três ou um

A motivação declarada foi **custo**. Medido:

| | Custo/dica | ~180 dicas/mês |
|---|---|---|
| Haiku 4.5 + web search | $0,049 | **$8,82** |
| Gemini 3.1 Flash-Lite + grounding | $0,005 | **$0,89** |
| Gemini 3.5 Flash + grounding | $0,036 | $5,35 |

**A busca é 61% do custo na Anthropic, não os tokens.** É por isso que a cota
gratuita de grounding do Gemini muda tanto o resultado.

A OpenAI saiu porque não compete nesse eixo: busca paga, sem cota gratuita
equivalente. Manter uma terceira implementação sem motivo de custo é manutenção
pura — três parsers de fonte, três mapeamentos de erro, três suítes.

Um provedor só (trocar tudo para Gemini) foi considerado e recusado por
sequenciamento: a implementação da Anthropic **já está verificada ponta a ponta**,
e apagá-la para apostar num caminho ainda não testado inverte o risco. Com os
dois, a troca é reversível e a comparação de qualidade sai de graça.

### Correção de uma estimativa anterior

Na entrevista eu afirmei que o Gemini sairia **de graça**, com base na cota de
5.000 prompts/mês. Estava errado em dois pontos:

1. **O Gemini 2.5 Flash foi descontinuado em junho/2026.** A vantagem do
   "cobrado por prompt" (uma unidade por requisição, independente do número de
   buscas) morreu com ele. Os modelos 3.x cobram **por busca**, igual à Anthropic.
2. **A folga é menor do que parecia.** 5.000 buscas ÷ ~3 por dica ≈ **1.666
   dicas/mês**, não 5.000.

O Gemini continua ~10× mais barato, mas "de graça" era exagero: os tokens custam.

### Por que a cota gratuita torna o orçamento *mais* importante

Passados os 5.000, o Gemini cobra **$14/1.000 buscas** — mais caro que os $10 da
Anthropic. O teto diário deixa de proteger contra custo linear e passa a proteger
contra um **degrau**: dentro da cota é quase grátis, fora dela é o mais caro dos
dois. Por isso o default do Gemini (`100`/dia) é generoso mas não ilimitado.

### Por que configuração por provedor, e não uma variável genérica

Testado contra o cenário de erro: com `AI_MODEL` e `AI_DAILY_BUDGET` genéricos, o
valor correto depende de qual provedor está ativo — e **nada no arquivo diria
isso**. Trocar `AI_PROVIDER` para `anthropic` esquecendo de baixar um orçamento
calibrado para o Gemini custaria ~$240/mês.

Chave de API genérica tem um problema adicional: os SDKs leem `ANTHROPIC_API_KEY`
e `GEMINI_API_KEY` por convenção. Nome genérico obrigaria a injetar à mão em
todos, brigando com o ecossistema sem ganho.

O custo aceito é um `.env` maior: ~10 linhas só de IA.

### Por que o prompt não muda entre provedores

Se cada provedor tivesse prompt afinado para si, a comparação de qualidade
compararia **prompts**, não provedores — e a conclusão seria inútil para decidir
qual manter.

### Por que o rótulo mantém "modelo de IA"

`▌ NPC · Gemini` seria mais limpo e violaria o SEC-113. "Gemini" é uma marca:
quem a conhece lê como IA, quem não conhece lê como nome próprio — possivelmente
o nome do NPC. O marcador tem de sobreviver a quem nunca ouviu falar do
fornecedor.

### Custos assumidos conscientemente

1. **Duas implementações para manter**, com dois parsers de fonte que quebram por
   motivos independentes quando um fornecedor mudar de formato.
2. **`.env` maior** — a legibilidade piora para eliminar um acoplamento silencioso.
3. **Cache não atravessa a troca** de provedor. Trocar *para* o Gemini é barato;
   voltar re-paga.
4. **Quebra de compatibilidade** em `AI_MODEL` → `ANTHROPIC_MODEL`.

## 8. Dependencies & External Integrations

### External Systems

- **EXT-130**: API Anthropic — já integrada.
- **EXT-131**: Gemini Developer API — grounding com Google Search.

### Third-Party Services

- **SVC-130**: Cota gratuita de grounding do Gemini (5.000 buscas/mês). Acima,
  $14/1.000. É premissa de custo, não garantia contratual: se mudar, o
  `GEMINI_DAILY_BUDGET` é o botão a girar.

### Technology Platform Dependencies

- **PLT-130**: `google-genai` (cliente assíncrono via `Client(...).aio`).
- **PLT-131**: `anthropic` — já presente.
- **PLT-132**: `openai` **removida** — adicionada por engano na exploração.

### Compliance Dependencies

- **COM-130**: `GEMINI_API_KEY` sujeita à mesma disciplina de segredo da
  `ANTHROPIC_API_KEY` e da `STEAM_API_KEY`: só env, nunca no bundle, log,
  resposta ou `.env.example`.

## 9. Examples & Edge Cases

```python
# REQ-132 — só a chave do provedor ativo é obrigatória. Validar no boot mantém
# o fail-fast sem exigir chave de provedor que não vai ser usado.
@model_validator(mode="after")
def _exige_chave_do_provedor_ativo(self):
    chave = {"anthropic": self.anthropic_api_key, "gemini": self.gemini_api_key}
    if not chave[self.ai_provider]:
        raise ValueError(
            f"AI_PROVIDER={self.ai_provider} exige {self.ai_provider.upper()}_API_KEY"
        )
    return self
```

```python
# CON-132 — o prompt é o mesmo; só o transporte muda.
class GeminiClient(ClienteDeIA):
    async def _gerar(self, prompt: str) -> Dica:
        try:
            r = await self._sdk.aio.models.generate_content(
                model=self._model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())]
                ),
            )
        except <rate limit do SDK> as exc:
            raise AiRateLimitError(str(exc)) from exc   # REQ-136
        except <erro genérico do SDK> as exc:
            raise AiUnavailableError(str(exc)) from exc
        ...
```

### Edge cases

| Caso | Comportamento esperado |
|---|---|
| `AI_PROVIDER=gemini`, sem `GEMINI_API_KEY` | Falha no boot nomeando a variável (AC-131) |
| `AI_PROVIDER=gemini`, sem `ANTHROPIC_API_KEY` | Sobe normalmente (AC-132) |
| `AI_PROVIDER` com valor inválido | Falha no boot (AC-133) |
| Dica cacheada por outro provedor | Ignorada; nova síntese é gerada (AC-134) |
| Gemini responde sem `grounding_metadata` | Dica com `fontes: []`. Texto sem fonte é pior que com, e muito melhor que erro |
| Gemini bloqueia por safety | `AiUnavailableError` → 502. Não inventar texto |
| Provedor estoura rate limit | `AiRateLimitError` → 429 (AC-136) |
| Orçamento do provedor esgotado | `DicaSemOrcamento` → 429 "volte amanhã", inalterado |
| Troca de provedor com cache cheio | Entradas antigas permanecem até expirar; ocupam espaço sob `_MAXSIZE` sem serem lidas |

## 10. Validation Criteria

- Todos os AC-130..AC-140 têm teste automatizado e passam.
- `uv run pytest`, `npm run test` e **`npm run typecheck`** verdes.
  *(`tsc --noEmit` não serve — checa zero arquivos; ver `CLAUDE.md`.)*
- `docker build` passa.
- `rg -n "openai" pyproject.toml app/` não retorna nada — PLT-132.
- `rg -n "anthropic|genai" app/services app/web` não retorna nada — CON-134.
- `rg -n "dica:" app/services/achievements.py` mostra o provedor na chave —
  REQ-134.
- Um teste prova que o prompt é idêntico entre provedores — CON-132/AC-140.
- Um teste prova que o painel exibe "modelo de IA" junto do provedor — SEC-130.
- `CLAUDE.md` documenta a chave `dica:{provedor}:{appid}:{apiname}` e a camada.
- `/verify`: com chave real, gerar a mesma dica nos dois provedores e comparar
  texto e fontes lado a lado.

## 11. Related Specifications / Further Reading

- `spec/spec-design-dica-conquista-ia.md` — a feature que esta spec generaliza.
  AC-118 (nenhum dado do jogador), SEC-111 (mensagem vaga), CON-110 (input
  público não escolhe modelo), SEC-113 (marcador de IA).
- `docs/adr/0001-steam-client-unico.md` — o precedente de "não partir sem seam
  real". Aqui o seam **é** real: duas implementações, não uma hipotética.
- `docs/adr/0002-fase-b-sem-monetizacao.md` — por que o custo importa tanto.
- `CONTEXT.md` — Dica, Fonte, NPC.
- `CLAUDE.md` — disciplina de cache, segredos, e o aviso sobre `tsc --noEmit`.
