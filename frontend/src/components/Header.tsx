import type { ReactNode } from "react";
import { Link, useMatch } from "react-router-dom";

import { useGameDetail } from "@/api/hooks";

// Último crumb do detalhe: reusa a mesma query do GameDetail (queryKey
// ["game", steamid, appid]) — o React Query deduplica, sem request extra.
function GameCrumb({ steamid, appid }: { steamid: string; appid: number }) {
  const { data } = useGameDetail(steamid, appid);
  return <>{data?.name ?? "…"}</>;
}

export function Header() {
  const libMatch = useMatch("/u/:steamid");
  const gameMatch = useMatch("/u/:steamid/game/:appid");
  const steamid = gameMatch?.params.steamid ?? libMatch?.params.steamid;
  const appid = gameMatch?.params.appid;

  // Trilha cresce com a profundidade da rota; o steamid é preservado nos links.
  const crumbs: { label: ReactNode; to?: string }[] = [
    { label: "Início", to: "/" },
  ];
  if (steamid) crumbs.push({ label: "Biblioteca", to: `/u/${steamid}` });
  if (steamid && appid) {
    crumbs.push({
      label: <GameCrumb steamid={steamid} appid={Number(appid)} />,
    });
  }

  return (
    <header className="flex items-center gap-6 border-b border-border bg-header px-6 py-4">
      <Link
        to="/"
        aria-label="Conquistas — página inicial"
        className="font-display font-semibold tracking-widest text-primary hover:underline"
      >
        ▌CONQUISTAS_
      </Link>
      <nav aria-label="Trilha de navegação">
        <ol className="flex flex-wrap items-center gap-2 text-sm">
          {crumbs.map((crumb, i) => {
            const isCurrent = i === crumbs.length - 1;
            return (
              <li key={i} className="flex items-center gap-2">
                {i > 0 && (
                  <span aria-hidden="true" className="text-muted-foreground">
                    ›
                  </span>
                )}
                {isCurrent || !crumb.to ? (
                  <span aria-current="page" className="text-foreground">
                    {crumb.label}
                  </span>
                ) : (
                  <Link
                    to={crumb.to}
                    className="text-muted-foreground hover:text-foreground hover:underline"
                  >
                    {crumb.label}
                  </Link>
                )}
              </li>
            );
          })}
        </ol>
      </nav>
    </header>
  );
}
