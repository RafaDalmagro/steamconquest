import { describe, expect, it } from "vitest";
import { fireEvent } from "@testing-library/react";

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
});
