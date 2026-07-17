import { afterEach, describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { useGames, usePlayerSummary } from "./hooks";
import { jsonResponse } from "@/test/utils";

function wrapper() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
}

afterEach(() => vi.restoreAllMocks());

describe("useGames", () => {
  it("retorna os jogos em caso de sucesso", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse([
          { appid: 10, name: "Portal", playtime_minutes: 60, icon_url: null },
        ]),
      ),
    );

    const { result } = renderHook(() => useGames("76561197960287930", []), {
      wrapper: wrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.[0].name).toBe("Portal");
  });

  it("expõe a mensagem de erro do backend quando a resposta falha", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse({ detail: "Perfil privado." }, false, 404),
      ),
    );

    const { result } = renderHook(() => useGames("76561197960287930", []), {
      wrapper: wrapper(),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error?.message).toBe("Perfil privado.");
  });
});

describe("usePlayerSummary", () => {
  it("retorna nome e avatar do perfil", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse({ personaname: "Fulano", avatar_url: "http://a/av.jpg" }),
      ),
    );

    const { result } = renderHook(
      () => usePlayerSummary("76561197960287930"),
      { wrapper: wrapper() },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.personaname).toBe("Fulano");
    expect(result.current.data?.avatar_url).toBe("http://a/av.jpg");
  });

  it("não busca o perfil quando não há steamid", () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);

    renderHook(() => usePlayerSummary(""), { wrapper: wrapper() });

    expect(fetchSpy).not.toHaveBeenCalled();
  });
});
