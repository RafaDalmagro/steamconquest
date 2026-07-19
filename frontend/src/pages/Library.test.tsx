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

  it("reordena sem novo request ao servidor", async () => {
    // Fora de ordem de propósito: quem ordena é o cliente, com o dado que já tem.
    const fetchMock = vi.fn(async () =>
      jsonResponse([
        { appid: 20, name: "Half-Life 2", playtime_minutes: 60, icon_url: null },
        { appid: 10, name: "Portal", playtime_minutes: 480, icon_url: null },
        { appid: 30, name: "Antichamber", playtime_minutes: 5, icon_url: null },
      ]),
    );
    vi.stubGlobal("fetch", fetchMock);

    renderWithProviders(<App />, "/u/76561197960287930");
    await screen.findByText("Portal");

    const nomes = () =>
      screen.getAllByRole("heading", { level: 3 }).map((h) => h.textContent);
    expect(nomes()).toEqual(["Portal", "Half-Life 2", "Antichamber"]); // playtime

    await userEvent.click(screen.getByRole("button", { name: "Nome" }));

    expect(nomes()).toEqual(["Antichamber", "Half-Life 2", "Portal"]);
    // Reordenar não muda o dado: nada além da carga inicial (jogos + perfil).
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("reflete a busca na URL e aceita deep-link por ?q=", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse([
          { appid: 10, name: "Portal", playtime_minutes: 480, icon_url: null },
          { appid: 20, name: "Half-Life 2", playtime_minutes: 60, icon_url: null },
        ]),
      ),
    );

    renderWithProviders(<App />, "/u/76561197960287930?q=half");
    await screen.findByText("Half-Life 2");

    // Deep-link: a busca já veio aplicada da URL, sem ninguém digitar.
    expect(screen.queryByText("Portal")).not.toBeInTheDocument();
    expect(screen.getByRole("searchbox")).toHaveValue("half");

    await userEvent.clear(screen.getByRole("searchbox"));
    await userEvent.type(screen.getByRole("searchbox"), "portal");

    expect(screen.getByText("Portal")).toBeInTheDocument();
    expect(screen.queryByText("Half-Life 2")).not.toBeInTheDocument();
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

  it("conta os jogos 'quase 100%' no resumo", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse([
          {
            appid: 10,
            name: "Portal",
            playtime_minutes: 90,
            icon_url: null,
            percent: 85,
            achieved_count: 17,
            total_count: 20,
          },
          {
            appid: 20,
            name: "Half-Life 2",
            playtime_minutes: 30,
            icon_url: null,
            percent: 40,
            achieved_count: 4,
            total_count: 10,
          },
        ]),
      ),
    );

    renderWithProviders(<App />, "/u/76561197960287930?sort=percent");

    expect(await screen.findByText(/1 jogo quase 100%/)).toBeInTheDocument();
  });

  it("no resumo, 'quase 100%' vem antes de '100%'", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse([
          {
            appid: 10,
            name: "Quase",
            playtime_minutes: 90,
            icon_url: null,
            percent: 85,
            achieved_count: 17,
            total_count: 20,
          },
          {
            appid: 20,
            name: "Completo",
            playtime_minutes: 30,
            icon_url: null,
            percent: 100,
            achieved_count: 20,
            total_count: 20,
          },
        ]),
      ),
    );

    renderWithProviders(<App />, "/u/76561197960287930?sort=percent");

    expect(
      await screen.findByText(/1 jogo quase 100% · 1 jogo 100%/),
    ).toBeInTheDocument();
  });

  it("omite 'quase 100%' do resumo quando nenhum jogo está quase lá", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse([
          {
            appid: 10,
            name: "Completo",
            playtime_minutes: 90,
            icon_url: null,
            percent: 100,
            achieved_count: 20,
            total_count: 20,
          },
          {
            appid: 20,
            name: "Longe",
            playtime_minutes: 30,
            icon_url: null,
            percent: 40,
            achieved_count: 4,
            total_count: 10,
          },
        ]),
      ),
    );

    renderWithProviders(<App />, "/u/76561197960287930?sort=percent");

    // O contador de 100% aparece (há dados), mas o de "quase" não.
    expect(await screen.findByText(/1 jogo 100%/)).toBeInTheDocument();
    expect(screen.queryByText(/quase 100%/)).not.toBeInTheDocument();
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

    // Casa a linha inteira: o card do jogo também mostra "0,5 h" (mesmo
    // formatador), então /0,5 h/ sozinho seria ambíguo.
    expect(screen.getByText("1 jogo · 0,5 h")).toBeInTheDocument();
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
    // Avatar é decorativo (alt=""): o nome já vem no h1 ao lado. Busca pelo src.
    expect(
      document.querySelector('img[src="http://a/av.jpg"]'),
    ).toBeInTheDocument();
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

  it("mostra a data da última vez jogada, e nada em quem nunca jogou", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse([
          {
            appid: 10,
            name: "Portal",
            playtime_minutes: 480,
            icon_url: null,
            // Meio-dia UTC: a data não vira véspera no fuso local do CI.
            last_played_at: "2024-03-12T12:00:00Z",
          },
          {
            appid: 20,
            name: "Nunca Jogado",
            playtime_minutes: 0,
            icon_url: null,
            last_played_at: null,
          },
        ]),
      ),
    );

    renderWithProviders(<App />, "/u/76561197960287930?sort=last_played");

    expect(await screen.findByText("Jogado em 12/03/2024")).toBeInTheDocument();
    // Um único card tem data: o "nunca jogado" não inventa uma.
    expect(screen.queryAllByText(/Jogado em/)).toHaveLength(1);
  });

  it("ordena os quase-concluídos primeiro, do mais perto de fechar", async () => {
    // 100% não é "quase": o loop está fechado. Ele e o 30% caem no segundo
    // grupo, na ordem em que a Steam devolveu.
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse([
          { appid: 10, name: "Fechado", playtime_minutes: 10, icon_url: null, percent: 100 },
          { appid: 20, name: "Noventa", playtime_minutes: 10, icon_url: null, percent: 95 },
          { appid: 30, name: "Oitenta", playtime_minutes: 10, icon_url: null, percent: 85 },
          { appid: 40, name: "Longe", playtime_minutes: 10, icon_url: null, percent: 30 },
        ]),
      ),
    );

    renderWithProviders(<App />, "/u/76561197960287930");
    await screen.findByText("Fechado");

    await userEvent.click(screen.getByRole("button", { name: "Quase lá" }));

    expect(
      screen.getAllByRole("heading", { level: 3 }).map((h) => h.textContent),
    ).toEqual(["Noventa", "Oitenta", "Fechado", "Longe"]);
  });

  it("não quebra ao ordenar por quase lá com jogos sem dados de conquista", async () => {
    // percent null (jogo sem conquistas) nunca é "quase lá": isQuaseLa já
    // garante isso, e o comparador não pode promovê-lo pelo `?? 0`.
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse([
          { appid: 10, name: "SemDado", playtime_minutes: 10, icon_url: null, percent: null },
          { appid: 20, name: "Quase", playtime_minutes: 10, icon_url: null, percent: 90 },
        ]),
      ),
    );

    renderWithProviders(<App />, "/u/76561197960287930?sort=quase_la");
    await screen.findByText("Quase");

    expect(
      screen.getAllByRole("heading", { level: 3 }).map((h) => h.textContent),
    ).toEqual(["Quase", "SemDado"]);
  });
});
