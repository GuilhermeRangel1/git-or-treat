import { useId, useLayoutEffect, useRef, useState } from "react";
import Modal from "@/shared/ui/Modal";
import type { OperationPeriod, OperationStatus } from "./contract";
import { formatMonth, formatNumber, monthsInPeriod } from "./operation-format";
import "./operation-series.css";

type SeriesPoint = {
  period: OperationPeriod;
  status: OperationStatus;
  dec_hours_per_uc: number | null;
  fec_interruptions_per_uc: number | null;
  denominator_uc_count: number | null;
};
type MonthlyValue = {
  month: string;
  dec: number | null;
  fec: number | null;
  denominator: number | null;
};
type ChartPoint = {
  month: string;
  value: number | null;
  denominator: number | null;
  x: number;
  y: number | null;
};

const chart = {
  height: 280,
  left: 84,
  right: 20,
  top: 20,
  bottom: 210,
};

function chartValues(
  period: OperationPeriod,
  series: SeriesPoint[],
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
      denominator: point?.denominator_uc_count ?? null,
    };
  });
}

function coordinates(
  values: MonthlyValue[],
  metric: "dec" | "fec",
  availableWidth: number,
) {
  const width = Math.max(availableWidth, 560, values.length * 68);
  const maximumValue = Math.max(
    0,
    ...values.flatMap((point) =>
      point[metric] === null ? [] : [point[metric]!],
    ),
  );
  const maximum = maximumValue > 0 ? maximumValue * 1.08 : 1;
  const plotWidth = width - chart.left - chart.right;
  const plotHeight = chart.bottom - chart.top;
  const points = values.map((point, index): ChartPoint => ({
    month: point.month,
    value: point[metric],
    denominator: point.denominator,
    x:
      values.length < 2
        ? chart.left + plotWidth / 2
        : chart.left + (plotWidth * index) / (values.length - 1),
    y:
      point[metric] === null
        ? null
        : chart.bottom - (point[metric]! / maximum) * plotHeight,
  }));
  return { width, maximum, points };
}

