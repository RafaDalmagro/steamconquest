import { describe, expect, it } from "vitest";
import { fireEvent, screen } from "@testing-library/react";

import { GameCard } from "@/components/GameCard";
import type { Game } from "@/api/client";
import { renderWithProviders } from "@/test/utils";

const game: Game = {
  appid: 10,
  name: "Portal",
  playtime_minutes: 480,
  icon_url: null,
  percent: null,
  achieved_count: null,
  total_count: null,
  genres: [],
};

describe("GameCard", () => {
  it("mostra a capa do jogo derivada do appid", () => {
    renderWithProviders(<GameCard steamid="76561197960287930" game={game} />);

    const cover = document.querySelector('img[src*="/apps/10/header.jpg"]');
    expect(cover).not.toBeNull();
  });

  it("cai para o fallback quando a capa falha ao carregar", () => {
    renderWithProviders(<GameCard steamid="76561197960287930" game={game} />);

    const cover = document.querySelector(
      'img[src*="header.jpg"]',
    ) as HTMLImageElement;
    fireEvent.error(cover);

    expect(document.querySelector('img[src*="header.jpg"]')).toBeNull();
  });

  it("formata as horas em pt-BR, igual ao resumo da biblioteca", () => {
    renderWithProviders(<GameCard steamid="76561197960287930" game={game} />);

    expect(screen.getByText("8,0 h")).toBeInTheDocument();
  });

  it("marca 'Quase lá' o jogo com progresso alto ainda não concluído", () => {
    const quase: Game = {
      ...game,
      percent: 85,
      achieved_count: 17,
      total_count: 20,
    };
    renderWithProviders(<GameCard steamid="76561197960287930" game={quase} />);

    expect(screen.getByText("Quase lá")).toBeInTheDocument();
  });

  it("no jogo 100% mostra o selo de concluído, não o 'Quase lá'", () => {
    const completo: Game = {
      ...game,
      percent: 100,
      achieved_count: 20,
      total_count: 20,
    };
    renderWithProviders(<GameCard steamid="76561197960287930" game={completo} />);

    expect(screen.getByText("✦ 100%")).toBeInTheDocument();
    expect(screen.queryByText("Quase lá")).not.toBeInTheDocument();
  });

  it("não marca 'Quase lá' abaixo do limiar nem sem dados de conquista", () => {
    const abaixo: Game = { ...game, percent: 79, achieved_count: 15, total_count: 19 };
    const { unmount } = renderWithProviders(
      <GameCard steamid="76561197960287930" game={abaixo} />,
    );
    expect(screen.queryByText("Quase lá")).not.toBeInTheDocument();
    unmount();

    // game base tem percent: null (jogo sem sistema de conquistas).
    renderWithProviders(<GameCard steamid="76561197960287930" game={game} />);
    expect(screen.queryByText("Quase lá")).not.toBeInTheDocument();
  });
});
