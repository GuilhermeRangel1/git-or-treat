export const effectLabels: Record<string, string> = {
  preco: "Efeito-preço",
  volume: "Efeito-volume",
  interacao: "Interação preço × volume",
  entradas: "Entradas",
  saidas: "Saídas",
  sem_leitura: "Faturas sem leitura",
  outros: "Outras parcelas",
};
const currency = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
});
export function money(value: number | null | undefined) {
  return value == null ? "Indisponível" : currency.format(value);
}
export function signedMoney(value: number | null | undefined) {
  return value == null
    ? "Indisponível"
    : `${value < 0 ? "−" : value > 0 ? "+" : ""}${currency.format(Math.abs(value))}`;
}
export function percentage(value: number | null | undefined, unit = "%") {
  return value == null
    ? "Percentual indisponível"
    : `${value > 0 ? "+" : value < 0 ? "−" : ""}${Math.abs(value).toLocaleString("pt-BR", { maximumFractionDigits: 2 })}${unit}`;
}
export function windowLabel(windows: string[]) {
  const label = (value: string) =>
    new Intl.DateTimeFormat("pt-BR", {
      month: "short",
      year: "numeric",
      timeZone: "UTC",
    })
      .format(new Date(`${value}-01T00:00:00Z`))
      .replace(". de ", "/");
  return windows.length === 4
    ? `${label(windows[0])}–${label(windows[1])} vs. ${label(windows[2])}–${label(windows[3])}`
    : "Janelas não disponíveis";
}
