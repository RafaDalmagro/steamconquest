# Steam Web API — Documentação do Projeto

Fonte de verdade dos endpoints usados pelo app. Apenas o que o projeto consome.
Referência oficial: <https://partner.steamgames.com/doc/webapi> e
<https://developer.valvesoftware.com/wiki/Steam_Web_API>.

## Convenções

- **Base URL:** `https://api.steampowered.com`
- **Autenticação:** parâmetro de query `key={STEAM_API_KEY}` (server-side only).
  Nunca logar a URL completa (vaza a chave). Ver `CLAUDE.md` → Segurança.
- **Formato:** `format=json` (default JSON).
- **Identificador do jogador:** `steamid` = SteamID64 (`{STEAM_ID}`).
- **Erros de autorização:** perfil privado ou key inválida ⇒ HTTP `401`/`403`.
- **Rate limit / indisponibilidade:** `429` (rate limit) e `5xx` ⇒ retry com
  backoff no client; esgotado, propaga exceção tipada.

---

## 1. IPlayerService/GetOwnedGames/v1

Biblioteca, tempo de jogo, nome e ícone dos jogos da conta.

> ⚠️ Endpoint oficial da Valve, porém historicamente **fora** do índice público
> de alguns docs. É o correto para a conta — **não** trocar por `GetAppList`
> (catálogo global, não a conta).

**Método:** `GET /IPlayerService/GetOwnedGames/v1/`

### Parâmetros

| Parâmetro | Obrigatório | Valor no projeto | Descrição |
|---|---|---|---|
| `key` | sim | `{STEAM_API_KEY}` | chave da Web API |
| `steamid` | sim | `{STEAM_ID}` | SteamID64 do jogador |
| `include_appinfo` | sim | `1` | inclui `name` e `img_icon_url` |
| `include_played_free_games` | sim | `1` | inclui jogos free jogados |
| `format` | não | `json` | formato da resposta |

### Resposta (campos usados)

```json
{
  "response": {
    "game_count": 2,
    "games": [
      {
        "appid": 220,
        "name": "Half-Life 2",
        "playtime_forever": 7200,
        "playtime_2weeks": 180,
        "rtime_last_played": 1710000000,
        "img_icon_url": "fcfb366051782b8ebf2aa297f3b746395858cb62"
      }
    ]
  }
}
```

| Campo | Tipo | Uso |
|---|---|---|
| `response.game_count` | int | total de jogos |
| `games[].appid` | int | identificador do jogo |
| `games[].name` | string | nome (requer `include_appinfo=1`) |
| `games[].playtime_forever` | int | **minutos** totais jogados |
| `games[].playtime_2weeks` | int (opcional) | **minutos** nas últimas 2 semanas → badge "Recente" |
| `games[].rtime_last_played` | int (epoch UTC) | última vez jogado → `sort=last_played` |
| `games[].img_icon_url` | string | hash do ícone (montar URL, ver abaixo) |

### Notas

- `playtime_forever` está em **minutos**; converter para exibição (horas).
- `playtime_2weeks` **só vem no payload de quem jogou nas últimas 2 semanas** — a
  ausência é o caso normal, não erro.
- `rtime_last_played` é epoch em **segundos**, UTC. `0` (ou ausente) significa
  **nunca jogado**, não 1970 — ordenar esses por último.
- Perfil privado ⇒ `response` vazio / sem `games` ⇒ tratar como
  `SteamDataUnavailable`.
- **URL do ícone do jogo:**
  `https://media.steampowered.com/steamcommunity/public/images/apps/{appid}/{img_icon_url}.jpg`

---

## 2. ISteamUserStats/GetPlayerAchievements/v1

Lista de conquistas do jogador para um jogo, com a flag de obtida.
**% e contagem saem daqui** — o schema NÃO é necessário para o percentual.

**Método:** `GET /ISteamUserStats/GetPlayerAchievements/v1/`

### Parâmetros

| Parâmetro | Obrigatório | Valor no projeto | Descrição |
|---|---|---|---|
| `key` | sim | `{STEAM_API_KEY}` | chave da Web API |
| `steamid` | sim | `{STEAM_ID}` | SteamID64 do jogador |
| `appid` | sim | `{appid}` | jogo alvo |
| `l` | não | `brazilian` | idioma dos textos (quando presentes) |

### Resposta (sucesso)

```json
{
  "playerstats": {
    "steamID": "7656119...",
    "gameName": "Half-Life 2",
    "success": true,
    "achievements": [
      { "apiname": "HL2_HIT_CANCOLLECTOR", "achieved": 1, "unlocktime": 1312345678 },
      { "apiname": "HL2_KILL_ENEMIES_WITHCAR", "achieved": 0, "unlocktime": 0 }
    ]
  }
}
```

| Campo | Tipo | Uso |
|---|---|---|
| `playerstats.success` | bool | `false` ⇒ jogo sem stats |
| `playerstats.achievements[].apiname` | string | chave da conquista (junção com schema) |
| `playerstats.achievements[].achieved` | int (0/1) | obtida (1) ou pendente (0) |

