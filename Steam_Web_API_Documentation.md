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
      { "name": "TF_SCOUT_LONG_DISTANCE_RUNNER", "percent": "49.9" },
      { "name": "TF_HEAVY_DAMAGE_TAKEN", "percent": "40.3" }
    ]
  }
}
```

| Campo | Tipo | Uso |
|---|---|---|
| `achievementpercentages.achievements[].name` | string | junta com `apiname` (mesma chave do `GetPlayerAchievements`) |
| `...[].percent` | **string** | % global de jogadores que obteve a conquista |

### Notas

- ⚠️ **`percent` vem como string** (`"49.9"`), não como número — verificado no
  payload real do appid 440. O client converte para `float` na fronteira; o
  resto do app só vê número.
- A junção é por `name` ↔ `apiname`, igual à do `GetSchemaForGame`.
- Jogo sem estatísticas globais ⇒ `403` ou lista vazia. É **best-effort**: sem
  raridade a conquista continua listada — nunca derruba o detalhe.
- A raridade é **por jogo, não por jogador** ⇒ cache `global_pct:{appid}` com TTL
  longo (24h), compartilhado entre todos os visitantes.

---

## 5. ISteamUser/GetPlayerSummaries/v2

Perfil público do jogador: nome de exibição e avatar. Usado no cabeçalho da
biblioteca — e, mais importante, como **desempate de erro** (ver Notas).

**Método:** `GET /ISteamUser/GetPlayerSummaries/v2/`

### Parâmetros

| Parâmetro | Obrigatório | Valor no projeto | Descrição |
|---|---|---|---|
| `key` | sim | `{STEAM_API_KEY}` | chave da Web API |
| `steamids` | sim | `{steamid}` | **plural** — aceita lista separada por vírgula; o app manda um só |

### Resposta (campos usados)

```json
{
  "response": {
    "players": [
      {
        "steamid": "76561197960287930",
        "personaname": "Rafa",
        "avatarfull": "https://avatars.steamstatic.com/....jpg"
      }
    ]
  }
}
```

| Campo | Tipo | Uso |
|---|---|---|
| `response.players[].personaname` | string | nome de exibição |
| `response.players[].avatarfull` | string (URL) | avatar (versão grande) |

### Notas / edge cases

- ⚠️ **`players: []` só acontece com SteamID inexistente.** Perfil **privado
  continua devolvendo o player** — nome e avatar são públicos na Steam,
  independentemente da privacidade do perfil.
- É exatamente isso que torna este endpoint o **desempate de erro** do app: a
  Steam responde "biblioteca indisponível" tanto para conta inexistente quanto
  para perfil privado, e só o perfil separa os dois casos:
  - `players: []` ⇒ `SteamProfileNotFound` ⇒ **404** "Steam ID não encontrado".
  - player presente, mas biblioteca indisponível ⇒ `SteamDataUnavailable` ⇒
    **404** "o perfil pode estar privado".
- A chamada só é paga **no caminho de erro** — a biblioteca que carrega bem nunca
  a dispara.
- Conta inexistente não passa a existir: o "não" é cacheado
  (`player_summary:{steamid}`, TTL curto) para que marretar o mesmo ID inválido
  não queime a quota da chave.

---

## 6. store.steampowered.com/api/appdetails (não-oficial)

Gêneros do jogo, para a biblioteca agrupada (`?group=genre`). **Único** lugar de
onde o gênero sai: ele **não existe na Web API oficial**.

> ⚠️ **Endpoint não-oficial da loja, não da Web API.** Base URL diferente
> (`store.steampowered.com`, não `api.steampowered.com`) e **não usa a
> `STEAM_API_KEY`** — nem a exige. Por isso é a única chamada do app que **não**
> passa pelo `_get()` nem pelo token bucket: sem chave, não há quota a proteger.
> Sem contrato, sem SLA, sem versionamento — pode sumir a qualquer momento.

**Método:** `GET https://store.steampowered.com/api/appdetails`

### Parâmetros

| Parâmetro | Obrigatório | Valor no projeto | Descrição |
|---|---|---|---|
| `appids` | sim | `{appid}` | jogo alvo (**plural**, como o `steamids` do §5) |
| `filters` | não | `genres` | recorta a resposta; sem isso vem o payload inteiro da loja |
| `l` | não | `brazilian` | idioma do nome do gênero |

### Resposta (sucesso)

```json
{
  "220": {
    "success": true,
    "data": {
      "genres": [
        { "id": "1", "description": "Ação" }
      ]
    }
  }
}
```

| Campo | Tipo | Uso |
|---|---|---|
| `{appid}.success` | bool | `false` ⇒ sem dados |
| `{appid}.data.genres[].description` | string | nome do gênero (é o que a UI agrupa) |

### Notas / edge cases

- A chave do objeto raiz é o **appid como string** (`"220"`), não como int.
- ⚠️ **Jogo sem dados vem como `success: true` com `"data": []`** — uma **lista
  vazia**, não um dict. Acessar `data["genres"]` aí levanta `TypeError`. O client
  checa `isinstance(data, dict)` antes de ler.
