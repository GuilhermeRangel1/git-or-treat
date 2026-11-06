import type { ComparisonType, KpiMetric } from "../../shared/analytics/types";

type PanoramaMetricCardProps = {
  metric: KpiMetric;
  title: string;
  comparison: ComparisonType;
};

const STABLE_VARIATION_LIMIT_PERCENT = 0.5;
const COMPARISON_UNAVAILABLE_TEXT = "Comparação indisponível neste recorte";
const PILL_CLASS =
  "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 font-medium";

function compactValue(metric: KpiMetric) {
  const value = metric.valorAtual;
  if (value == null) return "Indisponível";
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

function percentVariation(variation: number) {
  const sign = variation < 0 ? "−" : "+";
  const absolute = Math.abs(variation).toLocaleString("pt-BR", {
    maximumFractionDigits: 2,
  });
  return `${sign}${absolute}%`;
}

function variationTrend(metric: KpiMetric, comparison: ComparisonType) {
  const variation = metric.variacaoPercentual;
  if (
    metric.id === "ucs_atv" ||
    comparison === "nenhuma" ||
    metric.valorAnterior == null ||
    variation == null
  )
    return null;
  if (Math.abs(variation) < STABLE_VARIATION_LIMIT_PERCENT)
    return {
      symbol: "●",
      text: "Estável",
      className: "bg-[var(--status-info-bg)] text-[var(--status-info-text)]",
    };

  const absolute = absoluteVariation(metric);
  const detail = `${absolute ? `${absolute} · ` : ""}${percentVariation(variation)}`;
  return variation > 0
    ? {
        symbol: "▲",
        text: `Em alta · ${detail}`,
        className:
          "bg-[var(--status-success-bg)] text-[var(--status-success-text)]",
      }
    : {
        symbol: "▼",
        text: `Em queda · ${detail}`,
        className:
          "bg-[var(--action-danger-bg)] text-[var(--action-danger-text)]",
      };
}

export default function PanoramaMetricCard({
  metric,
  title,
  comparison,
}: PanoramaMetricCardProps) {
  const hasValue = metric.valorAtual != null;
  const trend = variationTrend(metric, comparison);
  const comparisonText = trend?.text ?? COMPARISON_UNAVAILABLE_TEXT;

  return (
    <article
      aria-label={`${title}: ${compactValue(metric)}${hasValue ? `. ${comparisonText}` : ""}`}
      className="flex min-h-[168px] min-w-0 flex-col justify-center gap-2 rounded-xl bg-surface p-4 text-left lg:items-center lg:gap-3 lg:p-5 lg:text-center"
    >
      <h2 className="text-sm font-medium leading-5 text-muted">{title}</h2>
      <p className="break-words font-heading text-2xl font-semibold leading-[30px] tracking-tight text-content lg:text-[36px] lg:leading-[44px]">
        {compactValue(metric)}
      </p>
      <div className="text-xs leading-[18px]">
        {!hasValue ? (
          <p className="text-muted">
            {metric.limitacoes?.[0] ?? "Valor não disponível nesta fonte."}
          </p>
        ) : trend ? (
          <p className={`${PILL_CLASS} ${trend.className}`}>
            <span aria-hidden="true">{trend.symbol}</span> {trend.text}
          </p>
        ) : (
          <p className="text-muted">{COMPARISON_UNAVAILABLE_TEXT}</p>
        )}
      </div>
    </article>
  );
}
