import { afterEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import App from "@/App";
import { jsonResponse, renderWithProviders } from "@/test/utils";

afterEach(() => vi.restoreAllMocks());

const detailComConquistas = {
  appid: 10,
  name: "Portal",
  supports_achievements: true,
  achieved_count: 1,
  total_count: 2,
  percent: 50.0,
  achievements: [
    {
      apiname: "A",
      display_name: "Conquista A",
      description: null,
      icon_url: null,
      achieved: true,
    },
    {
      apiname: "B",
      display_name: "Conquista B",
      description: null,
      icon_url: null,
      achieved: false,
    },
  ],
};

describe("GameDetail", () => {
  it("filtra por status sem novo request ao servidor", async () => {
    const fetchMock = vi.fn(async () => jsonResponse(detailComConquistas));
    vi.stubGlobal("fetch", fetchMock);

    renderWithProviders(<App />, "/u/76561197960287930/game/10");

    await waitFor(() =>
      expect(screen.getByText("Conquista A")).toBeInTheDocument(),
    );
    expect(screen.getByText("Conquista B")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("tab", { name: "Pendentes" }));

    expect(screen.queryByText("Conquista A")).not.toBeInTheDocument();
    expect(screen.getByText("Conquista B")).toBeInTheDocument();
    // Filtro é client-side: nenhuma chamada extra além da carga inicial.
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("mostra mensagem quando o jogo não tem conquistas", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse({
          appid: 99,
          name: "Sem Stats",
          supports_achievements: false,
          achieved_count: 0,
          total_count: 0,
          percent: 0.0,
          achievements: [],
        }),
      ),
    );

    renderWithProviders(<App />, "/u/76561197960287930/game/99");

    await waitFor(() =>
      expect(
        screen.getByText("Este jogo não possui conquistas."),
      ).toBeInTheDocument(),
    );
  });
});
