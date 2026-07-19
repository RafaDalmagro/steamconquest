import { afterEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import App from "@/App";
import { capturaUrl, jsonResponse, renderWithProviders } from "@/test/utils";

afterEach(() => vi.restoreAllMocks());

const detailComConquistas = {
  appid: 10,
  name: "Portal",
  supports_achievements: true,
  achieved_count: 1,
  total_count: 2,
  percent: 50.0,
  achievements: [
    {
      apiname: "A",
      display_name: "Conquista A",
      description: null,
      icon_url: null,
      achieved: true,
    },
    {
      apiname: "B",
      display_name: "Conquista B",
      description: null,
      icon_url: null,
      achieved: false,
    },
  ],
};

// Todas pendentes de propósito: `porDesbloqueio` empataria entre elas, então a
// ordem observada é a da raridade e de mais nada.
const comRaridade = (
  display_name: string,
  global_percent: number | null,
) => ({
  apiname: display_name,
  display_name,
  description: null,
  icon_url: null,
  achieved: false,
  global_percent,
});

const detailComRaridade = {
  ...detailComConquistas,
  achieved_count: 0,
  total_count: 3,
  percent: 0,
  // Nomeadas pelo percentil, e não "Rara"/"Comum": o AchievementItem renderiza
  // um badge com o texto "Rara" abaixo de 10%, e uma conquista com esse nome
  // faria as buscas por texto acharem dois elementos.
  achievements: [
    comRaridade("Dois", 2),
    comRaridade("Cinquenta", 50),
    comRaridade("Noventa", 90),
  ],
};

// O display_name mora num <strong> sem role própria; escopar ao tabpanel evita
// pegar texto de fora da lista.
const nomesNaLista = () =>
  Array.from(screen.getByRole("tabpanel").querySelectorAll("strong")).map(
    (s) => s.textContent,
  );

describe("GameDetail", () => {
  it("mostra erro e não chama a API quando o steamid da URL é inválido", async () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);

    renderWithProviders(<App />, "/u/abc/game/10");

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Steam ID inválido",
    );
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("mostra a mensagem do backend quando o appid da URL não é um número", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse(
          { detail: "Parâmetro inválido na URL. Confira o Steam ID e o jogo." },
          false,
          422,
        ),
      ),
    );

    renderWithProviders(<App />, "/u/76561197960287930/game/abc");

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Parâmetro inválido na URL",
    );
  });

  it("filtra por status sem novo request ao servidor", async () => {
    const fetchMock = vi.fn(async () => jsonResponse(detailComConquistas));
    vi.stubGlobal("fetch", fetchMock);

    renderWithProviders(<App />, "/u/76561197960287930/game/10");

    await waitFor(() =>
      expect(screen.getByText("Conquista A")).toBeInTheDocument(),
    );
    expect(screen.getByText("Conquista B")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("tab", { name: "Pendentes" }));

    expect(screen.queryByText("Conquista A")).not.toBeInTheDocument();
    expect(screen.getByText("Conquista B")).toBeInTheDocument();
    // Filtro é client-side: nenhuma chamada extra além da carga inicial.
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("liga a aba ao painel da lista e reflete o filtro na URL", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse(detailComConquistas)));

    // Deep-link: o filtro vem da URL, sem ninguém clicar.
    renderWithProviders(<App />, "/u/76561197960287930/game/10?filter=locked");

    await screen.findByText("Conquista B");
    expect(screen.queryByText("Conquista A")).not.toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Pendentes" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    // A lista tem de existir como tabpanel — é o que o aria-controls da aba
    // promete ao leitor de tela.
    expect(screen.getByRole("tabpanel")).toHaveTextContent("Conquista B");
  });

  it("mostra a data de desbloqueio só nas conquistas obtidas", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse({
          ...detailComConquistas,
          achievements: [
            {
              ...detailComConquistas.achievements[0],
              unlocked_at: "2011-08-03T04:27:58Z",
            },
            detailComConquistas.achievements[1], // pendente: sem data
          ],
        }),
      ),
    );

    renderWithProviders(<App />, "/u/76561197960287930/game/10");

    expect(await screen.findByText("Obtida em 03/08/2011")).toBeInTheDocument();
    expect(screen.queryAllByText(/Obtida em/)).toHaveLength(1);
  });

  it("ordena obtidas da mais recente para a mais antiga, pendentes por último", async () => {
    const ach = (
      apiname: string,
      achieved: boolean,
      unlocked_at: string | null = null,
    ) => ({
      apiname,
      display_name: apiname,
      description: null,
      icon_url: null,
      achieved,
      unlocked_at,
    });
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse({
          ...detailComConquistas,
          achievements: [
            ach("Pendente 1", false),
            ach("Antiga", true, "2020-01-01T00:00:00Z"),
            // Obtida sem data (unlocktime 0): depois das datadas, antes das pendentes.
            ach("Sem data", true),
            ach("Recente", true, "2024-06-01T00:00:00Z"),
            ach("Pendente 2", false),
          ],
        }),
      ),
    );

    renderWithProviders(<App />, "/u/76561197960287930/game/10");

    await screen.findByText("Recente");
    // getAllByText devolve na ordem do DOM — é o que queremos asserir.
    const nomes = screen
      .getAllByText(/^(Recente|Antiga|Sem data|Pendente \d)$/)
      .map((el) => el.textContent);
    expect(nomes).toEqual([
      "Recente",
      "Antiga",
      "Sem data",
      "Pendente 1",
      "Pendente 2",
    ]);
  });

  it("mostra mensagem quando o jogo não tem conquistas", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse({
          appid: 99,
          name: "Sem Stats",
          supports_achievements: false,
          achieved_count: 0,
          total_count: 0,
          percent: 0.0,
          achievements: [],
        }),
      ),
    );

    renderWithProviders(<App />, "/u/76561197960287930/game/99");

    await waitFor(() =>
      expect(
        screen.getByText("Este jogo não possui conquistas."),
      ).toBeInTheDocument(),
    );
  });

  it("mostra a raridade global e marca como rara a conquista abaixo de 10%", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse({
          ...detailComConquistas,
          achievements: [
            { ...detailComConquistas.achievements[0], global_percent: 42.7 },
            { ...detailComConquistas.achievements[1], global_percent: 4.1 },
          ],
        }),
      ),
    );

    renderWithProviders(<App />, "/u/76561197960287930/game/10");

    expect(await screen.findByText("42,7% dos jogadores")).toBeInTheDocument();
    expect(screen.getByText("4,1% dos jogadores")).toBeInTheDocument();
    // Só a de 4,1% é rara; a de 42,7% não.
    expect(screen.getAllByText("Rara")).toHaveLength(1);
  });

  it("renderiza normalmente quando a Steam não devolveu raridade", async () => {
    // global_percent null = jogo sem stats globais. A conquista continua listada.
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse(detailComConquistas)));

    renderWithProviders(<App />, "/u/76561197960287930/game/10");

    expect(await screen.findByText("Conquista A")).toBeInTheDocument();
    expect(screen.queryByText(/dos jogadores/)).not.toBeInTheDocument();
    expect(screen.queryByText("Rara")).not.toBeInTheDocument();
  });

  it("leva a conquista pendente ao vídeo, buscando pelo nome em inglês", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse({
          ...detailComConquistas,
          name: "Nioh: Complete Edition",
          achievements: [
            { ...detailComConquistas.achievements[1], name_en: "Spa Healer" },
          ],
        }),
      ),
    );

    renderWithProviders(<App />, "/u/76561197960287930/game/10");

    const link = await screen.findByRole("link", { name: "Como conseguir" });
    // O nome do jogo precisa chegar até o card: sem ele a busca acha qualquer
    // "Spa Healer" do YouTube, menos o do Nioh.
    expect(link).toHaveAttribute(
      "href",
      "https://www.youtube.com/results?search_query=Nioh%3A%20Complete%20Edition%20Spa%20Healer%20achievement",
    );
    // Sem noopener, a página aberta pode redirecionar esta aba.
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", expect.stringContaining("noopener"));
    expect(link).toHaveAttribute("rel", expect.stringContaining("noreferrer"));
  });

  it("não oferece 'como conseguir' numa conquista já obtida", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse({
          ...detailComConquistas,
          achievements: [
            { ...detailComConquistas.achievements[0], name_en: "Spa Healer" },
          ],
        }),
      ),
    );

    renderWithProviders(<App />, "/u/76561197960287930/game/10");

    await screen.findByText("Conquista A");
    expect(
      screen.queryByRole("link", { name: "Como conseguir" }),
    ).not.toBeInTheDocument();
  });

  it("não oferece 'como conseguir' quando não há nome em inglês para buscar", async () => {
    // name_en null = schema inglês indisponível ou conquista oculta. Buscar o
    // apiname não acharia nada, então o link não existe.
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse({
          ...detailComConquistas,
          achievements: [
            { ...detailComConquistas.achievements[1], name_en: null },
          ],
        }),
      ),
    );

    renderWithProviders(<App />, "/u/76561197960287930/game/10");

    await screen.findByText("Conquista B");
    expect(
      screen.queryByRole("link", { name: "Como conseguir" }),
    ).not.toBeInTheDocument();
  });

  it("aponta para os guias de conquista da comunidade, uma vez por jogo", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse({ ...detailComConquistas, appid: 485510 })),
    );

    renderWithProviders(<App />, "/u/76561197960287930/game/485510");

    // Filtro por tag, não por texto: buscar o nome da conquista devolve zero
    // resultado e a Steam cai calada nos guias populares — link que mente.
    const links = await screen.findAllByRole("link", {
      name: "Guias da comunidade",
    });
    expect(links).toHaveLength(1);
    expect(links[0]).toHaveAttribute(
      "href",
      "https://steamcommunity.com/app/485510/guides/?requiredtags%5B%5D=Achievements",
    );
    expect(links[0]).toHaveAttribute("rel", expect.stringContaining("noopener"));
  });

  it("não aponta para guias de conquista num jogo que não tem conquistas", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse({
          appid: 10,
          name: "Portal",
          supports_achievements: false,
          achieved_count: 0,
          total_count: 0,
          percent: 0,
          achievements: [],
        }),
      ),
    );

    renderWithProviders(<App />, "/u/76561197960287930/game/10");

    await screen.findByText("Este jogo não possui conquistas.");
    expect(
      screen.queryByRole("link", { name: "Guias da comunidade" }),
    ).not.toBeInTheDocument();
  });

  it("preserva a ordenação ao trocar de aba", async () => {
    // `setParams({ filter })` substitui a querystring inteira. Com um segundo
    // parâmetro, trocar de aba apagaria a ordenação escolhida — uma interação
    // desfazendo silenciosamente outra.
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse(detailComConquistas)));
    const url = capturaUrl();

    renderWithProviders(
      <>
        <App />
        <url.Spy />
      </>,
      "/u/76561197960287930/game/10?filter=locked&ordem=raras",
    );
    await screen.findByText("Conquista B");

    await userEvent.click(screen.getByRole("tab", { name: "Obtidas" }));

    expect(url.atual.search).toContain("filter=achieved");
    expect(url.atual.search).toContain("ordem=raras");
  });

  it("ordena da mais comum para a mais rara em \"mais fáceis\"", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse(detailComRaridade)));

    renderWithProviders(<App />, "/u/76561197960287930/game/10");
    await screen.findByText("Dois");

    await userEvent.click(screen.getByRole("button", { name: "Mais fáceis" }));

    expect(nomesNaLista()).toEqual(["Noventa", "Cinquenta", "Dois"]);
  });

  it("ordena da mais rara para a mais comum em \"mais raras\"", async () => {
    // Não é duplicata do anterior: porRaridade(1) e porRaridade(-1) são caminhos
    // distintos, e um sinal trocado passaria com só um deles coberto.
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse(detailComRaridade)));

    renderWithProviders(<App />, "/u/76561197960287930/game/10");
    await screen.findByText("Dois");

    await userEvent.click(screen.getByRole("button", { name: "Mais raras" }));

    expect(nomesNaLista()).toEqual(["Dois", "Cinquenta", "Noventa"]);
  });

  it("manda as conquistas sem raridade para o fim, nos dois sentidos", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse({
          ...detailComRaridade,
          total_count: 4,
          achievements: [
            comRaridade("Doze", 12),
            comRaridade("SemA", null),
            comRaridade("Tres", 3),
            comRaridade("SemB", null),
          ],
        }),
      ),
    );

    renderWithProviders(<App />, "/u/76561197960287930/game/10");
    await screen.findByText("Doze");

    await userEvent.click(screen.getByRole("button", { name: "Mais raras" }));
    // As sem raridade nunca sobem, e mantêm entre si a ordem de entrada.
    expect(nomesNaLista()).toEqual(["Tres", "Doze", "SemA", "SemB"]);

    await userEvent.click(screen.getByRole("button", { name: "Mais fáceis" }));
    expect(nomesNaLista()).toEqual(["Doze", "Tres", "SemA", "SemB"]);
  });

  it("combina o filtro de aba com a ordenação", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse({
          ...detailComRaridade,
          achieved_count: 1,
          total_count: 3,
          achievements: [
            { ...comRaridade("PendRara", 5) },
            { ...comRaridade("Obtida", 50), achieved: true },
            { ...comRaridade("PendFacil", 80) },
          ],
        }),
      ),
    );

    renderWithProviders(<App />, "/u/76561197960287930/game/10");
    await screen.findByText("PendRara");

    await userEvent.click(screen.getByRole("tab", { name: "Pendentes" }));
    await userEvent.click(screen.getByRole("button", { name: "Mais fáceis" }));

    // Filtro e ordem se combinam: nenhum sobrescreve o outro.
    expect(nomesNaLista()).toEqual(["PendFacil", "PendRara"]);
  });

  it("não mostra o controle de ordenação em jogo sem raridade nenhuma", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse({
          ...detailComRaridade,
          total_count: 1,
          achievements: [comRaridade("Uma", null)],
        }),
      ),
    );

    renderWithProviders(<App />, "/u/76561197960287930/game/10");
    await screen.findByText("Uma");

    // Ordenar não mudaria nada aqui — o controle some em vez de mentir.
    expect(
      screen.queryByRole("button", { name: "Mais raras" }),
    ).not.toBeInTheDocument();
  });
});
