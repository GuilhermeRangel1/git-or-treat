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
const metricTypographyClass =
  "font-heading text-lg leading-6 font-semibold tracking-tight sm:text-xl sm:leading-7 lg:text-2xl lg:leading-8";

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

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <article className="grid min-h-[192px] min-w-0 content-center gap-2 rounded-xl bg-surface px-4 py-5 text-center">
      <h3 className="text-sm font-medium leading-5 text-muted">{label}</h3>
      <p
        className={`min-w-0 whitespace-nowrap ${metricTypographyClass} ${value.startsWith("-") || value.startsWith("−") ? "text-danger" : "text-content"}`}
      >
        {value}
      </p>
      {value === "Indisponível" ? (
        <p className="text-xs text-muted">A fonte não informa esta medida.</p>
      ) : null}
    </article>
  );
}

export default function RevenueSummary({
  envelope,
}: {
  envelope: RevenueEnvelope;
}) {
  const { data } = envelope;
  const final = data.comparison.final;
  const change = data.comparison.billed_amount_change_brl;
  const signStyle = signedValueTone(change);

  return (
    <section aria-labelledby="revenue-summary-title" className="min-w-0">
      <h2 id="revenue-summary-title" className="sr-only">
        Resumo da receita
      </h2>
      <div className="grid min-w-0 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Valor faturado" value={money(final.billed_amount)} />
        <MetricCard
          label="Consumo medido"
          value={energy(final.measured_energy_kwh)}
        />
        <MetricCard
          label="Preço observado"
          value={price(final.observed_price_brl_per_kwh)}
        />
        <article className="grid min-h-[192px] min-w-0 content-center gap-2 rounded-xl bg-surface px-4 py-5 text-center">
          <h3 className="text-sm font-medium leading-5 text-muted">Variação</h3>
          <p
            className={`flex min-w-0 flex-nowrap items-center justify-center gap-2 whitespace-nowrap ${metricTypographyClass} ${signStyle}`}
          >
            <span className="min-w-0">{signedMoney(change)}</span>
          </p>
        </article>
      </div>
      {data.coverage.measured_energy_kwh.status === "partial" ? (
        <p className="mt-2 text-xs text-muted">
          Consumo medido com cobertura parcial no período.
        </p>
      ) : null}
    </section>
  );
}
