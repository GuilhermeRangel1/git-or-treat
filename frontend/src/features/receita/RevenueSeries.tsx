import { useState } from "react";
import type { RevenueEnvelope } from "./contract";
import "./revenue-series.css";

const money = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  maximumFractionDigits: 2,
});
const axisMoney = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  maximumFractionDigits: 0,
});
const decimal = new Intl.NumberFormat("pt-BR", {
  maximumFractionDigits: 2,
});

function monthLabel(value: string) {
  const date = new Date(`${value}-01T00:00:00Z`);
  const month = new Intl.DateTimeFormat("pt-BR", {
    month: "short",
    timeZone: "UTC",
  })
    .format(date)
    .replace(".", "");
  return `${month.charAt(0).toLocaleUpperCase("pt-BR")}${month.slice(1)}/${value.slice(0, 4)}`;
}

const chart = {
  width: 720,
  left: 104,
  right: 704,
  top: 20,
  bottom: 202,
  height: 260,
};

type ChartPoint = {
  competencia: string;
  value: number | null;
  x: number;
  y: number | null;
};

function chartCoordinates(rows: RevenueEnvelope["data"]["series"]): {
  points: ChartPoint[];
  ticks: number[];
} {
  const values = rows
    .map((row) => row.billed_amount)
    .filter((value): value is number => value !== null);
  const left = chart.left;
  const right = chart.right;
  const top = chart.top;
  const bottom = chart.bottom;

  if (values.length === 0) {
    return {
      points: rows.map((row, index) => ({
        competencia: row.competencia,
        value: row.billed_amount,
        x:
          rows.length < 2
            ? (left + right) / 2
            : left + ((right - left) * index) / (rows.length - 1),
        y: null,
      })),
      ticks: [],
    };
  }

  const observedMinimum = Math.min(...values);
  const observedMaximum = Math.max(...values);
  const observedSpan = observedMaximum - observedMinimum;
  const padding =
    observedSpan === 0
      ? Math.max(Math.abs(observedMaximum) * 0.08, 1)
      : observedSpan * 0.14;
  const minimum = observedMinimum - padding;
  const maximum = observedMaximum + padding;
  const span = maximum - minimum;
  const ticks = Array.from(
    { length: 4 },
    (_, index) => maximum - (span * index) / 3,
  );

  return {
    points: rows.map((row, index) => ({
      competencia: row.competencia,
      value: row.billed_amount,
      x:
        rows.length < 2
          ? (left + right) / 2
          : left + ((right - left) * index) / (rows.length - 1),
      y:
        row.billed_amount === null
          ? null
          : top + ((maximum - row.billed_amount) / span) * (bottom - top),
    })),
    ticks,
  };
}

function pointGroups(points: ChartPoint[]) {
  const groups: ChartPoint[][] = [];
  let current: ChartPoint[] = [];

  for (const point of points) {
    if (point.value === null || point.y === null) {
      if (current.length > 0) groups.push(current);
      current = [];
    } else {
      current.push(point);
    }
  }

  if (current.length > 0) groups.push(current);
  return groups;
}

function linePath(points: ChartPoint[]) {
  return points
    .map((point, index) => `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`)
    .join(" ");
}

function areaPath(points: ChartPoint[]) {
  const first = points[0];
  const last = points.at(-1);
  if (!first || !last) return "";
  return `M ${first.x} ${chart.bottom} L ${linePath(points).slice(2)} L ${last.x} ${chart.bottom} Z`;
}

