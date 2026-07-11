import { Button } from "@/components/ui/button";
import type { Group } from "@/api/client";

export const GROUPS: { value: Group; label: string }[] = [
  { value: "none", label: "Nenhum" },
  { value: "genre", label: "Gênero" },
];

export function GroupBar({
  value,
  onChange,
}: {
  value: Group;
  onChange: (group: Group) => void;
}) {
  return (
    <div className="mb-6 flex flex-wrap items-center gap-2">
      <span className="font-display text-xs uppercase tracking-widest text-muted-foreground">
        Agrupar por:
      </span>
      {GROUPS.map((g) => (
        <Button
          key={g.value}
          size="sm"
          variant={value === g.value ? "active" : "default"}
          aria-pressed={value === g.value}
          onClick={() => onChange(g.value)}
          className="font-display text-xs uppercase tracking-wide"
        >
          {g.label}
        </Button>
      ))}
    </div>
  );
}
