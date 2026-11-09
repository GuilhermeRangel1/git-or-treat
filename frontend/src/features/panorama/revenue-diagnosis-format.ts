const MONTHS = [
  "janeiro",
  "fevereiro",
  "março",
  "abril",
  "maio",
  "junho",
  "julho",
  "agosto",
  "setembro",
  "outubro",
  "novembro",
  "dezembro",
];
const CONNECTORS = new Set(["de", "da", "do", "das", "dos", "e"]);
const currency = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
});
const compactCurrency = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  notation: "compact",
  minimumFractionDigits: 0,
  maximumFractionDigits: 1,
});

function sign(value: number) {
  return value > 0 ? "+" : value < 0 ? "−" : "";
}

function monthParts(value: string) {
  const [year, month] = value.split("-");
  return { name: MONTHS[Number(month) - 1], year };
}

export function periodLabel(start: string, end: string) {
  const [from, to] = [start, end].map((value) => {
    const { name, year } = monthParts(value);
    return `${name.slice(0, 3)}/${year}`;
  });
  return `${from} – ${to}`;
}

export function fullPeriodLabel(start: string, end: string) {
  const [from, to] = [start, end].map((value) => {
    const { name, year } = monthParts(value);
    return `${name} de ${year}`;
  });
  return `${from} a ${to}`;
}

export function money(value: number) {
  return currency.format(Math.abs(value));
}

export function compactMoney(value: number) {
  const absolute = Math.abs(value);
  return (absolute < 1_000 ? currency : compactCurrency).format(absolute);
}

export function signedMoney(value: number) {
  return `${sign(value)}${money(value)}`;
}

export function signedCompactMoney(value: number) {
  return `${sign(value)}${compactMoney(value)}`;
}

export function percent(value: number) {
  return `${value.toLocaleString("pt-BR", { maximumFractionDigits: 1 })}%`;
}

export function signedPercent(value: number) {
  const absolute = Math.abs(value).toLocaleString("pt-BR", {
    maximumFractionDigits: 2,
  });
  return `${sign(value)}${absolute}%`;
}

/** A Gold publica municípios e bairros em maiúsculas; só muda a apresentação. */
export function groupLabel(value: string) {
  if (value !== value.toLocaleUpperCase("pt-BR")) return value;
  return value
    .toLocaleLowerCase("pt-BR")
    .split(" ")
    .map((word, index) =>
      index > 0 && CONNECTORS.has(word)
        ? word
        : `${word.charAt(0).toLocaleUpperCase("pt-BR")}${word.slice(1)}`,
    )
    .join(" ");
}
