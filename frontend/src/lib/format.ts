// Formatadores compartilhados. Intl é nativo: nenhuma lib de data ou de número.
const DATA = new Intl.DateTimeFormat("pt-BR", { dateStyle: "short" });
const PCT = new Intl.NumberFormat("pt-BR", {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});

/** ISO-8601 vindo da API → "dd/mm/aaaa" no fuso do navegador. */
export const formatarData = (iso: string) => DATA.format(new Date(iso));

/** 4.1 → "4,1" */
export const formatarPercentual = (valor: number) => PCT.format(valor);
