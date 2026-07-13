import { Button } from "@/components/ui/button";
import type { Sort } from "@/api/client";

// Record (e não array) de propósito: o TS cobra uma chave para cada `Sort`, então
// um sort novo no backend vira erro de compilação aqui, não um botão que faltou.
// A ordem dos botões é a ordem de declaração das chaves.
const ROTULOS: Record<Sort, string> = {
  playtime: "Tempo de jogo",
  name: "Nome",
  percent: "% concluído",
  ach_count: "Nº de conquistas",
  last_played: "Última vez jogado",
};

export const SORTS = Object.entries(ROTULOS) as [Sort, string][];

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
      {SORTS.map(([sort, label]) => (
        <Button
          key={sort}
          size="sm"
          variant={value === sort ? "active" : "default"}
          aria-pressed={value === sort}
          onClick={() => onChange(sort)}
          className="font-display text-xs uppercase tracking-wide"
        >
          {label}
        </Button>
      ))}
    </div>
  );
}
