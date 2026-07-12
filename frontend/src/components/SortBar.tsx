import { Button } from "@/components/ui/button";
import type { Sort } from "@/api/client";

export const SORTS: { value: Sort; label: string }[] = [
  { value: "playtime", label: "Tempo de jogo" },
  { value: "name", label: "Nome" },
  { value: "percent", label: "% concluído" },
  { value: "ach_count", label: "Nº de conquistas" },
  { value: "last_played", label: "Última vez jogado" },
];

export function SortBar({
  value,
  onChange,
}: {
  value: Sort;
  onChange: (sort: Sort) => void;
}) {
  return (
    <div className="mb-6 flex flex-wrap items-center gap-2">
      <span className="font-display text-xs uppercase tracking-widest text-muted-foreground">
        Ordenar:
      </span>
      {SORTS.map((s) => (
        <Button
          key={s.value}
          size="sm"
          variant={value === s.value ? "active" : "default"}
          aria-pressed={value === s.value}
          onClick={() => onChange(s.value)}
          className="font-display text-xs uppercase tracking-wide"
        >
          {s.label}
        </Button>
      ))}
    </div>
  );
}
