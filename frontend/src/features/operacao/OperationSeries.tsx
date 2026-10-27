import "./operation-series.css";
import type { OperationPoint, OperationPeriod } from "./contract";
import { formatMonth, formatNumber, monthsInPeriod } from "./operation-format";

type MonthlyValue = { month: string; dec: number | null; fec: number | null };

function chartValues(
  period: OperationPeriod,
  series: OperationPoint[],
): MonthlyValue[] {
  const byMonth = new Map(series.map((point) => [point.period.start, point]));
  return monthsInPeriod(period).map((month) => {
    const point = byMonth.get(month);
    const eligible =
      point?.status === "available" || point?.status === "partial";
    return {
      month,
      dec: eligible ? point.dec_hours_per_uc : null,
      fec: eligible ? point.fec_interruptions_per_uc : null,
    };
  });
}

function SeriesChart({
  label,
  unit,
  values,
}: {
  label: string;
  unit: string;
  values: Array<{ month: string; value: number | null }>;
}) {
  const presentValues = values.flatMap((item) =>
    item.value === null ? [] : [item.value],
  );
  const maximum = Math.max(...presentValues, 0);
  const axisMaximum = maximum > 0 ? maximum : 1;
  const half = axisMaximum / 2;
  const plotMinWidth = values.length * 44;

  return (
    <section
      role="region"
      aria-label={`Série mensal de ${label}`}
      className="grid min-w-0 gap-3 rounded-xl bg-surface p-4 sm:p-6"
    >
      <div>
        <h3 className="font-heading text-lg font-semibold">
          Evolução do {label} simplificado
        </h3>
        <p className="mt-1 text-xs text-muted">
          Série mensal · {unit} · escala começa em zero
        </p>
      </div>
      <div className="grid grid-cols-[42px_minmax(0,1fr)] gap-2">
        <div
          className="flex h-56 flex-col justify-between pb-7 text-right font-mono text-[11px] text-muted"
          aria-hidden="true"
        >
          <span>{formatNumber(axisMaximum)}</span>
          <span>{formatNumber(half)}</span>
          <span>0</span>
        </div>
        <div
          className="min-w-0 max-w-full overflow-x-auto pb-1"
          tabIndex={0}
          aria-label={`Rolagem do gráfico ${label}`}
        >
          <div
            className="relative h-56 w-full"
            style={{ minWidth: `${plotMinWidth}px` }}
          >
            <div
              className="pointer-events-none absolute inset-x-0 top-0 bottom-7 flex flex-col justify-between"
              aria-hidden="true"
            >
              <span className="border-t border-border" />
              <span className="border-t border-dashed border-border" />
              <span className="border-b border-control" />
            </div>
            <div className="relative flex h-full items-end justify-between gap-2">
              {values.map(({ month, value }) => (
                <div
                  key={month}
                  className="flex h-full min-w-0 flex-1 flex-col items-center justify-end gap-1"
                >
                  <span className="h-4 text-[11px] text-muted">
                    {value === null ? "—" : formatNumber(value)}
                  </span>
                  <div className="flex h-[calc(100%-3.25rem)] w-full items-end justify-center">
                    {value === null ? (
                      <span className="mb-0 block h-0 w-full border-b border-dashed border-control" />
                    ) : (
                      <span
                        className="operation-series-bar block w-[min(100%,2.25rem)] rounded-t-sm"
                        style={{
                          height: `${Math.max(0, (value / axisMaximum) * 100)}%`,
                          minHeight: value === 0 ? "2px" : undefined,
                        }}
                      />
                    )}
                  </div>
                  <span className="h-7 text-center text-[10px] leading-3 text-muted">
                    {formatMonth(month)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
      <ul className="sr-only">
        {values.map(({ month, value }) => (
          <li key={month}>
            {formatMonth(month)}:{" "}
            {value === null ? "indisponível" : `${formatNumber(value)} ${unit}`}
          </li>
        ))}
      </ul>
    </section>
  );
}

export default function OperationSeries({
  period,
  series,
}: {
  period: OperationPeriod;
  series: OperationPoint[];
}) {
  const values = chartValues(period, series);
  return (
    <div className="grid min-w-0 gap-4">
      <SeriesChart
        label="DEC"
        unit="h/UC"
        values={values.map(({ month, dec }) => ({ month, value: dec }))}
      />
      <SeriesChart
        label="FEC"
        unit="interrupções/UC"
        values={values.map(({ month, fec }) => ({ month, value: fec }))}
      />
      <div className="max-w-full min-w-0 overflow-x-auto rounded-xl">
        <table
          className="w-full min-w-[440px] border-collapse rounded-xl bg-surface text-left text-sm"
          aria-label="Dados mensais de continuidade"
        >
          <thead className="text-xs text-muted">
            <tr>
              <th scope="col" className="px-4 py-3">
                Competência
              </th>
              <th scope="col" className="px-4 py-3">
                DEC (h/UC)
              </th>
              <th scope="col" className="px-4 py-3">
                FEC (interrupções/UC)
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {values.map(({ month, dec, fec }) => (
              <tr key={month}>
                <th scope="row" className="px-4 py-3 font-medium">
                  {formatMonth(month)}
                </th>
                <td className="px-4 py-3">
                  {dec === null ? "Indisponível" : formatNumber(dec)}
                </td>
                <td className="px-4 py-3">
                  {fec === null ? "Indisponível" : formatNumber(fec)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
