import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";

import { AchievementItem } from "@/components/AchievementItem";
import type { Achievement } from "@/api/client";
import { jsonResponse, renderWithProviders } from "@/test/utils";

const STEAMID = "76561197960287930";

const pendente: Achievement = {
  apiname: "ACH_SPA",
  display_name: "Descanso no Spa",
  name_en: "Spa Healer",
  description: null,
  icon_url: null,
  achieved: false,
  unlocked_at: null,
  global_percent: null,
};

const obtida: Achievement = { ...pendente, achieved: true };

const render = (ach: Achievement) =>
  renderWithProviders(
    <AchievementItem
      ach={ach}
      gameName="Nioh: Complete Edition"
      steamid={STEAMID}
      appid={10}
    />,
  );

afterEach(() => vi.restoreAllMocks());

describe("AchievementItem — NPC", () => {
  it("não pede a dica antes do clique", async () => {
    // AC-120. A aba "Pendentes" de um jogo grande tem ~90 itens; buscar no
    // render transformaria abrir a aba em ~90 chamadas *pagas* de uma vez.
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);

    render(pendente);

    expect(screen.getByRole("button", { name: /npc/i })).toBeTruthy();
    await new Promise((r) => setTimeout(r, 20));
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("mostra texto e fontes depois do clique", async () => {
    // AC-121. A fonte é o que permite conferir a síntese — sem ela, uma
    // alucinação e um fato têm a mesma aparência na tela.
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse({
          texto: "Use a fonte termal em Izumo.",
          fontes: [{ title: "Nioh 100%", url: "https://exemplo/guia" }],
        }),
      ),
    );

    render(pendente);
    fireEvent.click(screen.getByRole("button", { name: /npc/i }));

    await waitFor(() =>
      expect(screen.getByText(/Use a fonte termal em Izumo/)).toBeTruthy(),
    );
    const fonte = screen.getByRole("link", { name: /Nioh 100%/ });
    expect(fonte.getAttribute("href")).toBe("https://exemplo/guia");
    // SEC-112: sem noopener a página aberta ganha window.opener.
    expect(fonte.getAttribute("rel")).toContain("noopener");
  });

  it("mantém o link do YouTube ao lado da dica", () => {
    // AC-122/REQ-121. O link determinístico é o fallback de custo zero: quando a
    // IA falha, a conquista não pode voltar a não dizer *como*.
    render(pendente);

    const video = screen.getByRole("link", { name: /Como conseguir/i });
    expect(video.getAttribute("href")).toContain("Spa%20Healer");
  });

  it("não oferece dica em conquista obtida", () => {
    // AC-123. Quem já tem a conquista não tem o problema que a dica resolve —
    // e o backend devolveria 404 de qualquer forma (AC-114).
    render(obtida);

    expect(screen.queryByRole("button", { name: /npc/i })).toBeNull();
  });
});

describe("AchievementItem — interação do painel", () => {
  it("fecha o painel ao clicar de novo, sem refazer a busca", async () => {
    // Custou dinheiro: reabrir tem de vir do cache do React Query
    // (staleTime: Infinity), nunca de uma segunda chamada paga.
    const fetchSpy = vi.fn(async () =>
      jsonResponse({ texto: "Use a fonte termal.", fontes: [] }),
    );
    vi.stubGlobal("fetch", fetchSpy);

    render(pendente);
    const botao = screen.getByRole("button", { name: /npc/i });

    fireEvent.click(botao);
    await waitFor(() =>
      expect(screen.getByText(/Use a fonte termal/)).toBeTruthy(),
    );

    fireEvent.click(botao);
    expect(screen.queryByText(/Use a fonte termal/)).toBeNull();

    fireEvent.click(botao);
    await waitFor(() =>
      expect(screen.getByText(/Use a fonte termal/)).toBeTruthy(),
    );
    expect(fetchSpy).toHaveBeenCalledTimes(1);
  });

  it("aponta o botão para o painel que ele controla", () => {
    // `aria-expanded` sozinho não diz *o quê* expandiu. Sem `aria-controls`,
    // leitor de tela anuncia o estado sem conseguir levar ao conteúdo.
    render(pendente);
    const botao = screen.getByRole("button", { name: /npc/i });
    fireEvent.click(botao);

    const id = botao.getAttribute("aria-controls");
    expect(id).toBeTruthy();
    expect(document.getElementById(id!)).not.toBeNull();
  });
});

describe("AchievementItem — honestidade da persona", () => {
  it("deixa claro que quem escreveu foi um modelo", async () => {
    // A Fonte só existe porque o modelo pode errar. Se a persona apagar o sinal
    // de que é IA, o painel passa a ler como alguém que *sabe* — e a confiança
    // deixa de ser condicional. Este teste é o que impede um refactor de copy
    // de remover o único marcador que sustenta esse contrato com o usuário.
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse({
          texto: "Use a fonte termal.",
          fontes: [{ title: "Nioh 100%", url: "https://exemplo/guia" }],
        }),
      ),
    );

    render(pendente);
    fireEvent.click(screen.getByRole("button", { name: /npc/i }));

    await waitFor(() =>
      expect(screen.getByText(/Use a fonte termal/)).toBeTruthy(),
    );
    expect(screen.getByText(/modelo de IA/i)).toBeTruthy();
    expect(screen.getByText(/pode errar/i)).toBeTruthy();
  });
});

describe("AchievementItem — provedor", () => {
  it("nomeia o provedor sem perder o marcador de IA", async () => {
    // SEC-130 — trocar "modelo de IA" por "Gemini" violaria o SEC-113: quem não
    // conhece a marca lê "Gemini" como nome próprio, possivelmente o nome do
    // NPC. O provedor é informação *adicional*, nunca substituta.
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse({
          texto: "Use a fonte termal.",
          fontes: [],
          provedor: "gemini",
        }),
      ),
    );

    render(pendente);
    fireEvent.click(screen.getByRole("button", { name: /npc/i }));

    await waitFor(() =>
      expect(screen.getByText(/Use a fonte termal/)).toBeTruthy(),
    );
    expect(screen.getByText(/modelo de IA/i)).toBeTruthy();
    expect(screen.getByText(/gemini/i)).toBeTruthy();
  });
});
