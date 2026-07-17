import type { PlayerSummary } from "@/api/client";
import { cn } from "@/lib/utils";

// Avatar do perfil. Some quando a Steam não devolve imagem — o nome já identifica
// o jogador, e um placeholder quebrado não acrescenta nada.
export function Avatar({
  profile,
  className,
}: {
  profile: PlayerSummary;
  className?: string;
}) {
  if (!profile.avatar_url) return null;

  return (
    // alt="" de propósito: o nome do jogador sempre aparece em texto ao lado,
    // e repeti-lo no alt faria o leitor de tela anunciar duas vezes. Dimensões
    // fixas (avatar da Steam é 64×64) evitam reflow antes de a imagem chegar.
    <img
      src={profile.avatar_url}
      alt=""
      width={64}
      height={64}
      className={cn("rounded border border-border", className)}
    />
  );
}