export default function RevenueSeries({
  envelope,
}: {
  envelope: RevenueEnvelope;
}) {
  const rows = envelope.data.series;
  const { points, ticks } = chartCoordinates(rows);
  const groups = pointGroups(points);
  const [activeCompetence, setActiveCompetence] = useState<string | null>(null);
  const activePoint = points.find(
    (point) => point.competencia === activeCompetence && point.value !== null,
  );
  const accessibleSummary = rows
    .map(
      (row) =>
        `${monthLabel(row.competencia)}: ${row.billed_amount === null ? "sem dado" : money.format(row.billed_amount)}`,
    )
    .join("; ");
  const tickStep = Math.max(1, Math.ceil(rows.length / 12));
  const monthTicks = rows.filter(
    (_, index) => index % tickStep === 0 || index === rows.length - 1,
  );
  const hasValues = points.some((point) => point.value !== null);

  return (
    <section
      aria-labelledby="revenue-series-title"
      aria-label="Série mensal"
      className="min-w-0 rounded-xl border border-border bg-surface p-4 sm:p-5"
    >
      <h2
        id="revenue-series-title"
        className="font-heading text-lg font-semibold text-content"
      >
        Série mensal de faturamento
      </h2>
      <p className="mt-1 text-sm text-muted">
        Receita faturada por competência (BRL). Lacunas permanecem sem valor e
        não são ligadas no gráfico.
      </p>
      <div className="mt-4 min-w-0 max-w-full overflow-x-auto rounded-lg bg-canvas/50 px-2 py-2">
        <div className="revenue-series__chart-enter">
          <svg
            className="block h-64 min-w-[560px] w-full"
            viewBox={`0 0 ${chart.width} ${chart.height}`}
            role="img"
            aria-label={`Receita faturada por competência. ${accessibleSummary}`}
            preserveAspectRatio="none"
          >
            <defs>
              <linearGradient
                id="revenue-series-fill"
                x1="0"
                x2="0"
                y1="0"
                y2="1"
              >
                <stop
                  offset="0%"
                  stopColor="var(--color-brand)"
                  stopOpacity="0.2"
                />
                <stop
                  offset="100%"
                  stopColor="var(--color-brand)"
                  stopOpacity="0.015"
                />
              </linearGradient>
            </defs>

            {ticks.map((tick, index) => {
              const y =
                chart.top +
                ((ticks[0] - tick) / (ticks[0] - ticks.at(-1)!)) *
                  (chart.bottom - chart.top);
              return (
                <g key={`tick-${index}`}>
                  <line
                    x1={chart.left}
                    x2={chart.right}
                    y1={y}
                    y2={y}
                    className="stroke-border"
                    strokeDasharray={
                      index === ticks.length - 1 ? undefined : "3 6"
                    }
                    strokeOpacity={index === ticks.length - 1 ? 0.9 : 0.65}
                  />
                  <text
                    x={chart.left - 12}
                    y={y + 4}
                    textAnchor="end"
                    className="fill-muted"
                    fontSize="11"
                  >
                    {axisMoney.format(tick)}
                  </text>
                </g>
              );
            })}

            {groups.map((group) => (
              <path
                key={`area-${group[0]?.competencia}`}
                d={areaPath(group)}
                fill="url(#revenue-series-fill)"
              />
            ))}
            {groups.map((group) =>
              group.length > 1 ? (
                <path
                  key={`line-${group[0]?.competencia}`}
                  d={linePath(group)}
                  pathLength="1"
                  fill="none"
                  className="revenue-series__line stroke-brand"
                  strokeWidth="3"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              ) : null,
            )}
            {points.map((point) =>
              point.value === null || point.y === null ? null : (
                <g key={point.competencia}>
                  <circle
                    cx={point.x}
                    cy={point.y}
                    r="8"
                    className="fill-brand"
                    opacity="0.14"
                    pointerEvents="none"
                  />
                  <circle
                    cx={point.x}
                    cy={point.y}
                    r="4.5"
                    className="revenue-series__point fill-surface stroke-brand"
                    strokeWidth="3"
                    tabIndex={0}
                    role="img"
                    aria-describedby={
                      activeCompetence === point.competencia
                        ? "revenue-series-tooltip"
                        : undefined
                    }
                    aria-label={`Exibir ${monthLabel(point.competencia)}, faturamento ${money.format(point.value)}`}
                    onMouseEnter={() => setActiveCompetence(point.competencia)}
                    onMouseLeave={() => setActiveCompetence(null)}
                    onFocus={() => setActiveCompetence(point.competencia)}
                    onBlur={() => setActiveCompetence(null)}
                  />
                </g>
              ),
            )}

            {monthTicks.map((row, index) => {
              const point = points.find(
                (candidate) => candidate.competencia === row.competencia,
              );
              if (!point) return null;
              return (
                <text
                  key={`month-${row.competencia}`}
                  x={point.x}
                  y={chart.bottom + 28}
                  textAnchor={
                    index === 0
                      ? "start"
                      : index === monthTicks.length - 1
                        ? "end"
                        : "middle"
                  }
                  className="fill-muted"
                  fontSize="11"
                >
                  {monthLabel(row.competencia)}
                </text>
              );
            })}

            {activePoint &&
            activePoint.value !== null &&
            activePoint.y !== null ? (
              <g
                id="revenue-series-tooltip"
                role="tooltip"
                aria-label={`${monthLabel(activePoint.competencia)}: ${money.format(activePoint.value)}`}
                pointerEvents="none"
              >
                <line
                  x1={chart.left}
                  x2={activePoint.x}
                  y1={activePoint.y}
                  y2={activePoint.y}
                  className="stroke-brand"
                  strokeDasharray="3 4"
                  strokeOpacity="0.7"
                />
                <line
                  x1={activePoint.x}
                  x2={activePoint.x}
                  y1={chart.top}
                  y2={chart.bottom}
                  className="stroke-brand"
                  strokeDasharray="3 4"
                  strokeOpacity="0.45"
                />
                <rect
                  x={
                    activePoint.x > (chart.left + chart.right) / 2
                      ? activePoint.x - 188
                      : activePoint.x + 12
                  }
                  y={Math.max(chart.top + 6, activePoint.y - 62)}
                  width="176"
                  height="48"
                  rx="9"
                  fill="var(--bg-surface)"
                  stroke="var(--line)"
                />
                <text
                  x={
                    activePoint.x > (chart.left + chart.right) / 2
                      ? activePoint.x - 176
                      : activePoint.x + 24
                  }
                  y={Math.max(chart.top + 23, activePoint.y - 45)}
                  className="fill-muted"
                  fontSize="10"
                >
                  Competência · {monthLabel(activePoint.competencia)}
                </text>
                <text
                  x={
                    activePoint.x > (chart.left + chart.right) / 2
                      ? activePoint.x - 176
                      : activePoint.x + 24
                  }
                  y={Math.max(chart.top + 42, activePoint.y - 27)}
                  className="fill-content"
                  fontSize="13"
                  fontWeight="600"
                >
                  Faturamento · {money.format(activePoint.value)}
                </text>
              </g>
            ) : null}

            {!hasValues ? (
              <text
                x={(chart.left + chart.right) / 2}
                y={(chart.top + chart.bottom) / 2}
                textAnchor="middle"
                className="fill-muted"
                fontSize="13"
              >
                Sem dados de faturamento no período
              </text>
            ) : null}
          </svg>
        </div>
      </div>
      <div className="mt-3 min-w-0 max-w-full overflow-x-auto">
        <table className="w-full min-w-[680px] border-collapse text-left text-sm">
          <caption className="sr-only">
            Série mensal com faturamento, pagamento e energia
          </caption>
          <thead className="border-b border-border text-xs text-muted">
            <tr>
              <th scope="col" className="px-3 py-2 font-medium">
                Competência
              </th>
              <th scope="col" className="px-3 py-2 font-medium">
                Receita faturada (BRL)
              </th>
              <th scope="col" className="px-3 py-2 font-medium">
                Receita paga (BRL)
              </th>
              <th scope="col" className="px-3 py-2 font-medium">
                Energia medida (kWh)
              </th>
              <th scope="col" className="px-3 py-2 font-medium">
                Energia faturada (kWh)
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr
                key={row.competencia}
                className="border-b border-border last:border-0"
              >
                <th
                  scope="row"
                  className="px-3 py-3 font-semibold text-content"
                >
                  {monthLabel(row.competencia)}
                </th>
                <td className="px-3 py-3">
                  {row.billed_amount === null
                    ? "Sem dado"
                    : money.format(row.billed_amount)}
                </td>
                <td className="px-3 py-3">
                  {row.paid_amount === null
                    ? "Sem dado"
                    : money.format(row.paid_amount)}
                </td>
                <td className="px-3 py-3">
                  {row.measured_energy_kwh === null
                    ? "Sem dado"
                    : `${decimal.format(row.measured_energy_kwh)} kWh`}
                </td>
                <td className="px-3 py-3">
                  {row.billed_energy_kwh === null
                    ? "Sem dado"
                    : `${decimal.format(row.billed_energy_kwh)} kWh`}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
