import { afterEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import App from "@/App";
import { jsonResponse, renderWithProviders } from "@/test/utils";

afterEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
});

describe("Home", () => {
  it("recusa o id incompleto sem gastar chamada, dizendo quantos dígitos vieram", async () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);

    renderWithProviders(<App />);

    await userEvent.type(screen.getByLabelText("Steam ID"), "123");
    await userEvent.click(screen.getByRole("button", { name: "Ver biblioteca" }));

    // Quem digita só dígitos está tentando um SteamID64 e comeu algum: a resposta
    // útil sai daqui, de graça, em vez de gastar quota no /resolve para ouvir
    // "perfil não encontrado".
    expect(
      screen.getByText("Um SteamID64 tem 17 dígitos — você informou 3."),
    ).toBeInTheDocument();
    expect(fetchSpy).not.toHaveBeenCalled();
    // Um id que nunca foi verificado não pode virar o "Continuar como" da
    // próxima visita (AC-062).
    expect(localStorage.getItem("lastSteamId")).toBeNull();
  });

  it("salva o id e navega para a biblioteca quando válido", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) =>
        url.includes("/profile")
          ? jsonResponse({ personaname: "Fulano", avatar_url: null })
          : jsonResponse([
              { appid: 10, name: "Portal", playtime_minutes: 60, icon_url: null },
            ]),
      ),
    );

    renderWithProviders(<App />);

    await userEvent.type(
      screen.getByLabelText("Steam ID"),
      "76561197960287930",
    );
    await userEvent.click(screen.getByRole("button", { name: "Ver biblioteca" }));

    await waitFor(() => expect(screen.getByText("Portal")).toBeInTheDocument());
    expect(localStorage.getItem("lastSteamId")).toBe("76561197960287930");
  });

  it("não navega e mostra erro quando o Steam ID não existe", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse(
          { detail: "Steam ID não encontrado. Confira os 17 dígitos." },
          false,
          404,
        ),
      ),
    );

    renderWithProviders(<App />);

    await userEvent.type(
      screen.getByLabelText("Steam ID"),
      "76561199999999999",
    );
    await userEvent.click(screen.getByRole("button", { name: "Ver biblioteca" }));

    expect(
      await screen.findByText("Steam ID não encontrado. Confira os 17 dígitos."),
    ).toBeInTheDocument();
    expect(localStorage.getItem("lastSteamId")).toBeNull();
    expect(screen.getByLabelText("Steam ID")).toBeInTheDocument(); // segue no Home
  });

  it("não navega quando a Steam falha durante a verificação", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse(
          { detail: "A Steam limitou as requisições. Tente novamente em instantes." },
          false,
          429,
        ),
      ),
    );

    renderWithProviders(<App />);

    await userEvent.type(
      screen.getByLabelText("Steam ID"),
      "76561197960287930",
    );
    await userEvent.click(screen.getByRole("button", { name: "Ver biblioteca" }));

    expect(
      await screen.findByText(
        "A Steam limitou as requisições. Tente novamente em instantes.",
      ),
    ).toBeInTheDocument();
    expect(localStorage.getItem("lastSteamId")).toBeNull();
    expect(screen.getByLabelText("Steam ID")).toBeInTheDocument();
  });

  it("começa com o input vazio mesmo havendo id salvo", () => {
    localStorage.setItem("lastSteamId", "76561197960287930");
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse({})));

    renderWithProviders(<App />);

    expect(screen.getByLabelText("Steam ID")).toHaveValue("");
  });

  it("oferece continuar como o último perfil salvo", async () => {
    localStorage.setItem("lastSteamId", "76561197960287930");
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse({ personaname: "Fulano", avatar_url: "http://a/av.jpg" }),
      ),
    );

    renderWithProviders(<App />);

    const link = await screen.findByRole("link", { name: /Fulano/ });
    expect(link).toHaveAttribute("href", "/u/76561197960287930");
    expect(screen.getByRole("img", { name: "Fulano" })).toHaveAttribute(
      "src",
      "http://a/av.jpg",
    );
  });

  it("não oferece continuar quando o perfil salvo falha", async () => {
    localStorage.setItem("lastSteamId", "76561197960287930");
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse({ detail: "Dados indisponíveis." }, false, 404),
      ),
    );

    renderWithProviders(<App />);

    await waitFor(() =>
      expect(screen.queryByText(/Continuar como/)).not.toBeInTheDocument(),
    );
  });

  it("não busca perfil quando não há id salvo", () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);

    renderWithProviders(<App />);

    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("aceita o link do perfil e navega sem gastar chamada no /resolve", async () => {
    const fetchSpy = vi.fn(async (url: string) =>
      url.includes("/profile")
        ? jsonResponse({ personaname: "Fulano", avatar_url: null })
        : jsonResponse([
            { appid: 10, name: "Portal", playtime_minutes: 60, icon_url: null },
          ]),
    );
    vi.stubGlobal("fetch", fetchSpy);

    renderWithProviders(<App />);

    await userEvent.type(
      screen.getByLabelText("Steam ID"),
      "https://steamcommunity.com/profiles/76561197960287930",
    );
    await userEvent.click(screen.getByRole("button", { name: "Ver biblioteca" }));

    await waitFor(() => expect(screen.getByText("Portal")).toBeInTheDocument());
    // Os 17 dígitos já estavam no link: resolvê-los na Steam seria pagar por um
    // dado que a regex entregou de graça.
    const urls = fetchSpy.mock.calls.map(([url]) => String(url));
    expect(urls.some((u) => u.includes("/resolve"))).toBe(false);
    expect(localStorage.getItem("lastSteamId")).toBe("76561197960287930");
  });

  it("resolve o nome do perfil na API e navega com o id devolvido", async () => {
    const fetchSpy = vi.fn(async (url: string) => {
      if (url.includes("/resolve"))
        return jsonResponse({ steamid: "76561197960287930" });
      if (url.includes("/profile"))
        return jsonResponse({ personaname: "Gabe", avatar_url: null });
      return jsonResponse([
        { appid: 10, name: "Portal", playtime_minutes: 60, icon_url: null },
      ]);
    });
    vi.stubGlobal("fetch", fetchSpy);

    renderWithProviders(<App />);

    await userEvent.type(screen.getByLabelText("Steam ID"), "gabelogannewell");
    await userEvent.click(screen.getByRole("button", { name: "Ver biblioteca" }));

    await waitFor(() => expect(screen.getByText("Portal")).toBeInTheDocument());
    // O ID não estava no input: só a Steam sabia — e só o backend pode perguntar.
    const urls = fetchSpy.mock.calls.map(([url]) => String(url));
    expect(urls[0]).toContain("/resolve?vanity=gabelogannewell");
    // O que se grava é o id resolvido, nunca o nome: /u/:steamid é a rota.
    expect(localStorage.getItem("lastSteamId")).toBe("76561197960287930");
  });

  it("mostra o erro do backend e não grava nada quando o nome não existe", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse(
          { detail: "Perfil não encontrado. Confira o link ou o nome do perfil." },
          false,
          404,
        ),
      ),
    );

    renderWithProviders(<App />);

    await userEvent.type(screen.getByLabelText("Steam ID"), "nao-existe");
    await userEvent.click(screen.getByRole("button", { name: "Ver biblioteca" }));

    expect(
      await screen.findByText(
        "Perfil não encontrado. Confira o link ou o nome do perfil.",
      ),
    ).toBeInTheDocument();
    expect(localStorage.getItem("lastSteamId")).toBeNull();
  });

  it("ensina a achar o link do perfil, sem roubar a tela de quem já sabe o id", async () => {
    renderWithProviders(<App />);

    const ajuda = screen.getByText("Não sei meu Steam ID");
    const details = ajuda.closest("details")!;
    // Recolhido por padrão: é fallback, não o caminho principal. (No jsdom o
    // conteúdo segue no DOM — quem esconde é o navegador —, então o que se
    // verifica é o estado do próprio <details>.)
    expect(details.open).toBe(false);

    await userEvent.click(ajuda);

    expect(details.open).toBe(true);
    expect(screen.getByText(/Copie o endereço/)).toBeInTheDocument();
    // A única falha que o app não conserta sozinho — e pela qual ele leva a culpa.
    expect(screen.getByText(/privado/i)).toBeInTheDocument();
  });
});
