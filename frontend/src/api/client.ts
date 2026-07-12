import type { components } from "./types.gen";

export type Game = components["schemas"]["Game"];
export type GameDetail = components["schemas"]["GameDetail"];
export type Achievement = components["schemas"]["Achievement"];
export type PlayerSummary = components["schemas"]["PlayerSummary"];
export type Sort =
	| "playtime"
	| "name"
	| "percent"
	| "ach_count"
	| "last_played";
export type Group = "none" | "genre";

const DEFAULT_API_BASE_URL = "/api";

export class ApiError extends Error {
	status: number;

	constructor(status: number, message: string) {
		super(message);
		this.name = "ApiError";
		this.status = status;
	}
}

async function getJSON<T>(url: string): Promise<T> {
	let resp: Response;
	try {
		resp = await fetch(url);
	} catch {
		// Falha de rede: fetch rejeita antes de qualquer resposta.
		throw new ApiError(0, "Falha de conexão com o servidor.");
	}
	if (!resp.ok) {
		// O backend devolve {detail: "mensagem pt-BR"} nos erros mapeados. Erros de
		// validação do FastAPI (422) trazem detail como array — ignoramos esses.
		let detail = `Erro ${resp.status}`;
		try {
			const body = await resp.json();
			if (typeof body?.detail === "string") detail = body.detail;
		} catch {
			/* corpo não-JSON: mantém a mensagem padrão */
		}
		throw new ApiError(resp.status, detail);
	}
	return (await resp.json()) as T;
}

export function buildApiUrl(
	path: string,
	baseUrl = import.meta.env.VITE_API_BASE_URL || DEFAULT_API_BASE_URL,
) {
	const normalizedBaseUrl = baseUrl.replace(/\/$/, "");
	const normalizedPath = path.startsWith("/") ? path : `/${path}`;
	return `${normalizedBaseUrl}${normalizedPath}`;
}

export const fetchGames = (
	steamid: string,
	sort: Sort,
	group: Group = "none",
) => {
	let url = buildApiUrl(
		`/users/${encodeURIComponent(steamid)}/games?sort=${encodeURIComponent(sort)}`,
	);
	if (group === "genre") url += "&group=genre";
	return getJSON<Game[]>(url);
};

export const fetchPlayerSummary = (steamid: string) =>
	getJSON<PlayerSummary>(
		buildApiUrl(`/users/${encodeURIComponent(steamid)}/profile`),
	);

export const fetchGameDetail = (steamid: string, appid: number) =>
	getJSON<GameDetail>(
		buildApiUrl(`/users/${encodeURIComponent(steamid)}/games/${appid}`),
	);
