import { useParams, useSearchParams } from "react-router-dom";

import type { Achievement } from "@/api/client";
import { useGameDetail } from "@/api/hooks";
import { AchievementItem } from "@/components/AchievementItem";
import { Message } from "@/components/Message";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";

// Record (e não union solta): o TS cobra um rótulo por filtro, e a ordem das
// chaves é a ordem das abas.
const FILTROS = {
  all: "Todas",
  achieved: "Obtidas",
  locked: "Pendentes",
} as const;

type Filter = keyof typeof FILTROS;

const isFilter = (v: string | null): v is Filter => v != null && v in FILTROS;

// Três opções explícitas, e não uma direção derivada da aba ativa: a aba "Todas"
// não teria resposta óbvia, o mesmo controle mudaria de significado ao trocar de
// aba, e "quais pendentes são as mais raras" — pergunta legítima — ficaria
// inexprimível. Ver §7.1 da spec-design-ordenacao-derivada.
const ORDENS = {
  desbloqueio: "Desbloqueio",
  faceis: "Mais fáceis",
  raras: "Mais raras",
} as const;

type OrdemAch = keyof typeof ORDENS;

const isOrdem = (v: string | null): v is OrdemAch => v != null && v in ORDENS;

// Filtro por *tag*, e não por `searchText`: buscar o nome da conquista devolve
// zero resultado e a Steam cai calada nos guias populares do jogo — o usuário
// veria "Recommended Keyboard & Mouse Settings" achando que é sobre a conquista.
// O corpus de guias é por jogo, não por conquista: por isso este link é do jogo
// e mora aqui, não no card.
const guiasDaComunidade = (appid: number) =>
  `https://steamcommunity.com/app/${appid}/guides/?requiredtags%5B%5D=Achievements`;

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
  // Filtro na URL (e não em useState): é estado de UI compartilhável — o link
  // para "o que ainda falta neste jogo" tem de sobreviver ao refresh.
  const [params, setParams] = useSearchParams();
  const raw = params.get("filter");
  const filter: Filter = isFilter(raw) ? raw : "all";
  const rawOrdem = params.get("ordem");
  const ordem: OrdemAch = isOrdem(rawOrdem) ? rawOrdem : "desbloqueio";

  // Um atualizador só para os dois parâmetros, como a Library já faz: escrever
  // um sem reler o outro apagaria o vizinho, porque `setParams` substitui a
  // querystring inteira. Defaults omitidos para manter a URL limpa; `replace`
  // para o botão Voltar não virar um desfazer de cliques em aba.
  const update = (next: { filter?: Filter; ordem?: OrdemAch }) => {
    const f = next.filter ?? filter;
    const o = next.ordem ?? ordem;
    const p: Record<string, string> = {};
    if (f !== "all") p.filter = f;
    if (o !== "desbloqueio") p.ordem = o;
    setParams(p, { replace: true });
  };

  if (isLoading) {
    return (
      <div
        className="flex flex-col gap-3"
        aria-busy="true"
        aria-label="Carregando conquistas…"
      >
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
        {" · "}
        <a
          href={guiasDaComunidade(data.appid)}
          target="_blank"
          rel="noopener noreferrer"
          className="underline underline-offset-4 hover:text-foreground"
        >
          Guias da comunidade
        </a>
      </p>
      <Progress
        value={percent}
        segmented
        complete={percent === 100}
        className="mb-6"
      />

      <Tabs value={filter} onValueChange={(v) => update({ filter: v as Filter })}>
        <TabsList>
          {Object.entries(FILTROS).map(([value, label]) => (
            <TabsTrigger key={value} value={value}>
              {label}
            </TabsTrigger>
          ))}
        </TabsList>

        {/* Um painel por aba: é o que o aria-controls do trigger aponta. Só o
            ativo monta, então a lista não é renderizada três vezes. */}
        <TabsContent value={filter} className="flex flex-col gap-2">
          {shown.map((ach) => (
            <AchievementItem
              key={ach.apiname}
              ach={ach}
              gameName={data.name}
              steamid={steamid}
              // `data.appid` e não o `appid` do useParams: aquele é string.
              // Mesma fonte que o link de guias acima usa.
              appid={data.appid}
            />
          ))}
        </TabsContent>
      </Tabs>
    </div>
  );
}
