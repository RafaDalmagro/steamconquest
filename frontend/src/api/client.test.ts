import { afterEach, describe, expect, it, vi } from "vitest";

import { buildApiUrl, fetchDica, fetchGames, includesFor } from "./client";
import { jsonResponse } from "@/test/utils";

afterEach(() => vi.unstubAllEnvs());

describe("includesFor", () => {
	// A API não deduz nada: cada dado caro tem de ser pedido. O que a UI quer
	// exibir (progresso, gênero) vira `include` aqui — e só aqui.
	it("não pede nada além da biblioteca para ordenar pelo que já veio", () => {
		expect(includesFor("playtime", "none")).toEqual([]);
		expect(includesFor("name", "none")).toEqual([]);
		expect(includesFor("last_played", "none")).toEqual([]);
	});

	it("pede conquistas quando a ordem depende do progresso", () => {
		expect(includesFor("percent", "none")).toEqual(["achievements"]);
		expect(includesFor("ach_count", "none")).toEqual(["achievements"]);
		// Sem isto o percent vem null para todos, isQuaseLa devolve false para
		// todos, e o botão "Quase lá" não reordenaria nada.
		expect(includesFor("quase_la", "none")).toEqual(["achievements"]);
	});

	it("pede gênero quando a UI vai agrupar por gênero", () => {
		expect(includesFor("percent", "genre")).toEqual(["achievements", "genres"]);
		expect(includesFor("playtime", "genre")).toEqual(["genres"]);
	});
});

describe("fetchGames", () => {
	const urlDe = async (...args: Parameters<typeof fetchGames>) => {
		const fetchSpy = vi
			.spyOn(globalThis, "fetch")
			.mockResolvedValue(jsonResponse([]));
		await fetchGames(...args);
		const [url] = fetchSpy.mock.calls[0];
		fetchSpy.mockRestore();
		return String(url);
	};

	it("sem include, busca só a biblioteca", async () => {
		expect(await urlDe("123", [])).toBe("/api/users/123/games?");
	});

	it("repete o parâmetro include, um por dado pedido", async () => {
		expect(await urlDe("123", ["achievements", "genres"])).toBe(
			"/api/users/123/games?include=achievements&include=genres",
		);
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

describe("fetchDica", () => {
	it("codifica o apiname na URL", async () => {
		const fetchSpy = vi
			.spyOn(globalThis, "fetch")
			.mockResolvedValue(jsonResponse({ texto: "ok", fontes: [] }));

		await fetchDica("76561197960287930", 10, "ACH_SPA");

		expect(fetchSpy).toHaveBeenCalledWith(
			"/api/users/76561197960287930/games/10/achievements/ACH_SPA/dica",
		);
		fetchSpy.mockRestore();
	});
});
