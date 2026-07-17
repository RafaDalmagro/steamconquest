import { useParams, useSearchParams } from "react-router-dom";

import { useGames, usePlayerSummary } from "@/api/hooks";
import { includesFor, type Game, type Group } from "@/api/client";
import { Avatar } from "@/components/Avatar";
import { GameCard } from "@/components/GameCard";
import { GROUPS, GroupBar } from "@/components/GroupBar";
import { Message } from "@/components/Message";
import { SORTS, SortBar, type Sort } from "@/components/SortBar";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { formatarHoras } from "@/lib/format";
import { isQuaseLa } from "@/lib/progress";

const GRID = "grid grid-cols-[repeat(auto-fill,minmax(220px,1fr))] gap-4";
const SEM_CATEGORIA = "Sem categoria";

const plural = (n: number, singular: string) =>
  `${n} ${singular}${n === 1 ? "" : "s"}`;

// Agrega o que está em tela (já filtrado pela busca): nada de chamada extra.
function resumo(games: Game[]): string {
  const minutos = games.reduce((t, g) => t + g.playtime_minutes, 0);
  const partes = [plural(games.length, "jogo"), `${formatarHoras(minutos)} h`];
  // Gatilho é a presença do percentual, não o valor do sort: `ach_count`
  // também preenche as conquistas, e amarrar em `sort === "percent"` erraria lá.
  if (games.some((g) => g.percent != null)) {
    const quase = games.filter((g) => isQuaseLa(g.percent)).length;
    if (quase > 0) partes.push(`${plural(quase, "jogo")} quase 100%`);
    const perfeitos = games.filter((g) => g.percent === 100).length;
    partes.push(`${plural(perfeitos, "jogo")} 100%`);
  }
  return partes.join(" · ");
}

// Ordenar não precisa do servidor: os campos já estão todos aqui. Ausentes viram
// 0 — nunca jogado e sem conquista caem no fim, e dois ausentes empatam, o que o
// sort estável do JS resolve preservando a ordem que a Steam devolveu.
const quando = (g: Game) => (g.last_played_at ? Date.parse(g.last_played_at) : 0);

// Collator instanciado uma vez, não por comparação: `a.name.localeCompare(b.name)`
// remonta a tabela de collation do ICU a cada par e quase dobra o custo do sort
// (medido em ~4.6k jogos: 13ms → 7ms), com resultado idêntico.
const collator = new Intl.Collator("pt-BR");

const COMPARADORES: Record<Sort, (a: Game, b: Game) => number> = {
  playtime: (a, b) => b.playtime_minutes - a.playtime_minutes,
  name: (a, b) => collator.compare(a.name, b.name),
  percent: (a, b) => (b.percent ?? 0) - (a.percent ?? 0),
  ach_count: (a, b) => (b.achieved_count ?? 0) - (a.achieved_count ?? 0),
  last_played: (a, b) => quando(b) - quando(a),
};

// Particiona por gênero primário (genres[0]); jogos sem gênero vão para "Sem
// categoria", sempre por último. Mantém a ordem já definida dentro do grupo.
function byGenre(games: Game[]): [string, Game[]][] {
  const buckets = new Map<string, Game[]>();
  for (const game of games) {
    const key = game.genres[0] ?? SEM_CATEGORIA;
    (buckets.get(key) ?? buckets.set(key, []).get(key)!).push(game);
  }
  return [...buckets.entries()].sort(([a], [b]) =>
    a === SEM_CATEGORIA ? 1 : b === SEM_CATEGORIA ? -1 : a.localeCompare(b),
  );
}

