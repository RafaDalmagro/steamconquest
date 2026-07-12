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
  it("mostra erro e não navega quando o Steam ID é inválido", async () => {
    renderWithProviders(<App />);

    await userEvent.type(screen.getByLabelText("Steam ID"), "123");
    await userEvent.click(screen.getByRole("button", { name: "Ver biblioteca" }));

    expect(
      screen.getByText("Informe um SteamID64 válido (17 dígitos)."),
    ).toBeInTheDocument();
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
});
