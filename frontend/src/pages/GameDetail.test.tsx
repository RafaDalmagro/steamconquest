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
  it("mostra erro e não chama a API quando o steamid da URL é inválido", async () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);

    renderWithProviders(<App />, "/u/abc/game/10");

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Steam ID inválido",
    );
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("mostra a mensagem do backend quando o appid da URL não é um número", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse(
          { detail: "Parâmetro inválido na URL. Confira o Steam ID e o jogo." },
          false,
          422,
        ),
      ),
    );

    renderWithProviders(<App />, "/u/76561197960287930/game/abc");

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Parâmetro inválido na URL",
    );
  });

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

  it("mostra a data de desbloqueio só nas conquistas obtidas", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse({
          ...detailComConquistas,
          achievements: [
            {
              ...detailComConquistas.achievements[0],
              unlocked_at: "2011-08-03T04:27:58Z",
            },
            detailComConquistas.achievements[1], // pendente: sem data
          ],
        }),
      ),
    );

    renderWithProviders(<App />, "/u/76561197960287930/game/10");

    expect(await screen.findByText("Obtida em 03/08/2011")).toBeInTheDocument();
    expect(screen.queryAllByText(/Obtida em/)).toHaveLength(1);
  });

  it("ordena obtidas da mais recente para a mais antiga, pendentes por último", async () => {
    const ach = (
      apiname: string,
      achieved: boolean,
      unlocked_at: string | null = null,
    ) => ({
      apiname,
      display_name: apiname,
      description: null,
      icon_url: null,
      achieved,
      unlocked_at,
    });
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse({
          ...detailComConquistas,
          achievements: [
            ach("Pendente 1", false),
            ach("Antiga", true, "2020-01-01T00:00:00Z"),
            // Obtida sem data (unlocktime 0): depois das datadas, antes das pendentes.
            ach("Sem data", true),
            ach("Recente", true, "2024-06-01T00:00:00Z"),
            ach("Pendente 2", false),
          ],
        }),
      ),
    );

    renderWithProviders(<App />, "/u/76561197960287930/game/10");

    await screen.findByText("Recente");
    // getAllByText devolve na ordem do DOM — é o que queremos asserir.
    const nomes = screen
      .getAllByText(/^(Recente|Antiga|Sem data|Pendente \d)$/)
      .map((el) => el.textContent);
    expect(nomes).toEqual([
      "Recente",
      "Antiga",
      "Sem data",
      "Pendente 1",
      "Pendente 2",
    ]);
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
