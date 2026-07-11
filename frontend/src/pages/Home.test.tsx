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
      vi.fn(async () =>
        jsonResponse([
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

  it("pré-preenche o input com o último id salvo", () => {
    localStorage.setItem("lastSteamId", "76561197960287930");

    renderWithProviders(<App />);

    expect(screen.getByLabelText("Steam ID")).toHaveValue("76561197960287930");
  });
});
