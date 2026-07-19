import type { ReactElement } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";

export function renderWithProviders(ui: ReactElement, route = "/") {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}

export function jsonResponse(data: unknown, ok = true, status = 200): Response {
  return { ok, status, json: async () => data } as Response;
}

// Expõe a querystring atual para asserções sobre a URL. Existe porque o
// `MemoryRouter` mantém a rota em memória e **não** mexe em `window.location`:
// sem isto não há como afirmar o que uma interação escreveu (ou apagou) na query.
// Renderizar como irmão do componente sob teste, dentro do mesmo router:
//   const url = capturaUrl();
//   renderWithProviders(<><App /><url.Spy /></>, "/rota?x=1");
export function capturaUrl() {
  const atual = { search: "" };
  function Spy() {
    atual.search = useLocation().search;
    return null;
  }
  return { atual, Spy };
}
