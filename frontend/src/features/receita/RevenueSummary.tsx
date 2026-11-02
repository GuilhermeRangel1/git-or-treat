import type { RevenueEnvelope } from "./contract";
import { signedValueTone } from "@/shared/ui/signedValue";

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

function competenceLabel(value: string) {
  const monthNames = [
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
  return `${monthNames[Number(value.slice(5, 7)) - 1]}/${value.slice(0, 4)}`;
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
        className={`min-w-0 [overflow-wrap:anywhere] font-heading ${valueClassName ?? (value.length > 13 ? "text-2xl" : "text-3xl")} leading-tight font-semibold tracking-tight ${value.startsWith("-") || value.startsWith("−") ? "text-danger" : "text-content"}`}
      >
        {value}
      </p>
      {value !== "Indisponível" || before !== "Indisponível" ? (
        <p className="text-xs text-muted">
          Antes:{" "}
          <span
            className={
              before.startsWith("-") || before.startsWith("−")
                ? "text-danger"
                : "text-content"
            }
          >
            {before}
          </span>
        </p>
      ) : (
        <p className="text-xs text-muted">A fonte não informa esta medida.</p>
      )}
      <p className="text-xs text-muted">Mês: {competence}</p>
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
  const signStyle = signedValueTone(change);

  return (
    <section aria-labelledby="revenue-summary-title" className="min-w-0">
      <h2 id="revenue-summary-title" className="sr-only">
        Resumo da receita
      </h2>
      <div className="grid min-w-0 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          label="Valor faturado"
          value={money(final.billed_amount)}
          before={money(initial.billed_amount)}
          competence={competenceLabel(final.competencia)}
        />
        <MetricCard
          label="Energia faturada"
          value={energy(final.billed_energy_kwh)}
          before={energy(initial.billed_energy_kwh)}
          competence={competenceLabel(final.competencia)}
        />
        <MetricCard
          label="Preço observado"
          value={price(final.observed_price_brl_per_kwh)}
          before={price(initial.observed_price_brl_per_kwh)}
          competence={competenceLabel(final.competencia)}
          valueClassName="text-xl sm:text-2xl"
        />
        <article className="grid min-h-[192px] min-w-0 content-center gap-2 rounded-xl bg-surface px-4 py-5 text-center">
          <h3 className="text-sm text-muted">Variação</h3>
          <p
            className={
              "flex min-w-0 flex-wrap items-center justify-center gap-2 [overflow-wrap:anywhere] font-heading text-xl sm:text-2xl leading-tight font-semibold tracking-tight " +
              signStyle
            }
          >
            <span aria-hidden="true">
              {change === null ? "" : change > 0 ? "▲" : change < 0 ? "▼" : "▶"}
            </span>
            <span className="min-w-0">{signedMoney(change)}</span>
          </p>
          <p className="text-xs text-muted">
            Período: {competenceLabel(initial.competencia)} →{" "}
            {competenceLabel(final.competencia)}
          </p>
        </article>
      </div>
    </section>
  );
}