### Cálculo de progresso

```
total    = len(achievements)
obtidas  = sum(a.achieved == 1)
percent  = obtidas / total * 100   # total > 0
```

### Notas / edge cases

- O campo é **`apiname`** (não `api_name`).
- Jogo sem sistema de conquistas ⇒ `playerstats.success: false` **ou** ausência
  de `achievements` ⇒ tratar como `supports_achievements=False` (não quebrar).
- Perfil privado / key inválida ⇒ `401`/`403` ⇒ `SteamDataUnavailable`.

---

## 3. ISteamUserStats/GetSchemaForGame/v2

Metadados das conquistas (nome legível, descrição, ícone). Usado **apenas** no
detalhe do jogo para enriquecer a lista; não é fonte do percentual.

**Método:** `GET /ISteamUserStats/GetSchemaForGame/v2/`

### Parâmetros

| Parâmetro | Obrigatório | Valor no projeto | Descrição |
|---|---|---|---|
| `key` | sim | `{STEAM_API_KEY}` | chave da Web API |
| `appid` | sim | `{appid}` | jogo alvo |
| `l` | não | `brazilian` | idioma de `displayName`/`description` |

### Resposta (campos usados)

```json
{
  "game": {
    "gameName": "Half-Life 2",
    "availableGameStats": {
      "achievements": [
        {
          "name": "HL2_HIT_CANCOLLECTOR",
          "displayName": "Defenestrado",
          "description": "Acertar o coletor de latas.",
          "icon": "https://media.steampowered.com/.../unlocked.jpg",
          "icongray": "https://media.steampowered.com/.../locked.jpg"
        }
      ]
    }
  }
}
```

| Campo | Tipo | Uso |
|---|---|---|
| `game.availableGameStats.achievements[].name` | string | junta com `apiname` |
| `...[].displayName` | string | nome exibido |
| `...[].description` | string | descrição (pode faltar p/ ocultas) |
| `...[].icon` | string (URL) | ícone da conquista obtida |
| `...[].icongray` | string (URL) | ícone da conquista bloqueada |

### Notas

- A junção é por `name` (schema) ↔ `apiname` (player achievements).
- `description` pode vir vazia em conquistas ocultas.
- `l=brazilian` traduz `displayName`/`description` quando há tradução; sem
  tradução, retorna o texto padrão (inglês).
- Schema é praticamente imutável ⇒ cache com TTL longo (`schema:{appid}`, 24h).

---

## 4. ISteamUserStats/GetGlobalAchievementPercentagesForApp/v2

Percentual **global** de jogadores que obteve cada conquista de um jogo — a
"raridade". Usado no detalhe para decorar cada conquista; **não** é fonte do
progresso do jogador.

> ⚠️ O parâmetro é **`gameid`**, não `appid` — diferente de todos os outros
> endpoints deste doc. Errar o nome devolve resposta vazia, não erro.

**Método:** `GET /ISteamUserStats/GetGlobalAchievementPercentagesForApp/v2/`

### Parâmetros

| Parâmetro | Obrigatório | Valor no projeto | Descrição |
|---|---|---|---|
| `gameid` | sim | `{appid}` | jogo alvo (**não** se chama `appid`) |
| `key` | não | `{STEAM_API_KEY}` | não é exigida; o app manda por reusar o `_get()` |

### Resposta (sucesso)

```json
{
  "achievementpercentages": {
    "achievements": [
      { "name": "HL2_HIT_CANCOLLECTOR", "percent": 42.7 },
      { "name": "HL2_BEAT_GAME", "percent": 4.1 }
    ]
  }
}
```

| Campo | Tipo | Uso |
|---|---|---|
| `achievementpercentages.achievements[].name` | string | junta com `apiname` (mesma chave do `GetPlayerAchievements`) |
| `...[].percent` | float | % global de jogadores que obteve a conquista |

### Notas

- A junção é por `name` ↔ `apiname`, igual à do `GetSchemaForGame`.
- Jogo sem estatísticas globais ⇒ `403` ou lista vazia. É **best-effort**: sem
  raridade a conquista continua listada — nunca derruba o detalhe.
- A raridade é **por jogo, não por jogador** ⇒ cache `global_pct:{appid}` com TTL
  longo (24h), compartilhado entre todos os visitantes.

---

## Mapa de uso no app

| Necessidade | Endpoint(s) |
|---|---|
| Index (biblioteca + playtime) | `GetOwnedGames` |
| Index ordenado por % / nº conquistas | `GetOwnedGames` + `GetPlayerAchievements` (fan-out) |
| Index ordenado por última vez jogado | `GetOwnedGames` (`rtime_last_played`, sem chamada extra) |
| Detalhe do jogo (obtidas/pendentes/% + textos) | `GetPlayerAchievements` + `GetSchemaForGame` |
| Detalhe com raridade global | + `GetGlobalAchievementPercentagesForApp` |
