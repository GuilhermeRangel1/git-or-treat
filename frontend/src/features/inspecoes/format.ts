export const formatNumber = (value: number) =>
  value.toLocaleString("pt-BR", { maximumFractionDigits: 2 });
export const energy = (value: number | null) =>
  value === null ? "Estimativa indisponível" : `${formatNumber(value)} kWh`;
