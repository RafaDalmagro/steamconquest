import { afterEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";

import App from "@/App";
import { jsonResponse, renderWithProviders } from "@/test/utils";

const STEAMID = "76561197960287930";

afterEach(() => vi.restoreAllMocks());

function nav() {
  return screen.getByRole("navigation", { name: "Trilha de navegação" });
}

describe("Header — breadcrumb", () => {
  it("na home mostra só Início como página atual", () => {
    renderWithProviders(<App />, "/");

    const inicio = within(nav()).getByText("Início");
    expect(inicio).toHaveAttribute("aria-current", "page");
    expect(within(nav()).queryByText("Biblioteca")).not.toBeInTheDocument();
  });

  it("na biblioteca mostra Início (link) e Biblioteca (atual)", () => {
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse([])));

    renderWithProviders(<App />, `/u/${STEAMID}`);

    expect(within(nav()).getByRole("link", { name: "Início" })).toHaveAttribute(
      "href",
      "/",
    );
    expect(within(nav()).getByText("Biblioteca")).toHaveAttribute(
      "aria-current",
      "page",
    );
  });

  it("no detalhe mostra o nome do jogo como página atual e Biblioteca como link", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse({
          appid: 10,
          name: "Portal",
          supports_achievements: true,
          achieved_count: 0,
          total_count: 0,
          percent: 0,
          achievements: [],
        }),
      ),
    );

    renderWithProviders(<App />, `/u/${STEAMID}/game/10`);

    await waitFor(() =>
      expect(within(nav()).getByText("Portal")).toHaveAttribute(
        "aria-current",
        "page",
      ),
    );
    expect(
      within(nav()).getByRole("link", { name: "Biblioteca" }),
    ).toHaveAttribute("href", `/u/${STEAMID}`);
  });

  it("o logo tem nome acessível de link para a home", () => {
    renderWithProviders(<App />, "/");

    expect(
      screen.getByRole("link", { name: /conquistas/i }),
    ).toHaveAttribute("href", "/");
  });
});
