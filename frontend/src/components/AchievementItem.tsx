import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { Achievement } from "@/api/client";

// Intl é nativo: nenhuma lib de data para formatar uma linha.
const DATA = new Intl.DateTimeFormat("pt-BR", { dateStyle: "short" });

export function AchievementItem({ ach }: { ach: Achievement }) {
  return (
    <Card className={cn(!ach.achieved && "opacity-50")}>
      <CardContent>
        {ach.icon_url && (
          <img
            src={ach.icon_url}
            alt=""
            width={32}
            height={32}
            loading="lazy"
            className="size-8 flex-none rounded"
          />
        )}
        <span className="flex flex-col">
          <strong className="font-display font-semibold">
            {ach.display_name}
          </strong>
          {ach.description && (
            <small className="text-muted-foreground">{ach.description}</small>
          )}
          {ach.unlocked_at && (
            <time
              dateTime={ach.unlocked_at}
              className="text-xs text-muted-foreground tabular-nums"
            >
              Obtida em {DATA.format(new Date(ach.unlocked_at))}
            </time>
          )}
        </span>
        <Badge
          variant={ach.achieved ? "achieved" : "locked"}
          className="ml-auto flex-none"
        >
          {ach.achieved ? "Obtida" : "Pendente"}
        </Badge>
      </CardContent>
    </Card>
  );
}
