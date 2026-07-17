import { useEffect, useRef, useState, type FormEvent } from "react";
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

// Constante de produto, não config (CON-081): não varia entre deploys, não é
// segredo (vai no href, e todo VITE_* é público de qualquer forma), e uma var
// não-setada criaria um modo de falha idêntico a "o perfil ficou privado".
// Perfil verificado contra a API real em 16/07/2026: público, 155 jogos, com
// progresso de conquistas real. Ficou privado? O link some sozinho (REQ-081).
const DEMO_STEAMID = "76561198082363621";

// Card de perfil que o próprio perfil justifica: o nome e o avatar vêm da API,
// então o link só existe se o perfil existir. Falhou? Some sem alarde — vale
// tanto para o atalho de quem já consultou (o id do localStorage) quanto para a
// demo (REQ-081), e é o que impede um perfil que virou privado de entregar 404
// na cara de quem chegou agora.
function PerfilLink({ steamid, rotulo }: { steamid: string; rotulo: string }) {
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
							{rotulo}
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
	const erroRef = useRef<HTMLParagraphElement>(null);

	// Erro de submit leva o foco: sem isso, quem navega por teclado ou leitor de
	// tela fica no botão e não sabe que apareceu um texto acima dele.
	useEffect(() => {
		if (error) erroRef.current?.focus();
	}, [error]);

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

	// Centrado na vertical porque a página é só o herói: sem o "Como funciona"
	// que antes ocupava a dobra, o conteúdo encostava no topo e sobrava meia tela
	// morta embaixo. O desconto de 9rem é o header + o p-6 do <main> (App.tsx).
	return (
		<div className="flex min-h-[calc(100vh-9rem)] items-center py-10">
			<section className="grid items-center gap-10 md:grid-cols-[1.2fr_1fr]">
				<div>
					<p className="font-display text-sm uppercase tracking-[0.3em] text-primary">
						Conquistas Steam
					</p>
					{/* Nomeia o loop de completude, não a agregação (REQ-080):
					    "tudo em um lugar" é o que todo tracker promete, e arquivo
					    morto não puxa ninguém — o que puxa é o loop aberto (efeito
					    Zeigarnik, ver spec-quase-la). A promessa só é honesta
					    porque o perfil de exemplo a prova a um clique (CON-080):
					    se o link de demo cair, o título volta para agregação. */}
					<h1 className="mt-3 text-balance text-4xl font-semibold uppercase leading-tight tracking-wide sm:text-5xl">
						O que falta para o seu próximo 100%
					</h1>
					<p className="mt-4 max-w-prose text-lg text-muted-foreground">
						Veja quais jogos da sua biblioteca estão a poucas
						conquistas de fechar, quanto já jogou e o que ainda falta
						em cada um — direto da Steam, em tempo real.
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
							name="steamid"
							autoComplete="off"
							spellCheck={false}
							placeholder="steamcommunity.com/id/seu-perfil…"
							value={value}
							onChange={(e) => {
								setValue(e.target.value);
								setError(null);
							}}
						/>
						{error && (
							// tabIndex={-1} só para receber o foco programático do
							// submit — não entra na ordem de tabulação.
							<p
								ref={erroRef}
								tabIndex={-1}
								role="alert"
								className="text-sm text-destructive outline-none">
								{error}
							</p>
						)}
						<Button
							type="submit"
							variant="active"
							disabled={verificando}>
							{verificando ? "Verificando…" : "Ver biblioteca"}
						</Button>

						{/* A objeção ("por que este site quer meu perfil?") dispara
						    aqui, no campo — então a resposta mora aqui, visível, e
						    não dentro do <details> abaixo nem numa seção que só se
						    lê depois de já ter decidido. Estava sepultada no passo 1
						    do "Como funciona": respondia depois do pedido. */}
						<p className="text-xs text-muted-foreground">
							Sem login e sem senha — só dados públicos da Steam.
						</p>

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

					{/* Um alvo por visitante (REQ-081): quem já tem perfil salvo
					    veio buscar a própria biblioteca — uma demo ao lado só
					    levaria para longe dela. Quem chega sem nada não tem o que
					    continuar, e precisa é de prova. */}
					{lastSteamId ? (
						<PerfilLink steamid={lastSteamId} rotulo="Continuar como" />
					) : (
						<PerfilLink
							steamid={DEMO_STEAMID}
							rotulo="Ver um perfil de exemplo"
						/>
					)}
				</div>
			</section>
		</div>
	);
}
