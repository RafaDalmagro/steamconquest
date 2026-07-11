import { useQuery } from "@tanstack/react-query";

import { fetchGameDetail, fetchGames, type Group, type Sort } from "./client";

export function useGames(steamid: string, sort: Sort, group: Group = "none") {
  return useQuery({
    queryKey: ["games", steamid, sort, group],
    queryFn: () => fetchGames(steamid, sort, group),
  });
}

export function useGameDetail(steamid: string, appid: number) {
  return useQuery({
    queryKey: ["game", steamid, appid],
    queryFn: () => fetchGameDetail(steamid, appid),
  });
}
