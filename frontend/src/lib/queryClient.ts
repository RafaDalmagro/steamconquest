import { QueryClient } from "@tanstack/react-query";

import { ApiError } from "@/api/client";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // 4xx não muda de opinião: repetir um "Steam ID não encontrado" só custa
      // uma 2ª chamada à Steam e atrasa o erro. Retry só em falha transitória.
      retry: (falhas, erro) =>
        erro instanceof ApiError && erro.status >= 400 && erro.status < 500
          ? false
          : falhas < 1,
      refetchOnWindowFocus: false,
      staleTime: 60_000,
    },
  },
});
