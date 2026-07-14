import { describe, expect, it } from "vitest";

import { normalizeSteamId } from "./steamid";

describe("normalizeSteamId", () => {
	// O usuário não sabe o próprio SteamID64 — ele tem o link do perfil. Quando os
	// 17 dígitos já estão no que ele colou, extraí-los é uma regex: fazê-lo pedir
	// à Steam (ou ao próprio olho) seria trabalho que a máquina já fez.
	it("extrai o steamid sem tocar a rede quando os 17 dígitos já estão no input", () => {
		const entradas = [
			"76561197960287930",
			"  76561197960287930  ",
			"https://steamcommunity.com/profiles/76561197960287930",
			"steamcommunity.com/profiles/76561197960287930/",
			"https://steamcommunity.com/profiles/76561197960287930/games/?tab=all",
		];

		for (const entrada of entradas) {
			expect(normalizeSteamId(entrada), entrada).toEqual({
				kind: "steamid",
				steamid: "76561197960287930",
			});
		}
	});

	// Aqui o ID não está no input, e regex nenhuma o inventa: só a Steam sabe.
	// O nome solto vale tanto quanto o link — é o que o usuário tem na cabeça.
	it("trata o link /id/<nome> e o nome solto como vanity, a resolver na Steam", () => {
		const entradas = [
			"https://steamcommunity.com/id/gabelogannewell",
			"steamcommunity.com/id/gabelogannewell/",
			"gabelogannewell",
			"  gabelogannewell  ",
		];

		for (const entrada of entradas) {
			expect(normalizeSteamId(entrada), entrada).toEqual({
				kind: "vanity",
				vanity: "gabelogannewell",
			});
		}
	});

	// `1234` casa com o charset de vanity, mas é o erro de digitação mais provável
	// que existe (um dígito comido no copiar/colar). Mandá-lo para o /resolve
	// gastaria quota da chave para responder "perfil não encontrado" — quando a
	// mensagem certa sai de graça, aqui. O preço: um vanity só de dígitos jamais é
	// resolvido. Trade-off aceito.
	it("recusa localmente quem digitou dígitos mas não 17, dizendo quantos faltam", () => {
		const resultado = normalizeSteamId("7656119796028793"); // 16 dígitos

		expect(resultado.kind).toBe("invalid");
		expect(resultado).toMatchObject({ erro: expect.stringContaining("17 dígitos") });
	});

	it("recusa lixo sem consultar a Steam", () => {
		for (const lixo of ["", "   ", "!!!", "tem espaço", "x".repeat(33), "a"]) {
			expect(normalizeSteamId(lixo).kind, JSON.stringify(lixo)).toBe("invalid");
		}
	});
});
