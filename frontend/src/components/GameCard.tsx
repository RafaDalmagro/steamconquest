import { useState } from "react";
import { Link } from "react-router-dom";

import { Card } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { formatarData, formatarHoras } from "@/lib/format";
import { isQuaseLa } from "@/lib/progress";
import type { Game } from "@/api/client";

// Mesma CDN pública de assets já usada pelo icon_url — não envolve a API key.
const coverUrl = (appid: number) =>
  `https://cdn.cloudflare.steamstatic.com/steam/apps/${appid}/header.jpg`;

export function GameCard({ steamid, game }: { steamid: string; game: Game }) {
  const [coverFailed, setCoverFailed] = useState(false);
  const hours = formatarHoras(game.playtime_minutes);
  const percent = game.percent != null ? Math.round(game.percent) : null;
  const complete = percent === 100;

  return (
    // `content-visibility: auto` pula o render do que está fora da viewport —
    // é a virtualização nativa, sem lib e sem altura fixa. `contain-intrinsic-size`
    // reserva a altura estimada do card para a barra de rolagem não pular.
    <Link
      to={`/u/${steamid}/game/${game.appid}`}
      className="group block [content-visibility:auto] [contain-intrinsic-size:auto_260px]"
    >
      <Card className="overflow-hidden p-0 transition-[transform,border-color,box-shadow] duration-150 group-hover:-translate-y-0.5 group-hover:border-primary group-hover:shadow-[0_0_12px_rgb(247_37_133/0.35)] motion-reduce:group-hover:translate-y-0">
        <div className="relative aspect-[460/215] bg-accent">
          {!coverFailed ? (
            <img
              src={coverUrl(game.appid)}
              alt=""
              width={460}
              height={215}
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
          {game.playtime_2weeks_minutes != null && (
            // `title` não chega a teclado nem a toque: as horas vão em texto
            // acessível, e o selo visual continua só "Recente".
            <span className="absolute left-1.5 top-1.5 rounded-sm bg-primary px-1.5 py-0.5 font-display text-xs font-semibold text-primary-foreground">
              Recente
              <span className="sr-only">
                : {formatarHoras(game.playtime_2weeks_minutes)} h nas últimas 2
                semanas
              </span>
            </span>
          )}
          {complete && (
            <span className="absolute right-1.5 top-1.5 rounded-sm bg-achieved px-1.5 py-0.5 font-display text-xs font-semibold text-achieved-foreground">
              ✦ 100%
            </span>
          )}
          {isQuaseLa(game.percent) && (
            <span className="absolute right-1.5 top-1.5 rounded-sm border border-achieved bg-background/70 px-1.5 py-0.5 font-display text-xs font-semibold text-achieved">
              Quase lá
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
          {game.last_played_at && (
            <time
              dateTime={game.last_played_at}
              className="text-xs text-muted-foreground tabular-nums"
            >
              Jogado em {formatarData(game.last_played_at)}
            </time>
          )}
          {percent != null && (
            <Progress
              value={percent}
              segmented
              complete={complete}
              aria-label={`${percent}% das conquistas de ${game.name}`}
            />
          )}
        </div>
      </Card>
    </Link>
  );
}
