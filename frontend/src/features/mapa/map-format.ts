import type { MapLayer } from "./map-state";

const MONTHS = [
  "Jan",
  "Fev",
  "Mar",
  "Abr",
  "Mai",
  "Jun",
  "Jul",
  "Ago",
  "Set",
  "Out",
  "Nov",
  "Dez",
];

const money = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  maximumFractionDigits: 2,
});
const energy = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2 });
const compactMoney = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  notation: "compact",
  compactDisplay: "short",
  minimumFractionDigits: 0,
  maximumFractionDigits: 1,
});
const compactEnergy = new Intl.NumberFormat("pt-BR", {
  notation: "compact",
  compactDisplay: "short",
  minimumFractionDigits: 0,
  maximumFractionDigits: 1,
});

export function formatCompetence(competencia: string) {
  const match = /^(\d{4})-(\d{2})$/.exec(competencia);
  if (!match) return competencia;
  const month = Number(match[2]);
  if (month < 1 || month > 12) return competencia;
  return `${MONTHS[month - 1]}/${match[1]}`;
}

export function formatPeriod(start: string, end: string) {
  return `${formatCompetence(start)} a ${formatCompetence(end)}`;
}

export function moneyValue(value: number | null) {
  return value === null ? "Indisponível" : money.format(value);
}

export function energyValue(value: number | null) {
  return value === null ? "Indisponível" : `${energy.format(value)} kWh`;
}

function sign(value: number) {
  return value > 0 ? "+" : value < 0 ? "−" : "";
}

export function signedMoney(value: number | null) {
  if (value === null) return "Indisponível";
  return `${sign(value)}${money.format(Math.abs(value))}`;
}

export function signedEnergy(value: number | null) {
  if (value === null) return "Indisponível";
  return `${sign(value)}${energy.format(Math.abs(value))} kWh`;
}

const normalizeName = (text: string) =>
  text
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toUpperCase()
    .trim();

/**
 * Os rótulos de bairro chegam como "MUNICÍPIO / BAIRRO". Dentro do painel do
 * município o prefixo só repete o título; se não for o mesmo município, o
 * rótulo fica como veio.
 */
export function neighborhoodLabel(label: string, municipalityName: string) {
  const separator = label.indexOf(" / ");
  if (separator < 0) return label;
  return normalizeName(label.slice(0, separator)) ===
    normalizeName(municipalityName)
    ? label.slice(separator + 3).trim() || label
    : label;
}

const isRevenue = (layer: MapLayer) =>
  layer === "revenue" || layer === "revenue_change";

/** Valor completo da camada (R$ ou kWh), com sinal nas camadas de variação. */
export function layerValue(value: number, layer: MapLayer) {
  if (layer.endsWith("change"))
    return isRevenue(layer) ? signedMoney(value) : signedEnergy(value);
  return isRevenue(layer) ? moneyValue(value) : energyValue(value);
}

/** Valor resumido para espaços pequenos (legenda); o valor completo vai em `title`. */
export function compactLayerValue(value: number, layer: MapLayer) {
  const text = isRevenue(layer)
    ? compactMoney.format(Math.abs(value))
    : `${compactEnergy.format(Math.abs(value))} kWh`;
  return layer.endsWith("change") ? `${sign(value)}${text}` : text;
}
