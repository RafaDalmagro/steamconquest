import { useState } from "react";
import { Link } from "react-router-dom";

import { Card } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import type { Game } from "@/api/client";

// Mesma CDN pública de assets já usada pelo icon_url — não envolve a API key.
const coverUrl = (appid: number) =>
  `https://cdn.cloudflare.steamstatic.com/steam/apps/${appid}/header.jpg`;

export function GameCard({ steamid, game }: { steamid: string; game: Game }) {
  const [coverFailed, setCoverFailed] = useState(false);
  const hours = (game.playtime_minutes / 60).toFixed(1);
  const percent = game.percent != null ? Math.round(game.percent) : null;
  const complete = percent === 100;

  return (
    <Link to={`/u/${steamid}/game/${game.appid}`} className="group block">
      <Card className="overflow-hidden p-0 transition-all duration-150 group-hover:-translate-y-0.5 group-hover:border-primary group-hover:shadow-[0_0_12px_rgb(247_37_133/0.35)]">
        <div className="relative aspect-[460/215] bg-accent">
          {!coverFailed ? (
            <img
              src={coverUrl(game.appid)}
              alt=""
              loading="lazy"
              onError={() => setCoverFailed(true)}
              className="h-full w-full object-cover"
            />
          ) : (
            <div className="flex h-full w-full items-center justify-center">
              {game.icon_url && (
                <img
                  src={game.icon_url}
                  alt=""
                  width={32}
                  height={32}
                  loading="lazy"
                  className="size-8 rounded"
                />
              )}
            </div>
          )}
          {complete && (
            <span className="absolute right-1.5 top-1.5 rounded-sm bg-achieved px-1.5 py-0.5 font-display text-xs font-semibold text-achieved-foreground">
              ✦ 100%
            </span>
          )}
        </div>

        <div className="flex flex-col gap-2 p-3">
          <h3 className="truncate font-display font-semibold tracking-wide">
            {game.name}
          </h3>
          <div className="flex items-baseline justify-between text-sm text-muted-foreground tabular-nums">
            <span>{hours} h</span>
            {percent != null && (
              <span>
                {game.achieved_count}/{game.total_count}
              </span>
            )}
          </div>
          {percent != null && (
            <Progress value={percent} segmented complete={complete} />
          )}
        </div>
      </Card>
    </Link>
  );
}
