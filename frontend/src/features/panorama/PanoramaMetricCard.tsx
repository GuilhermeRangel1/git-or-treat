import type { ComparisonType, KpiMetric } from "../../shared/analytics/types";

type PanoramaMetricCardProps = {
  metric: KpiMetric;
  title: string;
  period: string;
  comparison: ComparisonType;
  comparisonUnavailable?: boolean;
};

function compactValue(metric: KpiMetric) {
  const value = metric.valorAtual;
  if (metric.unidade === "R$") {
    if (Math.abs(value) >= 1_000_000)
      return `R$ ${(value / 1_000_000).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} mi`;
    if (Math.abs(value) >= 1_000)
      return `R$ ${(value / 1_000).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} mil`;
    return new Intl.NumberFormat("pt-BR", {
      style: "currency",
      currency: "BRL",
      maximumFractionDigits: 2,
    }).format(value);
  }
  if (metric.unidade === "kWh") {
    if (Math.abs(value) >= 1_000_000)
      return `${(value / 1_000_000).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} GWh`;
    if (Math.abs(value) >= 1_000)
      return `${(value / 1_000).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} MWh`;
  }
  return `${value.toLocaleString("pt-BR", { maximumFractionDigits: 2 })} ${metric.unidade}`;
}

function absoluteVariation(metric: KpiMetric) {
  const difference = metric.variacaoAbsoluta;
  if (difference == null) return null;
  const sign = difference < 0 ? "−" : "+";
  const absolute = Math.abs(difference);
  if (metric.unidade === "R$") {
    const value =
      absolute >= 1_000_000
        ? `${(absolute / 1_000_000).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} mi`
        : absolute >= 1_000
          ? `${(absolute / 1_000).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} mil`
          : absolute.toLocaleString("pt-BR", { maximumFractionDigits: 0 });
    return `${sign}R$ ${value}`;
  }
  if (metric.unidade === "kWh" && absolute >= 1_000)
    return `${sign}${(absolute / 1_000).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} MWh`;
  return `${sign}${absolute.toLocaleString("pt-BR", { maximumFractionDigits: 0 })} ${metric.unidade}`;
}

function periodLabel(period: string) {
  const [year, month] = period.split("-");
  const months = [
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
  return `${months[Number(month) - 1]}/${year}`;
}

export default function PanoramaMetricCard({
  metric,
  title,
  period,
  comparison,
  comparisonUnavailable = false,
}: PanoramaMetricCardProps) {
  const variation = metric.variacaoPercentual;
  const supportsComparison = metric.id === "rec_fat" || metric.id === "ene_fat";
  const isMeaningfulDecline =
    supportsComparison &&
    variation != null &&
    variation < 0 &&
    metric.bomSentido === "positivo";
  const description =
    metric.id === "ene_con"
      ? "Grandeza distinta da faturada"
      : metric.id === "ucs_atv"
        ? "Base sintética do cenário"
        : null;
  const absolute = supportsComparison ? absoluteVariation(metric) : null;

  return (
    <article
      aria-label={`${title}: ${compactValue(metric)}`}
      className="flex min-h-[132px] min-w-0 flex-col justify-center gap-2 rounded-xl bg-surface p-3 text-left lg:min-h-48 lg:items-center lg:gap-3 lg:p-6 lg:text-center"
    >
      <h2 className="text-sm font-medium leading-5 text-muted">{title}</h2>
      <p className="break-words font-heading text-2xl font-semibold leading-[30px] tracking-tight text-content lg:text-[36px] lg:leading-[44px]">
        {compactValue(metric)}
      </p>
      <div className="text-xs leading-[18px]">
        {description ? (
          <p className="text-muted">{description}</p>
        ) : comparisonUnavailable ? (
          <p className="text-muted">
            Comparação indisponível · período incompleto
          </p>
        ) : metric.baseZero ? (
          <p className="text-muted">N/D · Base anterior zero</p>
        ) : supportsComparison && variation != null ? (
          <p
            className={
              isMeaningfulDecline ? "text-[var(--status-danger)]" : "text-muted"
            }
          >
            {variation > 0 ? "+" : ""}
            {absolute ? `${absolute} · ` : ""}
            {variation.toLocaleString("pt-BR", { maximumFractionDigits: 2 })}%
          </p>
        ) : (
          <p className="text-muted">
            {comparison === "nenhuma"
              ? "Sem comparação"
              : metric.valorAnterior == null
                ? "Sem dados no período de comparação"
                : "Comparação indisponível"}
          </p>
        )}
      </div>
      <span className="font-mono text-xs text-muted">
        {periodLabel(period)}
      </span>
    </article>
  );
}
