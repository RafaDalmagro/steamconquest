import { afterEach, describe, expect, it, vi } from "vitest";

import { buildApiUrl, fetchGames } from "./client";
import { jsonResponse } from "@/test/utils";

afterEach(() => vi.unstubAllEnvs());

describe("fetchGames", () => {
	// A API não deduz nada: cada dado caro tem de ser pedido. O que a UI quer
	// exibir (progresso, gênero) vira `include` aqui — e só aqui.
	const urlDe = async (...args: Parameters<typeof fetchGames>) => {
		const fetchSpy = vi
			.spyOn(globalThis, "fetch")
			.mockResolvedValue(jsonResponse([]));
		await fetchGames(...args);
		const [url] = fetchSpy.mock.calls[0];
		fetchSpy.mockRestore();
		return String(url);
	};

	it("não pede nada além da biblioteca quando só ordena", async () => {
		expect(await urlDe("123", "playtime")).toBe(
			"/api/users/123/games?sort=playtime",
		);
	});

	it("pede conquistas quando a ordem depende do progresso", async () => {
		expect(await urlDe("123", "percent")).toContain("include=achievements");
		expect(await urlDe("123", "ach_count")).toContain("include=achievements");
	});

	it("pede gênero quando a UI vai agrupar por gênero", async () => {
		const url = await urlDe("123", "percent", "genre");

		expect(url).toContain("include=achievements");
		expect(url).toContain("include=genres");
	});
});

describe("buildApiUrl", () => {
	it("usa a base configurada em VITE_API_BASE_URL", () => {
		vi.stubEnv(
			"VITE_API_BASE_URL",
			"https://steamconquest-backend.onrender.com/api",
		);

		expect(buildApiUrl("/users/123/games")).toBe(
			"https://steamconquest-backend.onrender.com/api/users/123/games",
		);
	});

	it("mantém o fallback local em /api", () => {
		expect(buildApiUrl("/users/123/games")).toBe("/api/users/123/games");
	});
});
