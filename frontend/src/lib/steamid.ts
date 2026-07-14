// SteamID64 tem exatamente 17 dígitos. Formato apenas — existência só a Steam
// sabe, e quem responde por ela é /api/users/{id}/profile.
export const isSteamId64 = (value: string) => /^\d{17}$/.test(value);

export type SteamIdInput =
	| { kind: "steamid"; steamid: string }
	| { kind: "vanity"; vanity: string }
	| { kind: "invalid"; erro: string };

// Vocabulário do nome de perfil. Mesmo que o backend valida em /api/resolve —
// aqui poupa a ida; lá é a rede de segurança (a URL é input público).
const VANITY = /^[A-Za-z0-9_-]{2,32}$/;

// Os 17 dígitos dentro de uma URL de perfil: .../profiles/76561197960287930/…
const PROFILE_URL = /steamcommunity\.com\/profiles\/(\d{17})\b/i;
// O nome dentro de uma custom URL: .../id/gabelogannewell/…
// Composta a partir do VANITY (sem as âncoras) para as duas não divergirem.
const VANITY_URL = new RegExp(
	`steamcommunity\\.com/id/(${VANITY.source.slice(1, -1)})\\b`,
	"i",
);

/**
 * Classifica o que o usuário digitou, sem tocar a rede.
 *
 * O usuário não sabe o próprio SteamID64: ele tem o **link** ou o **nome** do
 * perfil. Quando os 17 dígitos já estão no input (crus ou dentro de
 * `/profiles/…`), extraí-los é local e de graça. Só o nome (`/id/<nome>`) exige
 * a Steam — e aí vai para o `/api/resolve`, que é o único que tem a chave.
 */
export function normalizeSteamId(value: string): SteamIdInput {
	const input = value.trim();

	const naUrl = input.match(PROFILE_URL);
	if (naUrl) return { kind: "steamid", steamid: naUrl[1] };

	if (isSteamId64(input)) return { kind: "steamid", steamid: input };

	const nomeNaUrl = input.match(VANITY_URL);
	if (nomeNaUrl) return { kind: "vanity", vanity: nomeNaUrl[1] };

	// Antes do vanity, de propósito: `1234` casa com o charset de nome, mas quem
	// digita só dígitos está tentando um SteamID64 e comeu algum. Mandá-lo à Steam
	// gastaria quota para dizer "não existe"; a resposta útil sai daqui, de graça.
	// O preço: um vanity puramente numérico nunca é resolvido.
	if (/^\d+$/.test(input)) {
		return {
			kind: "invalid",
			erro: `Um SteamID64 tem 17 dígitos — você informou ${input.length}.`,
		};
	}

	if (VANITY.test(input)) return { kind: "vanity", vanity: input };

	return {
		kind: "invalid",
		erro: "Informe o SteamID64 (17 dígitos), o link ou o nome do seu perfil.",
	};
}
