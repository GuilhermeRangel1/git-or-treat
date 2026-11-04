import type { ComparisonType, KpiMetric } from "../../shared/analytics/types";

type PanoramaMetricCardProps = {
  metric: KpiMetric;
  title: string;
  comparison: ComparisonType;
};

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

export default function PanoramaMetricCard({
  metric,
  title,
  comparison,
}: PanoramaMetricCardProps) {
  const variation = metric.variacaoPercentual;
  const supportsComparison = metric.id !== "ucs_atv";
  const absolute = supportsComparison ? absoluteVariation(metric) : null;

  return (
    <article
      aria-label={`${title}: ${compactValue(metric)}`}
      className="flex min-h-[168px] min-w-0 flex-col justify-center gap-2 rounded-xl bg-surface p-4 text-left lg:items-center lg:gap-3 lg:p-5 lg:text-center"
    >
      <h2 className="text-sm font-medium leading-5 text-muted">{title}</h2>
      <p className="break-words font-heading text-2xl font-semibold leading-[30px] tracking-tight text-content lg:text-[36px] lg:leading-[44px]">
        {compactValue(metric)}
      </p>
      <div className="text-xs leading-[18px]">
        {metric.valorAtual == null ? (
          <p className="text-muted">
            {metric.limitacoes?.[0] ?? "Valor não disponível nesta fonte."}
          </p>
        ) : null}
        {metric.valorAtual == null ||
        metric.id === "ucs_atv" ||
        comparison === "nenhuma" ||
        metric.valorAnterior == null ||
        variation == null ? null : (
          <p
            className={
              variation > 0
                ? "text-success"
                : variation < 0
                  ? "text-[var(--status-danger)]"
                  : "text-muted"
            }
          >
            {variation > 0 ? "+" : ""}
            {absolute ? `${absolute} · ` : ""}
            {variation.toLocaleString("pt-BR", { maximumFractionDigits: 2 })}%
          </p>
        )}
      </div>
    </article>
  );
}
