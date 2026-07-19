import { useId, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { formatarData, formatarPercentual } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { Achievement } from "@/api/client";
import { useDica } from "@/api/hooks";

// Abaixo disso a conquista é "rara". Limiar de produto, não da Steam — ela só
// devolve o número.
const RARA_ATE = 10;

// URL inválida não pode derrubar o painel: a string vem do provedor de IA, não
// de um contrato nosso. Cai para a URL crua, que ainda é informação.
const dominioDe = (url: string) => {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
};

// A busca vai em inglês de propósito: guia e vídeo de conquista são escritos em
// inglês, e o `display_name` que o card mostra é pt-BR — textos diferentes, não
// traduções ("Descanso no Spa" × "Spa Healer").
const buscaDeVideo = (jogo: string, nomeEn: string) =>
  `https://www.youtube.com/results?search_query=${encodeURIComponent(
    `${jogo} ${nomeEn} achievement`,
  )}`;

export function AchievementItem({
  ach,
  gameName,
  steamid,
  appid,
}: {
  ach: Achievement;
  gameName: string;
  steamid: string;
  appid: number;
}) {
  const raridade = ach.global_percent;
  // Estado local, não global: a dica é pedida por conquista, e o clique de uma
  // não pode disparar as outras ~90 da aba.
  const [pediuDica, setPediuDica] = useState(false);
  const painelId = useId();
  const dica = useDica(steamid, appid, ach.apiname, pediuDica);
  // Mesma regra do link de vídeo: sem `name_en` não há o que buscar.
  const podePedirDica = !ach.achieved && ach.name_en;

  return (
    // Pendente é dessaturada, não apagada: `opacity-50` no card inteiro levava o
    // texto muted a ~2.6:1 de contraste. A dessaturação fica no ícone (decorativo)
    // e o selo "Pendente" carrega o estado — o texto continua legível.
    <Card className="[content-visibility:auto] [contain-intrinsic-size:auto_64px]">
      {/* `flex-wrap` local, não no CardContent compartilhado: o painel da dica é
          `basis-full` e precisa quebrar para a própria linha. Sem isto ele vira
          um terceiro item da mesma linha e o `items-center` espreme o ícone e o
          título numa coluna estreita — pego no /verify. */}
      <CardContent className="flex-wrap">
        {ach.icon_url && (
          <img
            src={ach.icon_url}
            alt=""
            width={32}
            height={32}
            loading="lazy"
            className={cn(
              "size-8 flex-none rounded",
              !ach.achieved && "opacity-60 grayscale",
            )}
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
          {/* Só na pendente, e só com nome buscável: sem `name_en` o link
              buscaria o `apiname` e não acharia nada — link que não acha nada é
              pior que link nenhum. */}
          {!ach.achieved && ach.name_en && (
            <a
              href={buscaDeVideo(gameName, ach.name_en)}
              target="_blank"
              // Sem noopener a página aberta ganha window.opener e pode
              // redirecionar esta aba. Boundary de segurança, não estilo.
              rel="noopener noreferrer"
              className="text-xs text-muted-foreground underline underline-offset-4 hover:text-foreground"
            >
              Como conseguir
            </a>
          )}
          {/* Ao lado do link, não no lugar dele: o YouTube é o caminho de custo
              zero e infalível. Se a IA cair, a conquista não pode voltar a não
              dizer *como* (REQ-121). */}
          {podePedirDica && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setPediuDica((aberto) => !aberto)}
              aria-expanded={pediuDica}
              // `aria-expanded` sozinho anuncia o estado mas não leva ao
              // conteúdo. O par com o `id` do painel é o que fecha isso.
              aria-controls={painelId}
              className="text-xs"
            >
              {pediuDica ? "Dispensar" : "Chamar o NPC"}
            </Button>
          )}
          {raridade != null && raridade < RARA_ATE && (
            <Badge variant="rare">Rara</Badge>
          )}
          <Badge variant={ach.achieved ? "achieved" : "locked"}>
            {ach.achieved ? "Obtida" : "Pendente"}
          </Badge>
        </span>
        {pediuDica && (
          // Superfície *recuada* (bg-background é mais escura que o card), e não
          // elevada. Não é gosto: sobre `bg-accent`, o muted-foreground cai para
          // 4.30:1 e reprova o AA. Aqui sobe para 5.06:1, e o foreground vai a
          // 13.76:1. A borda esquerda em primary marca a procedência — este é o
          // único bloco do card que não é dado factual da Steam.
          <div
            id={painelId}
            aria-busy={dica.isPending}
            className="mt-1 basis-full rounded-md border-l-2 border-primary bg-background px-3 py-2.5 text-sm"
          >
            {/* Nome e natureza na MESMA linha, para serem lidos juntos. "NPC"
                sozinho seria charmoso e opaco; "modelo de IA" ao lado é o que
                mantém a confiança condicional — a Fonte só existe porque o
                modelo pode errar. Persona é camada de apresentação: no domínio
                o conceito continua sendo Dica (ver CONTEXT.md). */}
            <p className="text-xs text-muted-foreground">
              {/* Glifo, não ícone: o app fala por glifos (▌CONQUISTAS_ no
                  Header, ✦ no GameCard). lucide-react está instalado mas nunca
                  foi importado — trazê-lo aqui quebraria a estética de terminal
                  por um único ornamento. `aria-hidden` porque leitor de tela
                  soletra o caractere sem acrescentar nada. */}
              <span aria-hidden="true">▌ </span>
              <strong className="font-display uppercase tracking-widest text-foreground">
                NPC
              </strong>
              {" · modelo de IA"}
            </p>

            {dica.isPending && (
              <div className="mt-2 space-y-2">
                {/* Texto antes do shimmer: 25s de shimmer puro lê como travado.
                    Skeleton comunica "quase lá", e esta espera não é. */}
                <p className="text-muted-foreground">
                  O NPC está vasculhando a web…
                </p>
                <Skeleton className="h-3 w-full" />
                <Skeleton className="h-3 w-11/12" />
                <Skeleton className="h-3 w-3/4" />
              </div>
            )}

            {dica.isError && (
              <p className="mt-2 text-muted-foreground">
                {dica.error.message} O link “Como conseguir” continua valendo.
              </p>
            )}

            {dica.data && (
              <>
                {/* ponytail: `whitespace-pre-line` preserva os passos numerados
                    que o modelo devolve. Parsear em <ol> daria ritmo melhor, mas
                    é lógica frágil sobre saída de LLM — upgrade só se a saída se
                    provar consistente. max-w-prose porque a largura do card dá
                    ~150 chars por linha, o dobro do legível. */}
                <p className="mt-2 max-w-prose whitespace-pre-line leading-relaxed">
                  {dica.data.texto}
                </p>

                {dica.data.fontes.length > 0 && (
                  <>
                    {/* Legenda da lista, não aviso solto: a frase passa a
                        introduzir as fontes, que é o papel que ela sempre quis
                        ter. Sem `mb`, o `mt-1.5` da <ul> encosta as duas. */}
                    <p className="mt-3 text-xs text-muted-foreground">
                      O NPC pode errar. Confira nas fontes:
                    </p>
                    <ul className="mt-1.5 space-y-0.5">
                      {dica.data.fontes.map((f) => (
                        <li key={f.url}>
                          <a
                            href={f.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            // py-2 e não py-1: medido, o alvo tinha 24px de
                            // altura. Não chega aos 44px da diretriz de toque
                            // (9 fontes × 44px empurrariam a lista pra baixo
                            // demais), mas 32px é o meio-termo — e o alvo é
                            // largo, ocupa a linha inteira.
                            className="flex gap-2 rounded-sm py-2 text-xs hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                          >
                            {/* Domínio primeiro: "steamcommunity.com" diz mais
                                sobre confiabilidade que um título truncado. */}
                            <span className="w-40 flex-none truncate text-muted-foreground">
                              {dominioDe(f.url)}
                            </span>
                            <span className="truncate text-foreground">
                              {f.title}
                            </span>
                          </a>
                        </li>
                      ))}
                    </ul>
                  </>
                )}
              </>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
