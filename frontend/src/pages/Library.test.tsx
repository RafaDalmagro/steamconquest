import { afterEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

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

  it("marca como recente só o jogo com playtime nas últimas 2 semanas", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse([
          {
            appid: 10,
            name: "Portal",
            playtime_minutes: 480,
            playtime_2weeks_minutes: 120,
            icon_url: null,
          },
          {
            appid: 20,
            name: "Half-Life 2",
            playtime_minutes: 60,
            playtime_2weeks_minutes: null,
            icon_url: null,
          },
        ]),
      ),
    );

    renderWithProviders(<App />, "/u/76561197960287930");

    expect(await screen.findByText("Recente")).toBeInTheDocument();
    expect(screen.getAllByText("Recente")).toHaveLength(1);
    expect(screen.getByText("Portal").closest("a")).toHaveTextContent("Recente");
  });

  it("busca por nome sem novo request ao servidor", async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse([
        { appid: 10, name: "Portal", playtime_minutes: 480, icon_url: null },
        { appid: 20, name: "Half-Life 2", playtime_minutes: 60, icon_url: null },
      ]),
    );
    vi.stubGlobal("fetch", fetchMock);

    renderWithProviders(<App />, "/u/76561197960287930");
    await screen.findByText("Portal");

    await userEvent.type(screen.getByRole("searchbox"), "half");

    expect(screen.queryByText("Portal")).not.toBeInTheDocument();
    expect(screen.getByText("Half-Life 2")).toBeInTheDocument();
    // Client-side: nenhuma chamada além da carga inicial (jogos + perfil).
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("avisa quando a busca não encontra nenhum jogo", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse([
          { appid: 10, name: "Portal", playtime_minutes: 480, icon_url: null },
        ]),
      ),
    );

    renderWithProviders(<App />, "/u/76561197960287930");
    await screen.findByText("Portal");

    await userEvent.type(screen.getByRole("searchbox"), "xyz");

    expect(screen.getByText("Nenhum jogo encontrado.")).toBeInTheDocument();
  });

  it("resume jogos e horas, e conta os 100% quando há dados de conquista", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse([
          {
            appid: 10,
            name: "Portal",
            playtime_minutes: 90,
            icon_url: null,
            percent: 100,
            achieved_count: 2,
            total_count: 2,
          },
          {
            appid: 20,
            name: "Half-Life 2",
            playtime_minutes: 30,
            icon_url: null,
            percent: 50,
            achieved_count: 1,
            total_count: 2,
          },
        ]),
      ),
    );

    renderWithProviders(<App />, "/u/76561197960287930?sort=percent");

    expect(await screen.findByText(/2 jogos/)).toBeInTheDocument();
    expect(screen.getByText(/2,0 h/)).toBeInTheDocument();
    expect(screen.getByText(/1 jogo 100%/)).toBeInTheDocument();
  });

  it("resumo acompanha a busca e some com o contador de 100% sem dados de conquista", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse([
          { appid: 10, name: "Portal", playtime_minutes: 90, icon_url: null },
          { appid: 20, name: "Half-Life 2", playtime_minutes: 30, icon_url: null },
        ]),
      ),
    );

    renderWithProviders(<App />, "/u/76561197960287930");
    await screen.findByText("Portal");

    // sort=playtime não carrega conquistas: sem percentual, sem contador de 100%.
    expect(screen.queryByText(/100%/)).not.toBeInTheDocument();

    await userEvent.type(screen.getByRole("searchbox"), "half");

    expect(screen.getByText(/1 jogo/)).toBeInTheDocument();
    expect(screen.getByText(/0,5 h/)).toBeInTheDocument();
  });

  it("mostra o nome e o avatar do perfil no título", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) =>
        url.includes("/profile")
          ? jsonResponse({
              personaname: "Fulano",
              avatar_url: "http://a/av.jpg",
            })
          : jsonResponse([
              { appid: 10, name: "Portal", playtime_minutes: 480, icon_url: null },
            ]),
      ),
    );

    renderWithProviders(<App />, "/u/76561197960287930");

    await waitFor(() =>
      expect(
        screen.getByRole("heading", { name: /Biblioteca de Fulano/ }),
      ).toBeInTheDocument(),
    );
    expect(screen.getByRole("img", { name: "Fulano" })).toHaveAttribute(
      "src",
      "http://a/av.jpg",
    );
  });

  it("mantém a biblioteca quando o perfil falha", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) =>
        url.includes("/profile")
          ? jsonResponse({ detail: "Dados indisponíveis." }, false, 404)
          : jsonResponse([
              { appid: 10, name: "Portal", playtime_minutes: 480, icon_url: null },
            ]),
      ),
    );

    renderWithProviders(<App />, "/u/76561197960287930");

    await waitFor(() => expect(screen.getByText("Portal")).toBeInTheDocument());
    expect(
      screen.getByRole("heading", { name: /Biblioteca/ }),
    ).toBeInTheDocument();
  });

  it("mostra erro e não chama a API quando o steamid da URL é inválido", async () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);

    renderWithProviders(<App />, "/u/abc");

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Steam ID inválido",
    );
    expect(fetchSpy).not.toHaveBeenCalled();
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
