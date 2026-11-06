import type { UCChange, UCMeasure, UCOverview, UCStatus } from "./contract";
import { signedValueTone } from "@/shared/ui/signedValue";
import {
  formatUCCompetence,
  formatUCAmount,
  humanizeLimitation,
  statusLabel,
} from "./uc360-format";

const decimal = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2 });

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
      ? "Não foi possível comparar este período"
      : `Variação: ${change.delta > 0 ? "+" : ""}${formatUCAmount(change.delta, unit)}`;
  const percent =
    change.delta === null || change.percent_change === null
      ? null
      : `${change.percent_change > 0 ? "+" : ""}${decimal.format(change.percent_change)}%`;
  const limitations = [
    ...new Set([
      ...current.limitations,
      ...before.limitations,
      ...change.limitations,
    ]),
  ];
  return (
    <article className="grid min-w-0 content-start gap-2 rounded-xl border border-control/60 bg-surface px-3 py-4 text-left sm:px-4 sm:py-5">
      <h3 className="text-sm text-muted">{title}</h3>
      <p
        className={`[overflow-wrap:anywhere] font-heading text-2xl font-semibold sm:text-3xl ${signedValueTone(current.value, false)}`}
      >
        {formatUCAmount(current.value, unit)}
      </p>
      <p className="break-words text-sm font-semibold text-muted">
        <span className={signedValueTone(change.delta)}>{delta}</span>
        {percent !== null && (
          <>
            {" · "}
            <span className={signedValueTone(change.percent_change)}>
              {percent}
            </span>
          </>
        )}
      </p>
      <p className="text-xs text-muted">
        {before.value === null
          ? "Sem valor disponível no mês inicial"
          : "Mês inicial:"}{" "}
        {before.value !== null && (
          <span className={signedValueTone(before.value, false)}>
            {formatUCAmount(before.value, unit)}
          </span>
        )}
      </p>
      <p className="text-xs text-muted">{period}</p>
      {change.status !== "available" && change.delta !== null && (
        <p className="text-xs text-muted">
          Dados da comparação: {statusLabel(change.status).toLowerCase()}
        </p>
      )}
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
    <article className="grid min-w-0 content-start gap-2 rounded-xl bg-surface p-3 text-left sm:p-4">
      <h3 className="text-sm font-medium text-muted">{title}</h3>
      <p
        className={`[overflow-wrap:anywhere] font-heading font-semibold text-content ${valueSize}`}
      >
        {value}
      </p>
      <p className="text-xs text-muted">{detail}</p>
      <p className="text-xs text-muted">{statusLabel(status)}</p>
      {limitations.length > 0 && (
        <details className="text-xs text-muted">
          <summary className="cursor-pointer">Sobre os dados</summary>
          <p className="mt-1">
            {limitations.map(humanizeLimitation).join(" ")}
          </p>
        </details>
      )}
    </article>
  );
}

export function UC360SupportMetrics({ data }: { data: UCOverview["data"] }) {
  return (
    <section
      className="grid gap-2 rounded-xl border border-control p-3 sm:p-4"
      role="region"
      aria-label="Apoio ao atendimento"
    >
      <h2 className="font-heading text-base font-semibold text-content">
        Apoio ao atendimento
      </h2>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <SummaryMetric
          title="Geração própria"
          value={
            data.gold_generation?.capacity_kwp != null
              ? `${decimal.format(data.gold_generation.capacity_kwp)} kWp`
              : data.gold_generation_record === false
                ? "Sem cadastro"
                : data.gold_generation_record === true
                  ? "Cadastro encontrado"
                  : data.distributed_generation.items.length > 0
                    ? data.distributed_generation.items
                        .map((item) => `${decimal.format(item.capacity_kw)} kW`)
                        .join(" · ")
                    : data.distributed_generation.status === "empty"
                      ? "Sem registro"
                      : "Sem dado"
          }
          detail={
            data.gold_generation_record === false
              ? "Não encontramos cadastro de geração própria para esta UC. Isso não confirma que ela não tenha painéis solares."
              : data.gold_generation?.capacity_kwp != null
                ? "A potência cadastrada não informa quanta energia foi gerada ou compensada."
                : data.gold_generation_record === true
                  ? "Há um cadastro de geração própria, mas a potência não foi informada."
                  : data.distributed_generation.items.length > 0
                    ? "A potência cadastrada não informa quanta energia foi gerada ou compensada."
                    : data.distributed_generation.status === "empty"
                      ? "Não encontramos registro de geração própria para esta UC."
                      : "Não foi possível consultar o cadastro de geração própria."
          }
          status={
            data.gold_generation_record != null
              ? "partial"
              : data.distributed_generation.status
          }
          limitations={data.distributed_generation.limitations}
        />
      </div>
    </section>
  );
}

export function UC360Comparison({
  comparison,
}: {
  comparison: UCOverview["data"]["comparison"];
}) {
  const comparisonPeriod = `${formatUCCompetence(comparison.initial.competencia)} → ${formatUCCompetence(comparison.final.competencia)}`;
  const showPaid =
    comparison.initial.paid_amount.value !== null ||
    comparison.final.paid_amount.value !== null;
  return (
    <section className="grid gap-4" aria-label="Indicadores comparativos">
      <h2 className="font-heading text-xl font-semibold text-content">
        Indicadores comparativos
      </h2>
      <div
        className="grid gap-3 rounded-xl border border-control p-3 sm:p-4"
        aria-label="Consumo e financeiro"
        role="region"
      >
        <h2 className="font-heading text-lg font-semibold text-content">
          Consumo e financeiro
        </h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Metric
            title="Consumo medido (kWh)"
            current={comparison.final.measured_energy_kwh}
            before={comparison.initial.measured_energy_kwh}
            change={comparison.measured_energy_kwh}
            unit="kWh"
            period={comparisonPeriod}
          />
          <Metric
            title="Valor faturado (BRL)"
            current={comparison.final.billed_amount}
            before={comparison.initial.billed_amount}
            change={comparison.billed_amount}
            unit="BRL"
            period={comparisonPeriod}
          />
          {showPaid && (
            <Metric
              title="Valor pago (BRL)"
              current={comparison.final.paid_amount}
              before={comparison.initial.paid_amount}
              change={comparison.paid_amount}
              unit="BRL"
              period={comparisonPeriod}
            />
          )}
        </div>
        {!showPaid && (
          <p className="text-xs text-muted">
            O valor efetivamente pago não está disponível nesta consulta.
          </p>
        )}
      </div>
    </section>
  );
}
