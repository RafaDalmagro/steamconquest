import { keepPreviousData, useQuery } from "@tanstack/react-query";

import {
  fetchGameDetail,
  fetchGames,
  fetchPlayerSummary,
  fetchResolvedSteamId,
  type Include,
} from "./client";
import { isSteamId64 } from "@/lib/steamid";

// `enabled` aqui não é a mensagem de erro — quem a mostra é o guard de rota em
// App.tsx. É o que impede DISPARAR request com id malformado, e precisa morar no
// hook porque o Header (trilha de navegação) vive fora do <Routes> e também
// consome estes hooks. O appid mal formado fica de fora de propósito: o 422 do
// backend já devolve mensagem legível, e assim não há tela em branco.

// A chave é o `include`, não o filtro: reordenar ou buscar por nome não muda o
// dado, então não pode custar uma requisição. Só pedir algo que ainda não chegou
// (conquistas, gênero) justifica uma entrada nova de cache — e são no máximo 4.
export function useGames(steamid: string, include: Include[]) {
  return useQuery({
    queryKey: ["games", steamid, include],
    queryFn: () => fetchGames(steamid, include),
    enabled: isSteamId64(steamid),
    // Quando a chave muda é porque pedimos um dado *a mais*: a lista atual segue
    // válida, então fica em tela (com os campos novos vazios) enquanto o refetch
    // corre em background. Sem isto, pedir o % trocaria a biblioteca por skeleton.
    placeholderData: keepPreviousData,
  });
}

// Options soltas (não só o hook): o Home as usa via queryClient.fetchQuery para
// validar o id antes de navegar, e a Library reaproveita o mesmo cache depois.
export const playerSummaryQuery = (steamid: string) => ({
  queryKey: ["profile", steamid],
  queryFn: () => fetchPlayerSummary(steamid),
});

// Idem: sem hook próprio porque o Home resolve o nome *no submit*, não ao
// renderizar. Passar pelo React Query (e não chamar o fetch cru) é o que dedupe
// o resubmit do mesmo nome — o cache do backend já protege a quota da chave, este
// evita até a ida ao backend.
export const resolvedSteamIdQuery = (vanity: string) => ({
  queryKey: ["resolve", vanity],
  queryFn: () => fetchResolvedSteamId(vanity),
});

// Query própria (não acoplada à dos jogos): se o perfil falhar, a biblioteca
// continua renderizando — o nome/avatar são best-effort.
export function usePlayerSummary(steamid: string) {
  return useQuery({
    ...playerSummaryQuery(steamid),
    enabled: isSteamId64(steamid),
  });
}

export function useGameDetail(steamid: string, appid: number) {
  return useQuery({
    queryKey: ["game", steamid, appid],
    queryFn: () => fetchGameDetail(steamid, appid),
    enabled: isSteamId64(steamid),
  });
}
