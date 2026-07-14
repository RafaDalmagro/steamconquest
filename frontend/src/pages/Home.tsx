import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";

import {
	playerSummaryQuery,
	resolvedSteamIdQuery,
	usePlayerSummary,
} from "@/api/hooks";
import { Avatar } from "@/components/Avatar";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { normalizeSteamId } from "@/lib/steamid";

const STORAGE_KEY = "lastSteamId";

const PASSOS = [
	{
		titulo: "Informe seu perfil",
		texto: "Cole o link do seu perfil Steam, o nome dele ou o SteamID64. Nada de senha nem login — só o que é público.",
	},
	{
		titulo: "Veja sua biblioteca",
		texto: "Todos os jogos com tempo de jogo, ordenáveis por horas, nome, progresso ou conquistas.",
	},
	{
		titulo: "Acompanhe o progresso",
		texto: "Em cada jogo, o que já foi conquistado e o que falta, com o percentual de conclusão.",
	},
];

// Atalho para quem já consultou antes: o último id fica no localStorage e o
// perfil é buscado só para dar rosto e nome ao link. Falhou? Some sem alarde.
function ContinuarComo({ steamid }: { steamid: string }) {
	const { data: profile } = usePlayerSummary(steamid);
	if (!profile) return null;

	return (
		<Link
			to={`/u/${steamid}`}
			className="block rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background">
			<Card className="transition-colors hover:border-primary">
				<CardContent>
					<Avatar profile={profile} className="size-10" />
					<div className="min-w-0">
						<p className="text-xs uppercase tracking-widest text-muted-foreground">
							Continuar como
						</p>
						<p className="truncate font-display font-semibold">
							{profile.personaname}
						</p>
					</div>
					<span aria-hidden="true" className="ml-auto text-primary">
						›
					</span>
				</CardContent>
			</Card>
		</Link>
	);
}

export function Home() {
	const navigate = useNavigate();
	const queryClient = useQueryClient();
	const [value, setValue] = useState("");
	const [error, setError] = useState<string | null>(null);
	const [verificando, setVerificando] = useState(false);
	// Lazy: o Home re-renderiza a cada tecla digitada; o localStorage não muda.
	const [lastSteamId] = useState(() => localStorage.getItem(STORAGE_KEY) ?? "");

	// O usuário não sabe o próprio SteamID64 — ele tem o link ou o nome do perfil.
	// Três etapas, e cada uma só existe se a anterior não bastou: formato (local,
	// instantâneo), resolução do nome (só quando o ID não está no input) e
	// existência (a Steam é a única que sabe). Nada é gravado ou navegado sem tudo
	// passar — um id inexistente não pode virar o "Continuar como" da próxima visita.
	const submit = async (e: FormEvent) => {
		e.preventDefault();
		const entrada = normalizeSteamId(value);
		if (entrada.kind === "invalid") {
			setError(entrada.erro);
			return;
		}
		setError(null); // some com o erro da tentativa anterior enquanto verifica
		setVerificando(true);
		try {
			const id =
				entrada.kind === "steamid"
					? entrada.steamid
					: await queryClient.fetchQuery(
							resolvedSteamIdQuery(entrada.vanity),
						);
			// Popula o cache do React Query: a Library reaproveita, sem 2ª chamada.
			await queryClient.fetchQuery(playerSummaryQuery(id));
			localStorage.setItem(STORAGE_KEY, id);
			navigate(`/u/${id}`);
		} catch (err) {
			// detail em pt-BR do backend (404 não existe/nome não existe, 429 rate
			// limit, 502 fora do ar).
			setError((err as Error).message);
		} finally {
			setVerificando(false);
		}
	};

	return (
		<div className="flex flex-col gap-16 py-10">
			<section className="grid items-center gap-10 md:grid-cols-[1.2fr_1fr]">
				<div>
					<p className="font-display text-sm uppercase tracking-[0.3em] text-primary">
						Conquistas Steam
					</p>
					<h1 className="mt-3 text-4xl font-semibold uppercase leading-tight tracking-wide sm:text-5xl">
						Cada troféu da sua
						<br />
						biblioteca, em um lugar
					</h1>
					<p className="mt-4 max-w-prose text-lg text-muted-foreground">
						Veja quanto já jogou, quantas conquistas faltam e o quão
						perto está de 100% em cada jogo direto da Steam, em
						tempo real.
					</p>
				</div>

				<div className="flex flex-col gap-4">
					<form
						onSubmit={submit}
						className="flex flex-col gap-3 rounded-lg border border-border bg-card p-5">
						<label
							htmlFor="steamid"
							className="text-sm font-medium">
							Steam ID
						</label>
						{/* Sem inputMode="numeric": o campo aceita link e nome do
						    perfil, e um teclado numérico no celular impediria de
						    digitá-los. */}
						<Input
							id="steamid"
							autoComplete="off"
							placeholder="steamcommunity.com/id/seu-perfil"
							value={value}
							onChange={(e) => {
								setValue(e.target.value);
								setError(null);
							}}
						/>
						{error && (
							<p
								role="alert"
								className="text-sm text-destructive">
								{error}
							</p>
						)}
						<Button
							type="submit"
							variant="active"
							disabled={verificando}>
							{verificando ? "Verificando…" : "Ver biblioteca"}
						</Button>

						{/* Fallback, não caminho principal: quem já sabe o id nem
						    abre. `<details>` nativo — acessível por teclado e leitor
						    de tela sem uma linha de JS, e sem trazer um Dialog para
						    exibir três frases. Sem screenshot: print da UI da Valve
						    envelhece, e print velho é pior que texto nenhum. */}
						<details className="mt-1 text-sm text-muted-foreground">
							<summary className="cursor-pointer font-medium text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
								Não sei meu Steam ID
							</summary>
							<ol className="mt-2 list-decimal space-y-1 pl-5">
								<li>Abra a Steam (app ou site) e clique no seu nome ou avatar.</li>
								<li>
									Copie o endereço da página — algo como
									<code className="mx-1 rounded bg-muted px-1 py-0.5 text-xs">
										steamcommunity.com/id/seu-perfil
									</code>
									.
								</li>
								<li>Cole aqui. Não precisa descobrir os 17 dígitos.</li>
							</ol>
							<p className="mt-2">
								Perfil <strong>privado</strong>? A Steam não entrega a
								biblioteca para ninguém — mude para público em Privacidade,
								nas configurações do seu perfil.
							</p>
						</details>
					</form>

					{lastSteamId && <ContinuarComo steamid={lastSteamId} />}
				</div>
			</section>

			<section>
				<h2 className="font-display text-sm uppercase tracking-widest text-muted-foreground">
					Como funciona
				</h2>
				<ol className="mt-4 grid gap-4 sm:grid-cols-3">
					{PASSOS.map((passo, i) => (
						<li
							key={passo.titulo}
							className="rounded-lg border border-border bg-card p-5">
							<span className="font-display text-2xl font-semibold text-primary tabular-nums">
								{String(i + 1).padStart(2, "0")}
							</span>
							<h3 className="mt-2 font-semibold uppercase tracking-wide">
								{passo.titulo}
							</h3>
							<p className="mt-1 text-sm text-muted-foreground">
								{passo.texto}
							</p>
						</li>
					))}
				</ol>
			</section>
		</div>
	);
}
