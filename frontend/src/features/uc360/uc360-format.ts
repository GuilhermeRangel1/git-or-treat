import type { UCStatus } from "./contract";

const limitationFieldLabels: Record<string, string> = {
  measured_energy_kwh: "consumo medido",
  billed_energy_kwh: "energia faturada",
  billed_amount: "valor faturado",
  paid_amount: "valor pago",
  current_meter: "medidor vigente",
  open_invoices: "faturas em aberto",
  competencia: "competência",
};

const moneyFormat = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
});
const decimalFormat = new Intl.NumberFormat("pt-BR", {
  maximumFractionDigits: 2,
});

export function formatUCAmount(value: number | null, unit: "BRL" | "kWh") {
  return value === null
    ? "Sem dado"
    : unit === "BRL"
      ? moneyFormat.format(value)
      : `${decimalFormat.format(value)} kWh`;
}

export function formatUCPower(value: number) {
  return `${decimalFormat.format(value)} kW`;
}

export function statusLabel(status: UCStatus) {
  return {
    available: "Disponível",
    empty: "Sem registros",
    partial: "Fonte parcial",
    unavailable: "Indisponível",
  }[status];
}

export function humanizeLimitation(text: string) {
  return text
    .replace(/\bcomparison\.(initial|final)\./g, (_, point: string) =>
      point === "initial" ? "período anterior: " : "período atual: ",
    )
    .replace(
      /\b[a-z]+(?:_[a-z0-9]+)+\b/g,
      (key) => limitationFieldLabels[key] ?? key.replaceAll("_", " "),
    );
}