- ⚠️ **Rate-limita agressivo, por IP** (verificado ao vivo em 2026-07-11): um
  único load de ~155 jogos com concorrência 5 rendeu ~112/155 gêneros; loads
  repetidos em poucos minutos derrubaram o IP para `429` e depois `403`. Funciona
  em uso normal (um load esporádico), mas não aguenta rajada repetida.
- Por tudo acima é **100% best-effort**: qualquer falha (429, 5xx, rede, JSON
  inválido, formato inesperado) devolve `[]` em vez de levantar. Jogo sem gênero
  cai em "Sem categoria" e a biblioteca nunca quebra.
- Cache `genres:{appid}` — por **jogo**, não por jogador: 7 dias quando encontra
  (gênero é estático), 1h quando vem vazio (o vazio pode ser o 429, não ausência
  real — não faz sentido cachear um throttle por uma semana).

---

## 7. ISteamUser/ResolveVanityURL/v1

Traduz o **nome do perfil** (a "custom URL" da Steam) para SteamID64. É o que
permite ao app aceitar `steamcommunity.com/id/gabelogannewell` — ou só
`gabelogannewell` — em vez de exigir os 17 dígitos.

**Método:** `GET /ISteamUser/ResolveVanityURL/v1/`

### Parâmetros

| Parâmetro | Obrigatório | Valor no projeto | Descrição |
|---|---|---|---|
| `key` | sim | `{STEAM_API_KEY}` | chave da Web API |
| `vanityurl` | sim | `{nome}` | **só o nome**, não a URL inteira — o app extrai o trecho depois de `/id/` antes de chamar |
| `url_type` | não | *(omitido)* | `1` = perfil individual (default), `2` = grupo, `3` = grupo oficial de jogo. O app quer o default |

### Resposta (sucesso)

```json
{
  "response": {
    "steamid": "76561197960287930",
    "success": 1
  }
}
```

### Resposta (não encontrado)

```json
{
  "response": {
    "success": 42,
    "message": "No match"
  }
}
```

| Campo | Tipo | Uso |
|---|---|---|
| `response.success` | int | `1` = achou; `42` = não existe |
| `response.steamid` | string | SteamID64 — **só vem quando `success == 1`** |

### Notas / edge cases

- ⚠️ **O fracasso vem como HTTP `200`.** Nome inexistente **não** devolve 404: a
  resposta é `200` com `success: 42` no corpo. Quem confiar no status code vai
  achar que deu certo e depois estourar num `KeyError` ao ler `steamid`. O client
  checa o `success`, não o status.
- ⚠️ **`steamid` chega como string**, não int — e é assim que o app usa (o
  `steamid` trafega como string em todo lugar). Não converter.
- O nome do perfil é **case-insensitive** na Steam, mas o app **não normaliza o
  caixa** antes de montar a chave de cache: `Rafa` e `rafa` viram duas entradas
  distintas apontando para o mesmo steamid. É desperdício de cache, não bug —
  não vale o risco de normalizar um input que a Steam trata como opaco.
- **Nem todo perfil tem nome**: quem nunca configurou a custom URL só existe em
  `/profiles/{steamid}`. Para esse usuário este endpoint nunca é chamado — a URL
  dele já **contém** os 17 dígitos, e o frontend os extrai sem tocar na rede.
- Nome inexistente não passa a existir tão cedo: o "não" é cacheado
  (`vanity:{nome}`, TTL curto), pelo mesmo motivo do `GetPlayerSummaries` —
  marretar nomes aleatórios não pode queimar a quota da chave. TTL curto, e não
  longo, porque um nome livre hoje **pode ser registrado amanhã** (ao contrário
  de um appid, que é imutável).
- O nome é **texto livre do usuário**. O app valida o formato (2–32 chars,
  `[A-Za-z0-9_-]`) **antes** de o valor virar chave de cache ou chamada à Steam:
  sem isso, uma string de 100 KB vira chave de dict.

---

## Mapa de uso no app

| Necessidade | Endpoint(s) |
|---|---|
| Resolver nome do perfil (`/id/<nome>`) → SteamID64 | `ResolveVanityURL` (só quando o input não é um SteamID64) |
| Index (biblioteca + playtime) | `GetOwnedGames` |
| Index ordenado por % / nº conquistas | `GetOwnedGames` + `GetPlayerAchievements` (fan-out) |
| Index ordenado por última vez jogado | `GetOwnedGames` (`rtime_last_played`, sem chamada extra) |
| Index agrupado por gênero | `GetOwnedGames` + `store/appdetails` (fan-out, best-effort, sem key) |
| Cabeçalho com nome e avatar do jogador | `GetPlayerSummaries` |
| Desempate de erro (conta inexistente × perfil privado) | `GetPlayerSummaries` (só no caminho de erro) |
| Detalhe do jogo (obtidas/pendentes/% + textos) | `GetPlayerAchievements` + `GetSchemaForGame` |
| Detalhe com raridade global | + `GetGlobalAchievementPercentagesForApp` |
