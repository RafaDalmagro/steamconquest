import type { components, paths } from "./types.gen";

export type Game = components["schemas"]["Game"];
export type GameDetail = components["schemas"]["GameDetail"];
export type Achievement = components["schemas"]["Achievement"];
export type PlayerSummary = components["schemas"]["PlayerSummary"];
export type ResolvedProfile = components["schemas"]["ResolvedProfile"];

// Vem do OpenAPI, não de uma união escrita à mão: sort novo no backend vira erro
// de tipo aqui até a UI tratá-lo. `npm run generate:api` é o que sincroniza.
type GamesQuery = paths["/api/users/{steamid}/games"]["get"]["parameters"]["query"];
export type Sort = NonNullable<NonNullable<GamesQuery>["sort"]>;

// Não vem da API: é o estado de agrupamento da *UI*. A API só *inclui* o gênero
// (`include=genres`); quem agrupa de fato é a Library, client-side.
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

// A API não deduz o que buscar: quem pede declara. Ordenar por progresso exige o
// dado de conquistas, e agrupar por gênero exige o gênero — a tradução de intenção
// da UI para os dados caros mora aqui, num lugar só.
export const fetchGames = (
	steamid: string,
	sort: Sort,
	group: Group = "none",
) => {
	const params = new URLSearchParams({ sort });
	if (sort === "percent" || sort === "ach_count")
		params.append("include", "achievements");
	if (group === "genre") params.append("include", "genres");

	return getJSON<Game[]>(
		buildApiUrl(`/users/${encodeURIComponent(steamid)}/games?${params}`),
	);
};

// Só o backend resolve um nome de perfil: a chamada exige a STEAM_API_KEY, e o
// SPA nunca fala com a Steam. Quando o input já traz os 17 dígitos, ninguém passa
// por aqui — a extração é local (ver normalizeSteamId).
export const fetchResolvedSteamId = (vanity: string) =>
	getJSON<ResolvedProfile>(
		buildApiUrl(`/resolve?vanity=${encodeURIComponent(vanity)}`),
	).then((r) => r.steamid);

export const fetchPlayerSummary = (steamid: string) =>
	getJSON<PlayerSummary>(
		buildApiUrl(`/users/${encodeURIComponent(steamid)}/profile`),
	);

export const fetchGameDetail = (steamid: string, appid: number) =>
	getJSON<GameDetail>(
		buildApiUrl(`/users/${encodeURIComponent(steamid)}/games/${appid}`),
	);