export function Library() {
  const { steamid = "" } = useParams();
  const [params, setParams] = useSearchParams();

  const rawSort = params.get("sort");
  const sort: Sort = SORTS.some(([s]) => s === rawSort)
    ? (rawSort as Sort)
    : "playtime";
  const rawGroup = params.get("group");
  const group: Group = GROUPS.some((g) => g.value === rawGroup)
    ? (rawGroup as Group)
    : "none";

  const { data, isLoading, isError, error } = useGames(
    steamid,
    includesFor(sort, group),
  );
  // Best-effort: perfil indisponível apenas mantém o título genérico.
  const { data: profile } = usePlayerSummary(steamid);

  // Busca client-side sobre a lista já carregada — nenhuma chamada ao servidor.
  // Mora na URL junto de sort/group: é filtro, e filtro tem de ser
  // compartilhável e sobreviver ao refresh. `replace: true` em todos eles
  // impede que digitar empilhe uma entrada de histórico por tecla.
  const busca = params.get("q") ?? "";
  const termo = busca.trim().toLowerCase();
  // Roda a cada render, sem debounce nem useMemo: numa biblioteca de ~4.6k jogos
  // (a maior que apareceu no teste real) o par filtrar+ordenar custa ~7ms no pior
  // caso — por nome, sem busca — e ~6ms por tecla digitada, que já filtra antes de
  // ordenar. Fica dentro do frame; memoizar aqui custaria mais em ruído do que
  // devolve. Se um dia a lista for paginada, isto muda: ordenar client-side só é
  // correto porque a biblioteca inteira vem de uma vez.
  //
  // O `.sort()` (in-place) só é seguro porque o `.filter()` acima já devolveu um
  // array novo — `data` é o objeto do cache do React Query, compartilhado entre
  // renders, e ordená-lo direto o corromperia.
  const jogos = data
    ?.filter((g) => g.name.toLowerCase().includes(termo))
    .sort(COMPARADORES[sort]);

  // Mantém sort, group e busca juntos na URL; omite os defaults para URLs limpas.
  const update = (next: { sort?: Sort; group?: Group; q?: string }) => {
    const s = next.sort ?? sort;
    const g = next.group ?? group;
    const q = next.q ?? busca;
    const p: Record<string, string> = {};
    if (s !== "playtime") p.sort = s;
    if (g !== "none") p.group = g;
    if (q) p.q = q;
    setParams(p, { replace: true });
  };

  return (
    <div>
      <div className="mb-4 flex items-center gap-3">
        {profile && <Avatar profile={profile} className="size-11" />}
        <div>
          <h1 className="text-2xl font-semibold uppercase tracking-wide">
            {profile?.personaname
              ? `Biblioteca de ${profile.personaname}`
              : "Biblioteca"}
          </h1>
          {jogos && (
            <span className="text-sm font-medium tracking-widest text-muted-foreground tabular-nums">
              {resumo(jogos)}
            </span>
          )}
        </div>
      </div>

      {data && (
        <Input
          type="search"
          name="q"
          value={busca}
          onChange={(e) => update({ q: e.target.value })}
          placeholder="Buscar por nome…"
          aria-label="Buscar jogo por nome"
          autoComplete="off"
          spellCheck={false}
          className="mb-4 max-w-sm"
        />
      )}

      <SortBar value={sort} onChange={(s) => update({ sort: s })} />
      <GroupBar value={group} onChange={(g) => update({ group: g })} />

      {isLoading && (
        <div className={GRID} aria-busy="true" aria-label="Carregando biblioteca…">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="aspect-[460/215] w-full" />
          ))}
        </div>
      )}

      {isError && <Message role="alert">{(error as Error).message}</Message>}

      {jogos?.length === 0 && <Message>Nenhum jogo encontrado.</Message>}

      {jogos && group === "genre" && (
        <div className="space-y-8">
          {byGenre(jogos).map(([genre, games]) => (
            <section key={genre}>
              <h2 className="mb-3 flex items-baseline gap-2 font-display text-sm uppercase tracking-widest text-muted-foreground">
                {genre}
                <span className="tabular-nums">{games.length}</span>
              </h2>
              <div className={GRID}>
                {games.map((game) => (
                  <GameCard key={game.appid} steamid={steamid} game={game} />
                ))}
              </div>
            </section>
          ))}
        </div>
      )}

      {jogos && group !== "genre" && (
        <div className={GRID}>
          {jogos.map((game) => (
            <GameCard key={game.appid} steamid={steamid} game={game} />
          ))}
        </div>
      )}
    </div>
  );
}
