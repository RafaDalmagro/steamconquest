import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { formatarData, formatarPercentual } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { Achievement } from "@/api/client";

// Abaixo disso a conquista é "rara". Limiar de produto, não da Steam — ela só
// devolve o número.
const RARA_ATE = 10;

export function AchievementItem({ ach }: { ach: Achievement }) {
  const raridade = ach.global_percent;

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
              Obtida em {formatarData(ach.unlocked_at)}
            </time>
          )}
          {raridade != null && (
            <small className="text-muted-foreground tabular-nums">
              {formatarPercentual(raridade)}% dos jogadores
            </small>
          )}
        </span>
        <span className="ml-auto flex flex-none items-center gap-1.5">
          {raridade != null && raridade < RARA_ATE && (
            <Badge variant="rare">Rara</Badge>
          )}
          <Badge variant={ach.achieved ? "achieved" : "locked"}>
            {ach.achieved ? "Obtida" : "Pendente"}
          </Badge>
        </span>
      </CardContent>
    </Card>
  );
}