function lineGroups(points: ChartPoint[]) {
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

function SeriesChart({
  label,
  unit,
  metric,
  values,
}: {
  label: string;
  unit: string;
  metric: "dec" | "fec";
  values: MonthlyValue[];
}) {
  const [showTable, setShowTable] = useState(false);
  const [activeMonth, setActiveMonth] = useState<string | null>(null);
  const [availableWidth, setAvailableWidth] = useState(720);
  const viewportRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const tooltipId = useId();
  const { width, maximum, points } = coordinates(
    values,
    metric,
    availableWidth,
  );
  const activePoint = points.find((point) => point.month === activeMonth);
  const half = maximum / 2;
  const accessibleSummary = points
    .map(
      ({ month, value }) =>
        `${formatMonth(month)}: ${value === null ? `indisponível ${unit}` : `${formatNumber(value)} ${unit}`}`,
    )
    .join("; ");
  const tickValues = [maximum, half, 0];
  const pointSpacing =
    points.length > 1
      ? (width - chart.left - chart.right) / (points.length - 1)
      : Number.POSITIVE_INFINITY;
  const monthTickStep = Math.max(1, Math.ceil(84 / pointSpacing));
  const tooltipLeft = activePoint
    ? Math.min(
        width - 188,
        Math.max(
          0,
          activePoint.x > width / 2 ? activePoint.x - 188 : activePoint.x + 12,
        ),
      )
    : 0;
  const tooltipTop = activePoint?.y
    ? Math.min(chart.height - 54, Math.max(chart.top + 6, activePoint.y - 62))
    : chart.top + 6;

  useLayoutEffect(() => {
    const viewport = viewportRef.current;
    if (!viewport || typeof ResizeObserver === "undefined") return;

    const observer = new ResizeObserver(([entry]) => {
      const nextWidth = Math.floor(entry?.contentRect.width ?? 0);
      if (nextWidth > 0) setAvailableWidth(nextWidth);
    });
    observer.observe(viewport);
    return () => observer.disconnect();
  }, []);

  return (
    <section
      role="region"
      aria-label={`Série mensal de ${label}`}
      className="operation-series-chart"
    >
      <h3 className="operation-series-chart__title">
        Evolução mensal do {label} simplificado
      </h3>
      <p className="mt-1 text-sm text-muted">{unit} · escala começa em zero.</p>
      <div
        ref={viewportRef}
        className="mt-4 min-w-0 max-w-full overflow-x-auto rounded-lg bg-canvas/50 px-2 py-2"
      >
        <div className="operation-series__chart-enter">
          <svg
            className="block h-[280px]"
            style={{ minWidth: `${width}px`, width: `${width}px` }}
            viewBox={`0 0 ${width} ${chart.height}`}
            role="img"
            aria-label={`Evolução mensal do ${label}. ${accessibleSummary}`}
          >
            {tickValues.map((tick, index) => {
              const y = chart.top + (index * (chart.bottom - chart.top)) / 2;
              return (
                <g key={`tick-${index}`}>
                  <line
                    x1={chart.left}
                    x2={width - chart.right}
                    y1={y}
                    y2={y}
                    className={index === 2 ? "stroke-brand" : "stroke-border"}
                    strokeDasharray={index === 2 ? undefined : "3 6"}
                    strokeOpacity={index === 2 ? 0.3 : 0.65}
                    strokeWidth={index === 2 ? 1.5 : 1}
                  />
                  <text
                    x={chart.left - 10}
                    y={y + 4}
                    textAnchor="end"
                    className="fill-muted"
                    fontSize="11"
                  >
                    {formatNumber(tick)}
                  </text>
                </g>
              );
            })}
            {lineGroups(points).map((group) =>
              group.length > 1 ? (
                <path
                  key={`line-${group[0]?.month}`}
                  d={linePath(group)}
                  pathLength="1"
                  fill="none"
                  className="operation-series__line stroke-brand"
                  strokeWidth="3"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              ) : null,
            )}
            {points.map((point) =>
              point.value === null || point.y === null ? null : (
                <g key={point.month}>
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
                    className="operation-series__point fill-surface stroke-brand"
                    strokeWidth="3"
                    tabIndex={0}
                    role="img"
                    aria-describedby={
                      activeMonth === point.month ? tooltipId : undefined
                    }
                    aria-label={`Exibir ${formatMonth(point.month)}, ${label} ${formatNumber(point.value)} ${unit}`}
                    onMouseEnter={() => setActiveMonth(point.month)}
                    onMouseLeave={() => setActiveMonth(null)}
                    onFocus={() => setActiveMonth(point.month)}
                    onBlur={() => setActiveMonth(null)}
                  />
                </g>
              ),
            )}
            {points.map((point, index) => {
              const lastIndex = points.length - 1;
              const isEndpoint = index === 0 || index === lastIndex;
              const isSpacedTick =
                index % monthTickStep === 0 &&
                lastIndex - index >= monthTickStep;
              if (!isEndpoint && !isSpacedTick) return null;
              return (
                <text
                  key={`month-${point.month}`}
                  x={point.x}
                  y={chart.bottom + 32}
                  textAnchor={
                    index === 0
                      ? "start"
                      : index === lastIndex
                        ? "end"
                        : "middle"
                  }
                  className="fill-muted"
                  fontSize="11"
                >
                  {formatMonth(point.month)}
                </text>
              );
            })}
            {activePoint &&
            activePoint.value !== null &&
            activePoint.y !== null ? (
              <g
                id={tooltipId}
                role="tooltip"
                aria-label={`${formatMonth(activePoint.month)}: ${formatNumber(activePoint.value)} ${unit}`}
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
                  x={tooltipLeft}
                  y={tooltipTop}
                  width="176"
                  height="48"
                  rx="9"
                  fill="var(--bg-surface)"
                  stroke="var(--line)"
                />
                <text
                  x={tooltipLeft + 12}
                  y={tooltipTop + 17}
                  className="fill-muted"
                  fontSize="10"
                >
                  Mês · {formatMonth(activePoint.month)}
                </text>
                <text
                  x={tooltipLeft + 12}
                  y={tooltipTop + 36}
                  className="fill-content"
                  fontSize="13"
                  fontWeight="600"
                >
                  {formatNumber(activePoint.value)} {unit}
                </text>
              </g>
            ) : null}
            {points.every((point) => point.value === null) ? (
              <text
                x={width / 2}
                y={(chart.top + chart.bottom) / 2}
                textAnchor="middle"
                className="fill-muted"
                fontSize="13"
              >
                Sem dados no período
              </text>
            ) : null}
          </svg>
          <ul className="sr-only">
            {points.map(({ month, value }) => (
              <li key={month}>
                {formatMonth(month)}:{" "}
                {value === null
                  ? `indisponível ${unit}`
                  : `${formatNumber(value)} ${unit}`}
              </li>
            ))}
          </ul>
        </div>
      </div>
      <button
        ref={triggerRef}
        type="button"
        className="operation-series__details-link"
        aria-haspopup="dialog"
        onClick={() => setShowTable(true)}
      >
        Ver tabela da série →
      </button>
      <Modal
        open={showTable}
        onClose={() => setShowTable(false)}
        triggerRef={triggerRef}
        title={`Série mensal de ${label}`}
        description={`Valores mensais de ${label} simplificado e respectiva base no período.`}
        closeLabel={`Fechar dados de ${label}`}
        size="md"
        header="inline"
      >
        <div className="operation-series__table-wrap">
          <table className="operation-series__table font-sans">
            <caption className="sr-only">
              Série mensal de {label} simplificado
            </caption>
            <thead className="font-mono text-xs leading-[18px] text-muted [&_th]:font-normal">
              <tr>
                <th scope="col">Mês</th>
                <th scope="col">
                  {label} ({unit})
                </th>
                <th scope="col">Base (UCs)</th>
              </tr>
            </thead>
            <tbody>
              {values.map((point) => (
                <tr key={point.month}>
                  <th scope="row">{formatMonth(point.month)}</th>
                  <td>
                    {point[metric] === null
                      ? "Indisponível"
                      : `${formatNumber(point[metric]!)} ${unit}`}
                  </td>
                  <td>
                    {point.denominator === null
                      ? "Indisponível"
                      : point.denominator <= 0
                        ? `${formatNumber(point.denominator, 0)} · inválida`
                        : formatNumber(point.denominator, 0)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Modal>
    </section>
  );
}

export default function OperationSeries({
  period,
  series,
}: {
  period: OperationPeriod;
  series: SeriesPoint[];
}) {
  const values = chartValues(period, series);
  return (
    <div className="grid min-w-0 gap-4">
      <SeriesChart label="DEC" unit="h/UC" metric="dec" values={values} />
      <SeriesChart
        label="FEC"
        unit="interrupções/UC"
        metric="fec"
        values={values}
      />
    </div>
  );
}
