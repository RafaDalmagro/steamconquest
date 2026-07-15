// Limiar de produto do "Quase lá": jogo com progresso alto ainda não concluído.
// Percentual (não conquistas restantes) foi a decisão de produto — ver
// spec/spec-quase-la-completion-loop.md (REQ-070/071).
const QUASE_LA_MIN = 80;

// Opera sobre o percent EXIBIDO (arredondado), a mesma fonte de verdade do card
// e do resumo — evita "80%" sem selo ou "100%" com selo. `null` (jogo sem
// conquistas) nunca é "Quase lá".
export function isQuaseLa(percent: number | null | undefined): boolean {
  if (percent == null) return false;
  const exibido = Math.round(percent);
  return exibido >= QUASE_LA_MIN && exibido < 100;
}
