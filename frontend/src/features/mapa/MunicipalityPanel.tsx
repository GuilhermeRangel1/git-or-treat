import { useNavigate } from "react-router-dom";
import type { RevenueEnvelope } from "@/shared/analytics/revenueContract";
import type { TerritoryMunicipality } from "./municipalities";
import Button from "@/shared/ui/Button";
import { signedValueTone } from "@/shared/ui/signedValue";
import type { MapLayer, MapQuery } from "./map-state";

const money = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  maximumFractionDigits: 2,
});
const energy = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2 });
const competenceMonths = [
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

function formatCompetence(competencia: string) {
  const match = /^(\d{4})-(\d{2})$/.exec(competencia);
  if (!match) return competencia;
  const month = Number(match[2]);
  if (month < 1 || month > 12) return competencia;
  return `${competenceMonths[month - 1]}/${match[1]}`;
}

function formatPeriod(start: string, end: string) {
  return `${formatCompetence(start)} a ${formatCompetence(end)}`;
}

function moneyValue(value: number | null) {
  return value === null ? "Indisponível" : money.format(value);
}

function energyValue(value: number | null) {
  return value === null ? "Indisponível" : `${energy.format(value)} kWh`;
}

function signedMoney(value: number | null) {
  if (value === null) return "Indisponível";
  return `${value > 0 ? "+" : value < 0 ? "−" : ""}${money.format(Math.abs(value))}`;
}

function signedEnergy(value: number | null) {
  if (value === null) return "Indisponível";
  const sign = value > 0 ? "+" : value < 0 ? "−" : "";
  return `${sign}${energy.format(Math.abs(value))} kWh`;
}

function Metric({
  label,
  initial,
  final,
  change,
  format,
  formatChange,
}: {
  label: string;
  initial: number | null;
  final: number | null;
  change: number | null;
  format: (value: number | null) => string;
  formatChange: (value: number | null) => string;
}) {
  return (
    <div className="rounded-lg border border-border p-3">
      <h3 className="text-xs font-medium text-muted">{label}</h3>
      <dl className="mt-2 grid grid-cols-2 gap-x-3 gap-y-2 text-sm">
        <div>
          <dt className="text-xs text-muted">Inicial</dt>
          <dd className="mt-0.5 font-medium tabular-nums text-content">
            {format(initial)}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-muted">Final</dt>
          <dd className="mt-0.5 font-medium tabular-nums text-content">
            {format(final)}
          </dd>
        </div>
        <div className="col-span-2">
          <dt className="text-xs text-muted">Variação absoluta</dt>
          <dd
            className={`mt-0.5 font-semibold tabular-nums ${signedValueTone(change)}`}
          >
            {formatChange(change)}
          </dd>
        </div>
      </dl>
    </div>
  );
}

function Neighborhoods({ envelope }: { envelope: RevenueEnvelope }) {
  const rows = envelope.data.breakdown.items;
  const comparable = rows.filter(
    (row) =>
      row.comparison.initial.billed_amount !== null &&
      row.comparison.final.billed_amount !== null,
  );
  const incomplete = rows.filter(
    (row) =>
      row.comparison.initial.billed_amount === null ||
      row.comparison.final.billed_amount === null,
  );
  const rec = envelope.data.breakdown.reconciliation;
  return (
    <section
      aria-label="Bairros e contribuição para a variação do faturamento"
      className="mt-4 min-w-0"
    >
      <h3 className="font-heading text-sm font-semibold text-content">
        Bairros · faturamento
      </h3>
      <p className="mt-1 text-xs leading-5 text-muted">
        Variações conhecidas não representam reconciliação completa quando há
        bairros sem comparação ou valor residual.
      </p>
      <div className="mt-2 max-h-64 overflow-auto rounded-lg border border-border">
        <table className="w-full min-w-[430px] border-collapse text-left text-xs">
          <caption className="sr-only">
            Faturamento inicial, final e variação absoluta por bairro
          </caption>
          <thead className="sticky top-0 bg-surface text-muted">
            <tr>
              <th className="px-3 py-2 font-medium">Bairro</th>
              <th className="px-3 py-2 text-right font-medium">Inicial</th>
              <th className="px-3 py-2 text-right font-medium">Final</th>
              <th className="px-3 py-2 text-right font-medium">Variação</th>
            </tr>
          </thead>
          <tbody>
            {comparable.map((row) => (
              <tr key={row.key} className="border-t border-border">
                <th scope="row" className="px-3 py-2 font-medium text-content">
                  {row.label}
                </th>
                <td className="px-3 py-2 text-right tabular-nums text-content">
                  {moneyValue(row.comparison.initial.billed_amount)}
                </td>
                <td className="px-3 py-2 text-right tabular-nums text-content">
                  {moneyValue(row.comparison.final.billed_amount)}
                </td>
                <td
                  className={`px-3 py-2 text-right tabular-nums ${signedValueTone(row.comparison.billed_amount_change_brl)}`}
                >
                  {signedMoney(row.comparison.billed_amount_change_brl)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {incomplete.length ? (
        <div className="mt-3 rounded-lg border border-control/50 p-3">
          <h4 className="text-xs font-semibold text-content">
            Sem comparação nos dois extremos ({incomplete.length})
          </h4>
          <ul className="mt-1 list-inside list-disc text-xs text-muted">
            {incomplete.map((row) => (
              <li key={row.key}>
                {row.label} · faturamento indisponível em pelo menos um extremo
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {rec.limitations.length ? (
        <ul className="mt-2 list-inside list-disc text-xs leading-5 text-muted">
          {rec.limitations.map((limitation) => (
            <li key={limitation}>{limitation}</li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}

export default function MunicipalityPanel({
  municipality,
  item,
  detail,
  detailError,
  query,
  layer,
  revenueHref,
  onRetryDetail,
}: {
  municipality: TerritoryMunicipality | null;
  item: RevenueEnvelope["data"]["breakdown"]["items"][number] | null;
  detail: RevenueEnvelope | undefined;
  detailError: boolean;
  query: MapQuery | null;
  layer: MapLayer;
  revenueHref: string | null;
  onRetryDetail: () => void;
}) {
  const navigate = useNavigate();
  if (!municipality) {
    return (
      <section className="rounded-xl border border-border bg-surface p-5">
        <h2 className="font-heading text-lg font-semibold text-content">
          Selecione um município
        </h2>
        <p className="mt-2 text-sm leading-6 text-muted">
          Escolha um contorno no mapa ou um município na lista para consultar
          seus meses e bairros.
        </p>
      </section>
    );
  }
  const row = item;
  const comparison = row?.comparison ?? detail?.data.comparison;
  const monthCaption = query
    ? formatPeriod(query.competencia_inicio, query.competencia_fim)
    : "período selecionado";
  return (
    <section
      className="min-w-0 rounded-xl border border-border bg-surface p-4 sm:p-5"
      aria-label={`Detalhe de ${municipality.name}`}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-muted">
            Município selecionado
          </p>
          <h2 className="mt-1 font-heading text-xl font-semibold text-content">
            {municipality.name}
          </h2>
          <p className="mt-1 font-mono text-[11px] text-muted">
            IBGE {municipality.code} · {monthCaption}
          </p>
        </div>
        {revenueHref ? (
          <Button variant="primary" onClick={() => navigate(revenueHref)}>
            Investigar na Receita
          </Button>
        ) : (
          <span className="text-xs text-muted">
            Detalhe não disponível nesta publicação
          </span>
        )}
      </div>
      {!row && !detail ? (
        <p
          role="status"
          className="mt-4 rounded-lg border border-control/50 p-3 text-sm text-muted"
        >
          Este município oficial não tem linha analítica correspondente nesta
          publicação. A ausência não representa faturamento ou consumo zero.
        </p>
      ) : null}
      {comparison ? (
        <>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <Metric
              label="Faturamento · R$"
              initial={comparison.initial.billed_amount}
              final={comparison.final.billed_amount}
              change={comparison.billed_amount_change_brl}
              format={moneyValue}
              formatChange={signedMoney}
            />
            <Metric
              label="Consumo medido · kWh"
              initial={comparison.initial.measured_energy_kwh}
              final={comparison.final.measured_energy_kwh}
              change={comparison.measured_energy_change_kwh}
              format={energyValue}
              formatChange={signedEnergy}
            />
          </div>
          <section
            className="mt-4"
            aria-label={`Série mensal de ${municipality.name}`}
          >
            <h3 className="font-heading text-sm font-semibold text-content">
              Série mensal · faturamento e consumo medido
            </h3>
            <div className="mt-2 max-h-60 overflow-auto rounded-lg border border-border">
              <table className="w-full min-w-[380px] border-collapse text-left text-xs">
                <caption className="sr-only">
                  Série mensal do município selecionado
                </caption>
                <thead className="sticky top-0 bg-surface text-muted">
                  <tr>
                    <th className="px-3 py-2 font-medium">Competência</th>
                    <th className="px-3 py-2 text-right font-medium">
                      Faturamento
                    </th>
                    <th className="px-3 py-2 text-right font-medium">
                      Consumo medido
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {(detail?.data.series ?? []).map((month) => (
                    <tr
                      key={month.competencia}
                      className="border-t border-border"
                    >
                      <th
                        scope="row"
                        className="px-3 py-2 font-medium text-content"
                      >
                        {formatCompetence(month.competencia)}
                      </th>
                      <td className="px-3 py-2 text-right tabular-nums text-content">
                        {moneyValue(month.billed_amount)}
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums text-content">
                        {energyValue(month.measured_energy_kwh)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {detailError ? (
              <div
                role="alert"
                className="mt-2 flex flex-wrap items-center justify-between gap-2 text-xs text-danger"
              >
                <span>Não foi possível carregar a série e os bairros.</span>
                <Button variant="outline" size="sm" onClick={onRetryDetail}>
                  Tentar novamente
                </Button>
              </div>
            ) : null}
          </section>
          {detail ? <Neighborhoods envelope={detail} /> : null}
        </>
      ) : null}
      {detail &&
      detail.data.coverage.measured_energy_kwh.status === "partial" ? (
        <p className="mt-3 rounded-lg bg-[var(--status-warning-bg)] p-3 text-xs text-content">
          A cobertura do consumo medido é parcial no período. Os valores
          observados permanecem visíveis e não são tratados como zero.
        </p>
      ) : null}
      {layer.endsWith("change") ? (
        <p className="sr-only">
          A camada selecionada mostra a variação absoluta entre as duas
          competências.
        </p>
      ) : null}
    </section>
  );
}
