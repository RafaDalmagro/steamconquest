import { useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";

import { useGames, usePlayerSummary } from "@/api/hooks";
import type { Game, Group, Sort } from "@/api/client";
import { Avatar } from "@/components/Avatar";
import { GameCard } from "@/components/GameCard";
import { GROUPS, GroupBar } from "@/components/GroupBar";
import { Message } from "@/components/Message";
import { SORTS, SortBar } from "@/components/SortBar";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { isQuaseLa } from "@/lib/progress";

const GRID = "grid grid-cols-[repeat(auto-fill,minmax(220px,1fr))] gap-4";
const SEM_CATEGORIA = "Sem categoria";

const HORAS = new Intl.NumberFormat("pt-BR", {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});

const plural = (n: number, singular: string) =>
  `${n} ${singular}${n === 1 ? "" : "s"}`;

// Agrega o que está em tela (já filtrado pela busca): nada de chamada extra.
function resumo(games: Game[]): string {
  const horas = games.reduce((t, g) => t + g.playtime_minutes, 0) / 60;
  const partes = [plural(games.length, "jogo"), `${HORAS.format(horas)} h`];
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

// Particiona por gênero primário (genres[0]); jogos sem gênero vão para "Sem
// categoria", sempre por último. Mantém a ordem vinda do servidor dentro do grupo.
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

  const { data, isLoading, isError, error } = useGames(steamid, sort, group);
  // Best-effort: perfil indisponível apenas mantém o título genérico.
  const { data: profile } = usePlayerSummary(steamid);

  // Busca client-side sobre a lista já carregada — nenhuma chamada ao servidor.
  // Fica em useState (e não na URL como sort/group): é estado efêmero de
  // digitação, não vale sujar a URL a cada tecla.
  const [busca, setBusca] = useState("");
  const termo = busca.trim().toLowerCase();
  // Sem debounce nem useMemo: filtrar a biblioteca em memória é sub-milissegundo.
  const jogos = data?.filter((g) => g.name.toLowerCase().includes(termo));

  // Mantém sort e group juntos na URL; omite os valores default para URLs limpas.
  const update = (next: { sort?: Sort; group?: Group }) => {
    const s = next.sort ?? sort;
    const g = next.group ?? group;
    const p: Record<string, string> = {};
    if (s !== "playtime") p.sort = s;
    if (g !== "none") p.group = g;
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
          value={busca}
          onChange={(e) => setBusca(e.target.value)}
          placeholder="Buscar por nome…"
          aria-label="Buscar jogo por nome"
          className="mb-4 max-w-sm"
        />
      )}

      <SortBar value={sort} onChange={(s) => update({ sort: s })} />
      <GroupBar value={group} onChange={(g) => update({ group: g })} />

      {isLoading && (
        <div className={GRID}>
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
