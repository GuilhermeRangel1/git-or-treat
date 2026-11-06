import { formatNumber } from "./operation-format";

export type Trend = "worse" | "better" | "flat" | "none";

export type Variation = {
  trend: Exclude<Trend, "none">;
  /** Texto curto para o tooltip do gráfico. */
  short: string;
  /** Frase completa para leitores de tela. */
  sentence: string;
};

// Mesmo arredondamento usado para exibir os valores (3 casas), para que dois
// meses que aparecem iguais na tela não sejam tratados como piora ou melhora.
const round = (value: number) => Math.round(value * 1000) / 1000;

/**
 * Compara um mês com o mês imediatamente anterior. Em DEC e FEC, valor maior
 * é pior. Sem valor em um dos dois meses não há comparação.
 */
export function trendOf(value: number | null, previous: number | null): Trend {
  if (value === null || previous === null) return "none";
  const current = round(value);
  const before = round(previous);
  if (current > before) return "worse";
  if (current < before) return "better";
  return "flat";
}

export function describeVariation(
  value: number | null,
  previous: number | null,
  unit: string,
): Variation | null {
  const trend = trendOf(value, previous);
  if (trend === "none" || value === null || previous === null) return null;
  if (trend === "flat") {
    return {
      trend,
      short: "● sem variação vs mês anterior",
      sentence: "sem variação em relação ao mês anterior",
    };
  }
  const delta = round(value - previous);
  const amount =
    previous > 0
      ? `${formatNumber((Math.abs(delta) / previous) * 100, 1)}%`
      : `${formatNumber(Math.abs(delta))} ${unit}`;
  const arrow = delta > 0 ? "▲" : "▼";
  const sign = delta > 0 ? "+" : "−";
  return {
    trend,
    short: `${arrow} ${sign}${amount} vs mês anterior`,
    sentence: `${trend === "worse" ? "piorou" : "melhorou"} ${amount} em relação ao mês anterior`,
  };
}
