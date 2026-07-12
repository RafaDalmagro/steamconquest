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
    <img
      src={profile.avatar_url}
      alt={profile.personaname}
      className={cn("rounded border border-border", className)}
    />
  );
}
