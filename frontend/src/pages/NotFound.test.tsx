import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";

import App from "@/App";
import { renderWithProviders } from "@/test/utils";

describe("NotFound", () => {
  it("mostra página de erro em rota inexistente", () => {
    renderWithProviders(<App />, "/rota/que/nao/existe");

    expect(
      screen.getByRole("heading", { name: /não encontrada/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /voltar para o início/i }),
    ).toBeInTheDocument();
  });
});
