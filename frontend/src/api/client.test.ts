import { afterEach, describe, expect, it, vi } from "vitest";

import { buildApiUrl } from "./client";

afterEach(() => vi.unstubAllEnvs());

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
