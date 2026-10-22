import type { RevenueEnvelope } from "./contract";

const currency = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
});
const priceCurrency = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  minimumFractionDigits: 4,
  maximumFractionDigits: 4,
});
const decimal = new Intl.NumberFormat("pt-BR", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

function money(value: number | null) {
  return value === null ? "Indisponível" : currency.format(value);
}

function energy(value: number | null) {
  return value === null ? "Indisponível" : decimal.format(value) + " kWh";
}

function price(value: number | null) {
  return value === null ? "Indisponível" : priceCurrency.format(value) + "/kWh";
}

function signedMoney(value: number | null) {
  if (value === null) return "Indisponível";
  return (
    (value < 0 ? "−" : value > 0 ? "+" : "") + currency.format(Math.abs(value))
  );
}

function signedPercent(value: number | null, eligible: boolean) {
  if (value === null || !eligible) return "Indisponível";
  return (
    (value < 0 ? "−" : value > 0 ? "+" : "") +
    decimal.format(Math.abs(value)) +
    "%"
  );
}

function MetricCard({
  label,
  value,
  before,
  competence,
  valueClassName,
}: {
  label: string;
  value: string;
  before: string;
  competence: string;
  valueClassName?: string;
}) {
  return (
    <article className="grid min-h-[192px] min-w-0 content-center gap-2 rounded-xl bg-surface px-4 py-5 text-center">
      <h3 className="text-sm text-muted">{label}</h3>
      <p
        className={`break-words font-heading ${valueClassName ?? "text-4xl"} leading-tight font-semibold tracking-tight text-content`}
      >
        {value}
      </p>
      <p className="text-xs text-muted">Antes: {before}</p>
      <p className="text-xs text-muted">Competência: {competence}</p>
    </article>
  );
}

export default function RevenueSummary({
  envelope,
}: {
  envelope: RevenueEnvelope;
}) {
  const { data } = envelope;
  const initial = data.comparison.initial;
  const final = data.comparison.final;
  const change = data.comparison.billed_amount_change_brl;
  const signStyle =
    change === null
      ? "text-muted"
      : change < 0
        ? "text-danger"
        : change > 0
          ? "text-success"
          : "text-content";

  return (
    <section aria-labelledby="revenue-summary-title" className="min-w-0">
      <h2 id="revenue-summary-title" className="sr-only">
        Resumo da receita
      </h2>
      <div className="mt-2 grid min-w-0 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          label="Valor faturado"
          value={money(final.billed_amount)}
          before={money(initial.billed_amount)}
          competence={final.competencia}
        />
        <MetricCard
          label="Energia faturada"
          value={energy(final.billed_energy_kwh)}
          before={energy(initial.billed_energy_kwh)}
          competence={final.competencia}
        />
        <MetricCard
          label="Preço observado"
          value={price(final.observed_price_brl_per_kwh)}
          before={price(initial.observed_price_brl_per_kwh)}
          competence={final.competencia}
          valueClassName="text-[32px]"
        />
        <article className="grid min-h-[192px] min-w-0 content-center gap-2 rounded-xl bg-surface px-4 py-5 text-center">
          <h3 className="text-sm text-muted">Variação</h3>
          <p
            className={
              "flex items-center justify-center gap-2 break-words font-heading text-4xl leading-tight font-semibold tracking-tight " +
              signStyle
            }
          >
            <span aria-hidden="true">
              {change === null ? "" : change > 0 ? "▲" : change < 0 ? "▼" : "▶"}
            </span>
            {signedMoney(change)}
          </p>
          <p className="text-xs text-muted">
            Competência: {initial.competencia} → {final.competencia}
          </p>
          <p className="text-xs text-muted">
            {signedPercent(
              data.comparison.billed_amount_change_percent,
              data.quality.percent_change_eligible,
            )}
          </p>
        </article>
      </div>
    </section>
  );
}
