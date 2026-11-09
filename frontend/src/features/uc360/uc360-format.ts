import type { UCStatus, UCMeter } from "./contract";

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

export function formatUCCompetence(value: string) {
  const match = /^(\d{4})-(\d{2})$/.exec(value);
  return match ? `${match[2]}/${match[1]}` : value;
}

export function formatUCDate(value: string) {
  const match = /^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}:\d{2}))?/.exec(value);
  if (!match) return value;
  const date = `${match[3]}/${match[2]}/${match[1]}`;
  return match[4] ? `${date} · ${match[4]}` : date;
}

export function currentMeterMessage(meter: UCMeter | null, status?: UCStatus) {
  if (meter) {
    const removed = meter.removed_at
      ? `, retirado em ${formatUCDate(meter.removed_at)}`
      : "";
    if (status === "partial")
      return `Possível vínculo com o medidor ${meter.meter_id}, instalado em ${formatUCDate(meter.installed_at)}${removed}. As datas disponíveis não confirmam se este é o medidor atual.`;
    if (meter.removed_at)
      return `O cadastro informa que o medidor ${meter.meter_id} foi instalado em ${formatUCDate(meter.installed_at)} e retirado em ${formatUCDate(meter.removed_at)}.`;
    return `Medidor indicado como atual no cadastro: ${meter.meter_id}, instalado em ${formatUCDate(meter.installed_at)}.`;
  }
  switch (status) {
    case "empty":
      return "O cadastro consultado não informa um medidor atual para esta UC.";
    case "partial":
      return "Não foi possível identificar com segurança o medidor atual.";
    case "unavailable":
      return "Não foi possível consultar qual medidor está instalado atualmente.";
    case "available":
      return "O cadastro consultado não informou qual medidor está instalado atualmente.";
    default:
      return "Não há informação sobre o medidor atual nesta consulta.";
  }
}

export function statusLabel(status: UCStatus) {
  return {
    available: "Dados disponíveis",
    empty: "Nenhum registro",
    partial: "Informação parcial",
    unavailable: "Não disponível",
  }[status];
}

export function humanizeLimitation(text: string) {
  return text
    .replace(
      /Detalhe não fornecido nos CSVs Gold desta versão/gi,
      "Detalhe não informado nesta consulta",
    )
    .replace(/\bGold(?: CSV)?\b/gi, "fonte de dados")
    .replace(/\bcomparison\.(initial|final)\./g, (_, point: string) =>
      point === "initial" ? "período anterior: " : "período atual: ",
    )
    .replace(
      /\b[a-z]+(?:_[a-z0-9]+)+\b/g,
      (key) => limitationFieldLabels[key] ?? key.replaceAll("_", " "),
    );
}
