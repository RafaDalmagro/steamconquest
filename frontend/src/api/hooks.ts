import { useQuery } from "@tanstack/react-query";

import {
  fetchGameDetail,
  fetchGames,
  fetchPlayerSummary,
  type Group,
  type Sort,
} from "./client";
import { isSteamId64 } from "@/lib/steamid";

// `enabled` aqui não é a mensagem de erro — quem a mostra é o guard de rota em
// App.tsx. É o que impede DISPARAR request com id malformado, e precisa morar no
// hook porque o Header (trilha de navegação) vive fora do <Routes> e também
// consome estes hooks. O appid mal formado fica de fora de propósito: o 422 do
// backend já devolve mensagem legível, e assim não há tela em branco.

export function useGames(steamid: string, sort: Sort, group: Group = "none") {
  return useQuery({
    queryKey: ["games", steamid, sort, group],
    queryFn: () => fetchGames(steamid, sort, group),
    enabled: isSteamId64(steamid),
  });
}

// Options soltas (não só o hook): o Home as usa via queryClient.fetchQuery para
// validar o id antes de navegar, e a Library reaproveita o mesmo cache depois.
export const playerSummaryQuery = (steamid: string) => ({
  queryKey: ["profile", steamid],
  queryFn: () => fetchPlayerSummary(steamid),
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
