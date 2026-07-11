import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { Achievement } from "@/api/client";

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
