import { useState } from "react";
import { useParams } from "react-router-dom";

import type { Achievement } from "@/api/client";
import { useGameDetail } from "@/api/hooks";
import { AchievementItem } from "@/components/AchievementItem";
import { Message } from "@/components/Message";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

type Filter = "all" | "achieved" | "locked";

// Sem data → 0, que é menor que qualquer epoch real e mantém o comparador
// numérico (Date.parse("") daria NaN, e NaN empata tudo silenciosamente).
const quando = (ach: Achievement) =>
  ach.unlocked_at ? Date.parse(ach.unlocked_at) : 0;

// Obtidas primeiro (mais recente → mais antiga), depois as obtidas sem data
// (unlocktime 0 da Steam), e por fim as pendentes. Array.sort é estável, então
// pendentes e sem-data mantêm a ordem do schema sem precisar de critério extra.
const porDesbloqueio = (a: Achievement, b: Achievement) =>
  Number(b.achieved) - Number(a.achieved) || quando(b) - quando(a);

export function GameDetail() {
  const { steamid = "", appid } = useParams();
  const id = Number(appid);
  const { data, isLoading, isError, error } = useGameDetail(steamid, id);
  const [filter, setFilter] = useState<Filter>("all");

  if (isLoading) {
    return (
      <div className="flex flex-col gap-3">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-4 w-40" />
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-14 w-full" />
        ))}
      </div>
    );
  }

  if (isError)
    return <Message role="alert">{(error as Error).message}</Message>;
  if (!data) return null;

  if (!data.supports_achievements) {
    return (
      <div>
        <h1 className="mb-4 text-2xl font-semibold uppercase tracking-wide">
          {data.name}
        </h1>
        <Message>Este jogo não possui conquistas.</Message>
      </div>
    );
  }

  const shown = data.achievements
    .filter((a) =>
      filter === "all" ? true : filter === "achieved" ? a.achieved : !a.achieved,
    )
    .sort(porDesbloqueio);
  const percent = Math.round(data.percent);

  return (
    <div>
      <h1 className="mb-1 text-2xl font-semibold uppercase tracking-wide">
        {data.name}
      </h1>
      <p className="mb-2 text-muted-foreground tabular-nums">
        {data.achieved_count} de {data.total_count} conquistas · {percent}%
      </p>
      <Progress
        value={percent}
        segmented
        complete={percent === 100}
        className="mb-6"
      />

      <Tabs value={filter} onValueChange={(v) => setFilter(v as Filter)}>
        <TabsList>
          <TabsTrigger value="all">Todas</TabsTrigger>
          <TabsTrigger value="achieved">Obtidas</TabsTrigger>
          <TabsTrigger value="locked">Pendentes</TabsTrigger>
        </TabsList>
      </Tabs>

      <div className="mt-4 flex flex-col gap-2">
        {shown.map((ach) => (
          <AchievementItem key={ach.apiname} ach={ach} />
        ))}
      </div>
    </div>
  );
}
