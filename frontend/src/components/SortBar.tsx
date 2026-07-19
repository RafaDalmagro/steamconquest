import { Button } from "@/components/ui/button";

// Ordenar é assunto da UI, não da API: a ordem sai de campos que já vêm no
// payload, e quem reordena é o cliente. Por isso o vocabulário nasce aqui (como o
// `Group`) e não do OpenAPI — o backend não tem opinião sobre ordem.
export type Sort =
  | "playtime"
  | "name"
  | "percent"
  | "quase_la"
  | "ach_count"
  | "last_played";

// Record (e não array) de propósito: o TS cobra uma chave para cada `Sort`, então
// um sort novo vira erro de compilação em quem precisa tratá-lo (aqui e nos
// comparadores da Library), não um botão que faltou. A ordem dos botões é a ordem
// de declaração das chaves.
const ROTULOS: Record<Sort, string> = {
  playtime: "Tempo de jogo",
  name: "Nome",
  percent: "% concluído",
  quase_la: "Quase lá",
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
