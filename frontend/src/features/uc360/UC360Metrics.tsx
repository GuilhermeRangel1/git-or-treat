import type { UCChange, UCMeasure, UCOverview, UCStatus } from "./contract";
import {
  formatUCAmount,
  humanizeLimitation,
  statusLabel,
} from "./uc360-format";

const decimal = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2 });

function changeTone(value: number | null) {
  if (value === null || value === 0) return "text-muted";
  return value > 0
    ? "text-[var(--status-success)]"
    : "text-[var(--accent-goiaba)]";
}

function Metric({
  title,
  current,
  before,
  change,
  unit,
  period,
}: {
  title: string;
  current: UCMeasure;
  before: UCMeasure;
  change: UCChange;
  unit: "BRL" | "kWh";
  period: string;
}) {
  const delta =
    change.delta === null
      ? "Variação indisponível"
      : `${change.delta > 0 ? "+" : ""}${formatUCAmount(change.delta, unit)}`;
  const percent =
    change.percent_change === null
      ? "Percentual indisponível"
      : `${change.percent_change > 0 ? "+" : ""}${decimal.format(change.percent_change)}%`;
  const limitations = [
    ...new Set([
      ...current.limitations,
      ...before.limitations,
      ...change.limitations,
    ]),
  ];
  return (
    <article className="grid min-w-0 min-h-40 content-center gap-2 rounded-xl bg-surface px-3 py-4 text-center sm:px-4 sm:py-5">
      <h3 className="text-sm text-muted">{title}</h3>
      <p className="break-words font-heading text-xl font-semibold text-content sm:text-2xl xl:text-3xl">
        {formatUCAmount(current.value, unit)}
      </p>
      <p className="text-xs text-muted">
        Anterior: {formatUCAmount(before.value, unit)}
      </p>
      <p className="break-words text-xs font-medium text-muted sm:text-sm">
        <span className={changeTone(change.delta)}>{delta}</span> ·{" "}
        <span className={changeTone(change.percent_change)}>{percent}</span>
      </p>
      <p className="text-xs text-muted">
        {period} · atual: {statusLabel(current.status)} · anterior:{" "}
        {statusLabel(before.status)}
      </p>
      <p className="text-xs text-muted">
        Comparação: {statusLabel(change.status)}
      </p>
      {limitations.length > 0 && (
        <p className="text-xs text-muted">
          {limitations.map(humanizeLimitation).join(" ")}
        </p>
      )}
    </article>
  );
}

function SummaryMetric({
  title,
  value,
  detail,
  status,
  limitations = [],
}: {
  title: string;
  value: string;
  detail: string;
  status: UCStatus;
  limitations?: string[];
}) {
  const valueSize = /\d/.test(value)
    ? value.length > 15
      ? "text-lg sm:text-2xl"
      : "text-[28px] leading-8 lg:text-4xl lg:leading-10"
    : "text-xl sm:text-2xl";
  return (
    <article className="grid min-w-0 min-h-36 content-center gap-2 rounded-xl bg-surface p-3 text-left md:text-center sm:min-h-48 sm:p-5">
      <h3 className="text-sm font-medium text-muted">{title}</h3>
      <p
        className={`break-words font-heading font-semibold text-content ${valueSize}`}
      >
        {value}
      </p>
      <p className="text-xs text-muted">{detail}</p>
      <p className="text-xs text-muted">{statusLabel(status)}</p>
      {limitations.length > 0 && (
        <details className="text-xs text-muted">
          <summary className="cursor-pointer">Limites da fonte</summary>
          <p className="mt-1">
            {limitations.map(humanizeLimitation).join(" ")}
          </p>
        </details>
      )}
    </article>
  );
}

export function UC360SummaryMetrics({ data }: { data: UCOverview["data"] }) {
  const { comparison } = data;
  return (
    <section
      className="grid grid-cols-2 gap-3 lg:gap-4 xl:grid-cols-4"
      aria-labelledby="uc-primary-indicators-title"
    >
      <h2 id="uc-primary-indicators-title" className="sr-only">
        Indicadores principais da unidade
      </h2>
      <SummaryMetric
        title="Consumo recente"
        value={formatUCAmount(
          comparison.final.measured_energy_kwh.value,
          "kWh",
        )}
        detail={`${comparison.final.competencia} · Anterior: ${formatUCAmount(comparison.initial.measured_energy_kwh.value, "kWh")} (${comparison.initial.competencia})`}
        status={comparison.final.measured_energy_kwh.status}
        limitations={comparison.final.measured_energy_kwh.limitations}
      />
      <SummaryMetric
        title="Valor faturado"
        value={formatUCAmount(comparison.final.billed_amount.value, "BRL")}
        detail={`${comparison.final.competencia} · Anterior: ${formatUCAmount(comparison.initial.billed_amount.value, "BRL")} (${comparison.initial.competencia})`}
        status={comparison.final.billed_amount.status}
        limitations={comparison.final.billed_amount.limitations}
      />
      <SummaryMetric
        title="Faturas em aberto"
        value={data.open_invoices.count?.toLocaleString("pt-BR") ?? "Sem dado"}
        detail={`${data.period.start} a ${data.period.end} · contagem, sem saldo ou atraso`}
        status={data.open_invoices.status}
        limitations={data.open_invoices.limitations}
      />
      <SummaryMetric
        title="Geração própria"
        value={
          data.distributed_generation.items.length > 0
            ? data.distributed_generation.items
                .map((item) => `${decimal.format(item.capacity_kw)} kW`)
                .join(" · ")
            : data.distributed_generation.status === "empty"
              ? "Sem cadastro"
              : "Sem dado"
        }
        detail="Potência cadastrada em kW; não é energia compensada."
        status={data.distributed_generation.status}
        limitations={data.distributed_generation.limitations}
      />
    </section>
  );
}

export function UC360Comparison({
  comparison,
}: {
  comparison: UCOverview["data"]["comparison"];
}) {
  const comparisonPeriod = `${comparison.initial.competencia} → ${comparison.final.competencia}`;
  return (
    <section
      className="grid grid-cols-2 gap-3 xl:grid-cols-4"
      aria-labelledby="uc-comparison-title"
    >
      <h2
        id="uc-comparison-title"
        className="col-span-full font-heading text-lg font-semibold text-content"
      >
        Comparação entre competências
      </h2>
      <Metric
        title="Consumo medido"
        current={comparison.final.measured_energy_kwh}
        before={comparison.initial.measured_energy_kwh}
        change={comparison.measured_energy_kwh}
        unit="kWh"
        period={comparisonPeriod}
      />
      <Metric
        title="Energia faturada"
        current={comparison.final.billed_energy_kwh}
        before={comparison.initial.billed_energy_kwh}
        change={comparison.billed_energy_kwh}
        unit="kWh"
        period={comparisonPeriod}
      />
      <Metric
        title="Valor faturado"
        current={comparison.final.billed_amount}
        before={comparison.initial.billed_amount}
        change={comparison.billed_amount}
        unit="BRL"
        period={comparisonPeriod}
      />
      <Metric
        title="Valor pago"
        current={comparison.final.paid_amount}
        before={comparison.initial.paid_amount}
        change={comparison.paid_amount}
        unit="BRL"
        period={comparisonPeriod}
      />
    </section>
  );
}
