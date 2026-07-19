# Steam Achievements

Acompanhamento pessoal de conquistas, biblioteca e tempo de jogo de uma conta
Steam. Este arquivo é o glossário do domínio — só termos cujo sentido é próprio
deste projeto, e onde escolher a palavra errada confunde de verdade.

## Language

### Orientação da conquista

**Dica**:
Texto sintetizado por IA explicando como obter **uma** conquista pendente
específica, acompanhado das fontes citadas.
_Avoid_: Guia, guia de IA, tutorial

**Guia**:
Documento escrito pela comunidade Steam, publicado na plataforma e organizado por
**jogo** — não por conquista. Não existe guia de uma conquista isolada; existe o
guia 100% do jogo.
_Avoid_: Dica, artigo

**Fonte**:
URL citada junto de uma Dica, para o usuário conferir a síntese contra o material
original.
_Avoid_: Referência, link, citação

**NPC**:
A persona sob a qual a Dica é apresentada na interface. Nome de **UI**, não de
domínio — no código o conceito continua sendo Dica, e renomeá-lo seria descolar
o código da spec. Escolhido por ser obviamente artificial: um NPC dá dica de
missão e ninguém o confunde com pessoa, o que mantém a confiança condicional que
a Fonte pressupõe. Por isso aparece sempre acompanhado de "modelo de IA".
_Avoid_: Assistente, IA, bot, agente, mascote

### Conquistas

**Pendente**:
Conquista que o jogador ainda não obteve. É o único estado que recebe orientação —
Dica e link de vídeo só existem aqui.
_Avoid_: Bloqueada, não obtida, locked

**Obtida**:
Conquista já desbloqueada pelo jogador.
_Avoid_: Completa, unlocked, conquistada

**`apiname`**:
Identificador estável da conquista na Steam (ex.: `ACH_SPA`). Nunca é exibido ao
usuário e nunca serve para busca.
_Avoid_: `api_name`, id, chave

**`name_en`**:
Nome canônico da conquista em inglês. Existe para ser **pesquisável**, nunca para
ser exibido — o texto em pt-BR da Steam é outro texto, não uma tradução
("Descanso no Spa" × "Spa Healer"), e material de conquista é escrito em inglês.
_Avoid_: Nome original, nome traduzido, título

**Raridade**:
Percentual global de jogadores que obtiveram a conquista. Vem da Steam e é igual
para todo mundo.
_Avoid_: Dificuldade, popularidade

### Fases do produto

**Fase B**:
Nome histórico do agente de IA que gera Dicas. Preservado porque a
`spec-design-guia-conquista-pendente.md` §10.1 e o `ADR-0002` o referenciam.
_Avoid_: Fase 2, v2
