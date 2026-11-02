import { useLayoutEffect, useRef, useState } from "react";
import Modal from "@/shared/ui/Modal";
import { signedValueTone } from "@/shared/ui/signedValue";
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
  notation: "compact",
  maximumFractionDigits: 1,
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
  minWidth: 560,
  left: 104,
  rightInset: 16,
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

function chartCoordinates(
  rows: RevenueEnvelope["data"]["series"],
  width: number,
): {
  points: ChartPoint[];
  ticks: number[];
} {
  const values = rows
    .map((row) => row.billed_amount)
    .filter((value): value is number => value !== null);
  const left = chart.left;
  const right = Math.max(left + 1, width - chart.rightInset);
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
  const domainMinimum = Math.min(0, observedMinimum);
  const domainMaximum = Math.max(0, observedMaximum);
  const domainSpan = domainMaximum - domainMinimum;
  const padding = Math.max(domainSpan * 0.08, 1);
  const minimum = domainMinimum < 0 ? domainMinimum - padding : 0;
  const maximum = domainMaximum > 0 ? domainMaximum + padding : padding;
  const span = maximum - minimum;
  const ticks = Array.from(
    { length: 5 },
    (_, index) => maximum - (span * index) / 4,
  );
  if (
    minimum < 0 &&
    maximum > 0 &&
    !ticks.some((tick) => Math.abs(tick) < 0.000001)
  ) {
    ticks.push(0);
  }
  ticks.sort((left, right) => right - left);

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

export default function RevenueSeries({
  envelope,
}: {
  envelope: RevenueEnvelope;
}) {
  const rows = envelope.data.series;
  const showPaid = rows.some((row) => row.paid_amount !== null);
  const showBilledEnergy = rows.some((row) => row.billed_energy_kwh !== null);
  const chartRef = useRef<SVGSVGElement>(null);
  const tableTriggerRef = useRef<HTMLButtonElement>(null);
  const [chartWidth, setChartWidth] = useState(chart.width);
  const [showTable, setShowTable] = useState(false);

  useLayoutEffect(() => {
    const svg = chartRef.current;
    if (!svg) return;

    const updateWidth = () => {
      const width = Math.max(
        chart.minWidth,
        Math.round(svg.getBoundingClientRect().width),
      );
      if (width > 0) {
        setChartWidth((current) => (current === width ? current : width));
      }
    };

    updateWidth();
    if (typeof ResizeObserver === "undefined") return;

    const observer = new ResizeObserver(updateWidth);
    observer.observe(svg);
    return () => observer.disconnect();
  }, []);

  const { points, ticks } = chartCoordinates(rows, chartWidth);
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
  const tickStep = Math.max(
    1,
    Math.ceil(
      rows.length / Math.max(2, Math.floor((chartWidth - chart.left) / 90)),
    ),
  );
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
      <p className="mt-1 text-sm text-muted">Receita faturada por mês (BRL).</p>
      <div className="mt-4 min-w-0 max-w-full overflow-x-auto rounded-lg bg-canvas/50 px-2 py-2">
        <div className="revenue-series__chart-enter">
          <svg
            ref={chartRef}
            className="block h-64 min-w-[560px] w-full"
            viewBox={`0 0 ${chartWidth} ${chart.height}`}
            role="img"
            aria-label={`Receita faturada por mês. ${accessibleSummary}`}
            preserveAspectRatio="xMidYMid meet"
          >
            {ticks.map((tick, index) => {
              const y =
                chart.top +
                ((ticks[0] - tick) / (ticks[0] - ticks.at(-1)!)) *
                  (chart.bottom - chart.top);
              const isZero = Math.abs(tick) < 0.000001;
              return (
                <g key={`tick-${index}`}>
                  <line
                    x1={chart.left}
                    x2={chartWidth - chart.rightInset}
                    y1={y}
                    y2={y}
                    className={isZero ? "stroke-brand" : "stroke-border"}
                    strokeDasharray={isZero ? undefined : "3 6"}
                    strokeOpacity={isZero ? 0.3 : 0.65}
                    strokeWidth={isZero ? 1.5 : 1}
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
                    activePoint.x >
                    (chart.left + chartWidth - chart.rightInset) / 2
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
                    activePoint.x >
                    (chart.left + chartWidth - chart.rightInset) / 2
                      ? activePoint.x - 176
                      : activePoint.x + 24
                  }
                  y={Math.max(chart.top + 23, activePoint.y - 45)}
                  className="fill-muted"
                  fontSize="10"
                >
                  Mês · {monthLabel(activePoint.competencia)}
                </text>
                <text
                  x={
                    activePoint.x >
                    (chart.left + chartWidth - chart.rightInset) / 2
                      ? activePoint.x - 176
                      : activePoint.x + 24
                  }
                  y={Math.max(chart.top + 42, activePoint.y - 27)}
                  className="fill-content"
                  fontSize="13"
                  fontWeight="600"
                >
                  {money.format(activePoint.value).length > 13
                    ? axisMoney.format(activePoint.value)
                    : money.format(activePoint.value)}
                </text>
              </g>
            ) : null}

            {!hasValues ? (
              <text
                x={(chart.left + chartWidth - chart.rightInset) / 2}
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
      <button
        ref={tableTriggerRef}
        type="button"
        className="revenue-series__details-link"
        aria-haspopup="dialog"
        onClick={() => setShowTable(true)}
      >
        Ver tabela da série →
      </button>

      <Modal
        open={showTable}
        onClose={() => setShowTable(false)}
        triggerRef={tableTriggerRef}
        title="Tabela da série"
        description="Valores mensais de faturamento, pagamento e energia disponíveis no período."
        closeLabel="Fechar dados da série"
        size="md"
        header="inline"
      >
        <div className="revenue-series__table-wrap">
          <table className="revenue-series__table">
            <caption className="sr-only">
              Série mensal de faturamento e energia
            </caption>
            <thead className="text-xs text-muted">
              <tr>
                <th scope="col" className="font-medium">
                  Mês
                </th>
                <th scope="col" className="font-medium">
                  Receita faturada (BRL)
                </th>
                {showPaid && (
                  <th scope="col" className="font-medium">
                    Receita paga (BRL)
                  </th>
                )}
                <th scope="col" className="font-medium">
                  Energia medida (kWh)
                </th>
                {showBilledEnergy && (
                  <th scope="col" className="font-medium">
                    Energia faturada (kWh)
                  </th>
                )}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.competencia} className="last:border-0">
                  <th scope="row" className="font-semibold text-content">
                    {monthLabel(row.competencia)}
                  </th>
                  <td className={signedValueTone(row.billed_amount, false)}>
                    {row.billed_amount === null
                      ? "Sem dado"
                      : money.format(row.billed_amount)}
                  </td>
                  {showPaid && (
                    <td className={signedValueTone(row.paid_amount, false)}>
                      {row.paid_amount === null
                        ? "Sem dado"
                        : money.format(row.paid_amount)}
                    </td>
                  )}
                  <td
                    className={signedValueTone(row.measured_energy_kwh, false)}
                  >
                    {row.measured_energy_kwh === null
                      ? "Sem dado"
                      : `${decimal.format(row.measured_energy_kwh)} kWh`}
                  </td>
                  {showBilledEnergy && (
                    <td
                      className={signedValueTone(row.billed_energy_kwh, false)}
                    >
                      {row.billed_energy_kwh === null
                        ? "Sem dado"
                        : `${decimal.format(row.billed_energy_kwh)} kWh`}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {(!showPaid || !showBilledEnergy) && (
          <p className="mt-3 text-xs text-muted">
            {!showPaid && "Receita paga não está disponível neste recorte. "}
            {!showBilledEnergy &&
              "Energia faturada não está disponível; energia medida é uma grandeza diferente."}
          </p>
        )}
      </Modal>
    </section>
  );
}
