# ADR-0001 — Um único `SteamClient` para a Web API e para a loja

- **Status:** aceito
- **Data:** 2026-07-13
- **Contexto da decisão:** revisão de arquitetura (candidato 4)

## Contexto

`app/steam/client.py` é a única camada que fala HTTP com a Steam, e hoje ela atende
**duas fontes com contratos opostos**:

| | Web API (5 métodos) | Loja (`get_app_genres`) |
|---|---|---|
| `STEAM_API_KEY` | sim (querystring) | **não** (nem aceita) |
| Token bucket | sim (protege a quota da chave) | **não** (não gasta quota) |
| Retry/backoff | sim (`_get()`) | **não** |
| Falha | levanta exceção tipada | **nunca levanta** — devolve `[]` |

Ou seja: o mesmo módulo tem dois contratos de erro. Quem chama precisa saber qual
método pertence a qual regime — o que é, literalmente, complexidade na interface.

## Decisão

**Não partir.** O `SteamClient` continua único.

A divergência é real, mas o seam seria **hipotético**: existe **um** endpoint da
loja, e um adapter não justifica um seam. Partir agora acrescentaria um parâmetro no
`AchievementsService`, uma linha de wiring no `lifespan` e um arquivo de teste — para
**mover** ~30 linhas, não para eliminá-las. O custo é imediato; o benefício, imaginário.

A assimetria já está documentada onde importa: no `CLAUDE.md` ("O endpoint de gênero
não passa por ele: não usa a key") e na docstring de `get_app_genres`.

## Consequências

- O `SteamClient` permanece com dois regimes de erro. É uma dívida **consciente**, e o
  custo dela é lido na docstring, não descoberto em produção.
- Testes seguem cobrindo os dois regimes no mesmo arquivo (`tests/test_client.py`).
- **Gatilho para reabrir:** o **segundo** endpoint da loja. Aí passam a existir dois
  adapters de verdade, o seam deixa de ser hipotético e o split se paga — provavelmente
  como `app/steam/store.py`, injetado no service ao lado do client.

Registrado para que a próxima revisão de arquitetura não re-sugira o split sem trazer
esse gatilho junto.
