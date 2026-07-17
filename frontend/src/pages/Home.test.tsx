import { afterEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import App from "@/App";
import { jsonResponse, renderWithProviders } from "@/test/utils";

afterEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
});

// O perfil de exemplo é buscado no mount de quem chega sem id salvo (CON-083),
// então ele aparece no fetch de todo teste de visitante novo. Quem quer falar do
// *submit* filtra essa chamada: ela é ruído de fundo, não parte do fluxo testado.
const DEMO_PROFILE_URL = "/users/76561198082363621/profile";
const semDemo = (urls: string[]) =>
  urls.filter((u) => !u.includes(DEMO_PROFILE_URL));

// O link de exemplo é identificado pelo href, nunca pelo rótulo: a redação é
// reversível de propósito (REQ-080) e não é critério de aceite — teste que
// quebra ao reescrever uma frase está testando a frase, não a regra.
const temLinkDemo = () =>
  screen
    .queryAllByRole("link")
    .some((l) => l.getAttribute("href") === "/u/76561198082363621");

describe("Home", () => {
  it("recusa o id incompleto sem gastar chamada, dizendo quantos dígitos vieram", async () => {
    // 404 em tudo: o perfil de exemplo não resolve, some (AC-2), e o teste fica
    // só com o que lhe interessa — o submit não gastou chamada.
    const fetchSpy = vi.fn(async (_url: string) =>
      jsonResponse({ detail: "não existe" }, false, 404),
    );
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
    const urls = fetchSpy.mock.calls.map(([url]) => String(url));
    expect(semDemo(urls)).toEqual([]);
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
    // Avatar é decorativo (alt=""), logo não tem nome acessível: o nome do
    // jogador já está em texto no link. Busca pelo src.
    expect(link.querySelector("img")).toHaveAttribute("src", "http://a/av.jpg");
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

  // Reescrito, não deletado (CON-083): a asserção original era "zero chamadas
  // sem id salvo", propriedade revogada de propósito pelo perfil de exemplo — sem
  // buscá-lo não há como saber que quebrou, e um 404 na cara de quem chega agora
  // é pior que a chamada. O que o teste protegia de verdade continua aqui: não
  // buscar um perfil salvo que não existe.
  it("não busca perfil salvo quando não há id salvo", async () => {
    const fetchSpy = vi.fn(async (_url: string) =>
      jsonResponse({ personaname: "Extremezada", avatar_url: null }),
    );
    vi.stubGlobal("fetch", fetchSpy);

    renderWithProviders(<App />);

    await screen.findByRole("link", { name: /Extremezada/ });
    const urls = fetchSpy.mock.calls.map(([url]) => String(url));
    expect(urls).toEqual([
      expect.stringContaining("/users/76561198082363621/profile"),
    ]);
  });

  it("prova o app com um perfil de exemplo para quem chega sem perfil salvo", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse({
          personaname: "Extremezada",
          avatar_url: "http://a/demo.jpg",
        }),
      ),
    );

    renderWithProviders(<App />);

    // Prova antes do pedido (AC-1): quem nunca veio vê uma biblioteca real sem
    // ter entregue a própria. O nome e o avatar vêm do perfil resolvido — é o
    // que separa prova viva de link hardcoded que ninguém verificou.
    const link = await screen.findByRole("link", { name: /Extremezada/ });
    expect(link).toHaveAttribute("href", "/u/76561198082363621");
    expect(link.querySelector("img")).toHaveAttribute(
      "src",
      "http://a/demo.jpg",
    );
  });

  it("some com o perfil de exemplo, sem alarde, quando ele não resolve", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (_url: string) =>
        jsonResponse({ detail: "Dados indisponíveis." }, false, 404),
      ),
    );

    renderWithProviders(<App />);

    // Prova é decoração (AC-2): o perfil de exemplo virou privado, a Steam caiu
    // ou o id morreu — o visitante novo não pode ver erro nenhum por causa disso,
    // e muito menos um link que entrega 404 no clique. O formulário é o que
    // importa, e ele continua de pé.
    await waitFor(() => expect(temLinkDemo()).toBe(false));
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Steam ID")).toBeInTheDocument();
  });

  it("não oferece perfil de exemplo a quem já tem perfil salvo", async () => {
    localStorage.setItem("lastSteamId", "76561197960287930");
    vi.stubGlobal(
      "fetch",
      vi.fn(async (_url: string) =>
        jsonResponse({ personaname: "Fulano", avatar_url: null }),
      ),
    );

    renderWithProviders(<App />);

    // Um alvo por visitante (AC-3): quem já converteu veio buscar a própria
    // biblioteca, e a demo ao lado seria o único outro link da página — atenção
    // que ela não merece, apontando para longe do que ele veio fazer.
    await screen.findByRole("link", { name: /Fulano/ });
    expect(temLinkDemo()).toBe(false);
  });

  it("não busca o perfil de exemplo quando há perfil salvo", async () => {
    localStorage.setItem("lastSteamId", "76561197960287930");
    const fetchSpy = vi.fn(async (_url: string) =>
      jsonResponse({ personaname: "Fulano", avatar_url: null }),
    );
    vi.stubGlobal("fetch", fetchSpy);

    renderWithProviders(<App />);

    await screen.findByRole("link", { name: /Fulano/ });
    // AC-6: o custo da prova (CON-083) é cobrado só de quem precisa dela.
    const urls = fetchSpy.mock.calls.map(([url]) => String(url));
    expect(urls.some((u) => u.includes(DEMO_PROFILE_URL))).toBe(false);
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
    expect(semDemo(urls)[0]).toContain("/resolve?vanity=gabelogannewell");
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

  it("responde à objeção de confiança sem exigir interação", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (_url: string) => jsonResponse({ detail: "x" }, false, 404)),
    );

    renderWithProviders(<App />);

    // AC-5: "por que este site quer meu perfil?" dispara quando o cursor entra no
    // campo — a resposta tem que estar lá, visível, não escondida atrás de um
    // clique no <details> nem depois do pedido, onde ela não desarma nada.
    const confianca = screen.getByText(/sem login e sem senha/i);
    expect(confianca).toBeInTheDocument();
    expect(confianca.closest("details")).toBeNull();

    // AC-4: a seção "Como funciona" explicava um problema que quem chega já tem.
    expect(screen.queryByText("Como funciona")).not.toBeInTheDocument();
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
