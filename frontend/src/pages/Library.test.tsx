import { afterEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";

import App from "@/App";
import { jsonResponse, renderWithProviders } from "@/test/utils";

afterEach(() => vi.restoreAllMocks());

describe("Library", () => {
  it("renderiza os jogos como cards linkando para o detalhe", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse([
          { appid: 10, name: "Portal", playtime_minutes: 480, icon_url: null },
          { appid: 20, name: "Half-Life 2", playtime_minutes: 60, icon_url: null },
        ]),
      ),
    );

    renderWithProviders(<App />, "/u/76561197960287930");

    await waitFor(() => expect(screen.getByText("Portal")).toBeInTheDocument());
    expect(screen.getByText("Half-Life 2")).toBeInTheDocument();
    const link = screen.getByText("Portal").closest("a");
    expect(link).toHaveAttribute("href", "/u/76561197960287930/game/10");
  });

  it("agrupa por gênero em seções, com 'Sem categoria' por último", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse([
          { appid: 10, name: "Portal", playtime_minutes: 480, icon_url: null, genres: ["Puzzle"] },
          { appid: 20, name: "Skyrim", playtime_minutes: 60, icon_url: null, genres: ["RPG"] },
          { appid: 30, name: "Sem Gênero", playtime_minutes: 5, icon_url: null, genres: [] },
        ]),
      ),
    );

    renderWithProviders(<App />, "/u/76561197960287930?group=genre");

    await waitFor(() =>
      expect(screen.getByRole("heading", { name: /Puzzle/ })).toBeInTheDocument(),
    );
    const headings = screen
      .getAllByRole("heading", { level: 2 })
      .map((h) => h.textContent);
    expect(headings).toEqual(["Puzzle1", "RPG1", "Sem categoria1"]);
  });

  it("mostra a mensagem de erro do backend quando a API falha", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse(
          { detail: "A Steam está indisponível no momento." },
          false,
          502,
        ),
      ),
    );

    renderWithProviders(<App />, "/u/76561197960287930");

    await waitFor(() =>
      expect(
        screen.getByText("A Steam está indisponível no momento."),
      ).toBeInTheDocument(),
    );
  });
});
