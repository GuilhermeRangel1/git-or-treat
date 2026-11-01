import type { UCMeasure, UCOverview } from "./contract";
import { formatUCCompetence, statusLabel } from "./uc360-format";

type Comparison = UCOverview["data"]["comparison"];
type Snapshot = Comparison["initial"];
type MeasureKind = "energy" | "money";

const money = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
});
const decimal = new Intl.NumberFormat("pt-BR", {
  maximumFractionDigits: 2,
});

function measureValue(measure: UCMeasure, kind: MeasureKind) {
  if (measure.value === null) return "Sem dado";
  return kind === "money"
    ? money.format(measure.value)
    : `${decimal.format(measure.value)} kWh`;
}

function Coverage({
  snapshot,
  showPaid,
}: {
  snapshot: Snapshot;
  showPaid: boolean;
}) {
  const measures = [
    ["Consumo medido", snapshot.measured_energy_kwh.status],
    ["Valor faturado", snapshot.billed_amount.status],
    ...(showPaid ? [["Valor pago", snapshot.paid_amount.status] as const] : []),
  ] as const;
  const sameStatus = measures.every(([, status]) => status === measures[0][1]);

  return (
    <span className="text-xs leading-4 text-muted">
      {sameStatus
        ? `Todas as medidas: ${statusLabel(measures[0][1])}`
        : measures
            .map(([label, status]) => `${label}: ${statusLabel(status)}`)
            .join(" · ")}
    </span>
  );
}

function MobileSnapshot({
  snapshot,
  showPaid,
}: {
  snapshot: Snapshot;
  showPaid: boolean;
}) {
  return (
    <article className="rounded-xl border border-control/50 bg-surface p-4">
      <h3 className="mb-3 grid gap-1">
        <span className="text-xs font-medium text-muted">Competência</span>
        <span className="text-base font-semibold text-content">
          {formatUCCompetence(snapshot.competencia)}
        </span>
      </h3>
      <dl className="grid grid-cols-2 gap-x-4 gap-y-3">
        <div className="grid min-w-0 gap-1">
          <dt className="text-xs text-muted">Consumo medido</dt>
          <dd className="break-words text-sm font-medium text-content">
            {measureValue(snapshot.measured_energy_kwh, "energy")}
          </dd>
          <dd className="text-xs text-muted">
            {statusLabel(snapshot.measured_energy_kwh.status)}
          </dd>
        </div>
        <div className="grid min-w-0 gap-1">
          <dt className="text-xs text-muted">Valor faturado</dt>
          <dd className="break-words text-sm font-medium text-content">
            {measureValue(snapshot.billed_amount, "money")}
          </dd>
          <dd className="text-xs text-muted">
            {statusLabel(snapshot.billed_amount.status)}
          </dd>
        </div>
        {showPaid && (
          <div className="grid min-w-0 gap-1">
            <dt className="text-xs text-muted">Valor pago</dt>
            <dd className="break-words text-sm font-medium text-content">
              {measureValue(snapshot.paid_amount, "money")}
            </dd>
            <dd className="text-xs text-muted">
              {statusLabel(snapshot.paid_amount.status)}
            </dd>
          </div>
        )}
      </dl>
    </article>
  );
}

export default function UC360OverviewTable({
  comparison,
}: {
  comparison: Comparison;
}) {
  const snapshots = [
    { key: "final", snapshot: comparison.final },
    { key: "initial", snapshot: comparison.initial },
  ] as const;
  const showPaid = snapshots.some(
    ({ snapshot }) => snapshot.paid_amount.value !== null,
  );

  return (
    <section
      aria-label="Resumo por competência"
      className="min-h-[188px] rounded-xl bg-transparent p-0 md:bg-surface md:p-4"
    >
      <div className="hidden md:block">
        <table className="w-full table-fixed border-collapse text-left">
          <caption className="sr-only">
            Comparação de consumo medido e valores por competência
          </caption>
          <thead>
            <tr className="h-8 font-mono text-xs tracking-wide text-muted">
              <th className="pb-2 font-medium" scope="col">
                Competência
              </th>
              <th className="pb-2 font-medium" scope="col">
                Consumo medido
              </th>
              <th className="pb-2 font-medium" scope="col">
                Valor faturado
              </th>
              {showPaid && (
                <th className="pb-2 font-medium" scope="col">
                  Valor pago
                </th>
              )}
              <th className="pb-2 font-medium" scope="col">
                Cobertura
              </th>
            </tr>
          </thead>
          <tbody>
            {snapshots.map(({ key, snapshot }) => (
              <tr className="h-14" key={key}>
                <th
                  className="pr-2 text-sm font-semibold text-content"
                  scope="row"
                >
                  {formatUCCompetence(snapshot.competencia)}
                </th>
                <td className="pr-2 text-sm text-content">
                  {measureValue(snapshot.measured_energy_kwh, "energy")}
                </td>
                <td className="pr-2 text-sm text-content">
                  {measureValue(snapshot.billed_amount, "money")}
                </td>
                {showPaid && (
                  <td className="pr-2 text-sm text-content">
                    {measureValue(snapshot.paid_amount, "money")}
                  </td>
                )}
                <td className="py-1">
                  <Coverage snapshot={snapshot} showPaid={showPaid} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="grid gap-3 md:hidden">
        {snapshots.map(({ key, snapshot }) => (
          <MobileSnapshot key={key} snapshot={snapshot} showPaid={showPaid} />
        ))}
      </div>
    </section>
  );
}
