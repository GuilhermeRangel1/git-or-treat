export function visualValue(value: number | null, unit: string, precision = 2) {
  if (value === null) return "Sem valor disponível";
  if (unit === "R$" || unit === "BRL")
    return new Intl.NumberFormat("pt-BR", {
      style: "currency",
      currency: "BRL",
      minimumFractionDigits: precision,
      maximumFractionDigits: precision,
    }).format(value);
  return `${new Intl.NumberFormat("pt-BR", { maximumFractionDigits: precision }).format(value)} ${unit}`;
}
