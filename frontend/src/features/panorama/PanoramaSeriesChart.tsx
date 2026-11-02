import { useId, useLayoutEffect, useRef, useState } from "react";
import type { MonthlyDataPoint } from "../../shared/analytics/types";
import { formatCompetenciaLabel } from "../../shared/analytics/syntheticData";
import Modal from "../../shared/ui/Modal";
import "./panorama-series-chart.css";

interface PanoramaSeriesChartProps {
  data: MonthlyDataPoint[];
  partialPeriod?: string;
  selectedPeriod?: string;
  sourceKind?: "gold" | "synthetic";
}

type WindowSize = 12 | 24 | "all";

const chart = {
  width: 720,
  minWidth: 560,
  left: 104,
  rightInset: 16,
  top: 20,
  bottom: 202,
  height: 260,
};

const axisCurrency = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  notation: "compact",
  maximumFractionDigits: 1,
});

type ChartPoint = {
  competencia: string;
  value: number | null;
  x: number;
  y: number | null;
};

function formatCurrency(value: number) {
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
    maximumFractionDigits: 2,
  }).format(value);
}

function chartCoordinates(data: MonthlyDataPoint[], width: number) {
  const values = data
    .map((point) => point.receitaFaturada)
    .filter((value): value is number => value !== null);
  const left = chart.left;
  const right = Math.max(left + 1, width - chart.rightInset);

  if (values.length === 0) {
    return {
      points: data.map((point, index) => ({
        competencia: point.competencia,
        value: point.receitaFaturada,
        x:
          data.length < 2
            ? (left + right) / 2
            : left + ((right - left) * index) / (data.length - 1),
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
  ticks.sort((leftTick, rightTick) => rightTick - leftTick);

  return {
    points: data.map((point, index) => ({
      competencia: point.competencia,
      value: point.receitaFaturada,
      x:
        data.length < 2
          ? (left + right) / 2
          : left + ((right - left) * index) / (data.length - 1),
      y:
        point.receitaFaturada === null
          ? null
          : chart.top +
            ((maximum - point.receitaFaturada) / span) *
              (chart.bottom - chart.top),
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

export default function PanoramaSeriesChart({
  data,
  partialPeriod,
  selectedPeriod,
  sourceKind = "synthetic",
}: PanoramaSeriesChartProps) {
  const [showTable, setShowTable] = useState(false);
  const [windowSize, setWindowSize] = useState<WindowSize>(12);
  const [chartWidth, setChartWidth] = useState(chart.width);
  const [activeCompetence, setActiveCompetence] = useState<string | null>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const chartRef = useRef<SVGSVGElement>(null);
  const titleId = useId();
  const chartDescriptionId = useId();
  const tooltipId = useId();

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

  if (!data || data.length === 0) return null;

  const eligible = data.filter(
    (point) => !selectedPeriod || point.competencia <= selectedPeriod,
  );
  if (eligible.length === 0)
    return (
      <p className="rounded-lg bg-surface p-4 text-sm text-muted">
        Não há competências observadas até o mês selecionado.
      </p>
    );
  const visibleData = eligible.slice(windowSize === "all" ? 0 : -windowSize);
  const observed = visibleData.flatMap((point) =>
    point.receitaFaturada == null ? [] : [point.receitaFaturada],
  );
  const firstPoint = visibleData[0];
  const lastPoint = visibleData[visibleData.length - 1];
  const totalShown = visibleData.reduce(
    (total, point) => total + (point.receitaFaturada ?? 0),
    0,
  );
  const { points, ticks } = chartCoordinates(visibleData, chartWidth);
  const groups = pointGroups(points);
  const pointByCompetence = new Map(
    points.map((point) => [point.competencia, point]),
  );
  const activePoint = points.find(
    (point) => point.competencia === activeCompetence && point.value !== null,
  );
  const tickStep = Math.max(
    1,
    Math.ceil(
      visibleData.length /
        Math.max(2, Math.floor((chartWidth - chart.left) / 90)),
    ),
  );
  const monthTicks = visibleData.filter(
    (_, index) => index % tickStep === 0 || index === visibleData.length - 1,
  );
  const hasValues = points.some((point) => point.value !== null);
  const accessibleSummary = visibleData
    .map(
      (point) =>
        `${formatCompetenciaLabel(point.competencia)}: ${point.receitaFaturada === null ? "sem dado" : formatCurrency(point.receitaFaturada)}`,
    )
    .join("; ");

  return (
    <section aria-labelledby={titleId} className="panorama-series-chart">
      <h2 id={titleId} className="panorama-series-chart__title">
        Receita por competência
      </h2>
      <p className="mt-1 text-sm text-muted">Receita faturada por mês (BRL).</p>

      <div
        className="mt-4 flex flex-wrap items-center gap-2"
        aria-label="Janela da série"
      >
        <span className="text-xs text-muted">Exibir:</span>
        {([12, 24, "all"] as const).map((size) => (
          <button
            key={size}
            type="button"
            aria-pressed={windowSize === size}
            onClick={() => setWindowSize(size)}
            className="min-h-9 rounded-md border border-control px-3 text-xs text-content focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
          >
            {size === "all" ? "Todo o histórico" : `${size} meses`}
          </button>
        ))}
        <span className="ml-auto text-xs text-muted">
          {formatCompetenciaLabel(firstPoint.competencia)} –{" "}
          {formatCompetenciaLabel(lastPoint.competencia)}
        </span>
      </div>

      <figure className="panorama-series-chart__figure">
        <figcaption id={chartDescriptionId} className="sr-only">
          Receita faturada mensal entre{" "}
          {formatCompetenciaLabel(firstPoint.competencia)} e{" "}
          {formatCompetenciaLabel(lastPoint.competencia)}. Valores observados:{" "}
          {accessibleSummary}
        </figcaption>
        <div className="mt-4 min-w-0 max-w-full overflow-x-auto rounded-lg bg-canvas/50 px-2 py-2">
          <div className="panorama-series-chart__chart-enter">
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
                      {axisCurrency.format(tick)}
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
                    className="panorama-series-chart__line stroke-brand"
                    strokeWidth="3"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                ) : null,
              )}
              {points.map((point) => {
                if (point.value === null || point.y === null) return null;
                const monthLabel = formatCompetenciaLabel(point.competencia);
                const selected = point.competencia === selectedPeriod;
                return (
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
                      r={selected ? 5.5 : 4.5}
                      className={`panorama-series-chart__point fill-surface stroke-brand${selected ? " is-selected" : ""}`}
                      strokeWidth="3"
                      tabIndex={0}
                      role="img"
                      aria-describedby={
                        activeCompetence === point.competencia
                          ? tooltipId
                          : undefined
                      }
                      aria-label={`Exibir ${monthLabel}, faturamento ${formatCurrency(point.value)}${selected ? ", competência selecionada" : ""}${point.competencia === partialPeriod ? ", competência parcial" : ""}`}
                      data-partial={
                        point.competencia === partialPeriod || undefined
                      }
                      onMouseEnter={() =>
                        setActiveCompetence(point.competencia)
                      }
                      onMouseLeave={() => setActiveCompetence(null)}
                      onFocus={() => setActiveCompetence(point.competencia)}
                      onBlur={() => setActiveCompetence(null)}
                    />
                  </g>
                );
              })}

              {monthTicks.map((row, index) => {
                const point = pointByCompetence.get(row.competencia);
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
                    {formatCompetenciaLabel(row.competencia)}
                  </text>
                );
              })}

              {activePoint &&
              activePoint.value !== null &&
              activePoint.y !== null ? (
                <g
                  id={tooltipId}
                  role="tooltip"
                  aria-label={`${formatCompetenciaLabel(activePoint.competencia)}: ${formatCurrency(activePoint.value)}`}
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
                    Mês · {formatCompetenciaLabel(activePoint.competencia)}
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
                    {formatCurrency(activePoint.value).length > 13
                      ? axisCurrency.format(activePoint.value)
                      : formatCurrency(activePoint.value)}
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
        {partialPeriod ? (
          <p className="panorama-series-chart__summary">
            * Competência parcial; valor ainda não consolidado.
          </p>
        ) : null}
      </figure>

      <button
        ref={triggerRef}
        type="button"
        className="panorama-series-chart__details-link"
        aria-haspopup="dialog"
        onClick={() => setShowTable(true)}
      >
        Ver tabela da série →
      </button>

      <Modal
        open={showTable}
        onClose={() => setShowTable(false)}
        triggerRef={triggerRef}
        title="Tabela da série"
        description="Receita faturada por competência na janela exibida."
        closeLabel="Fechar dados da receita"
        size="md"
        header="inline"
      >
        <div className="panorama-series-chart__table-wrap">
          <table className="panorama-series-chart__table">
            <thead>
              <tr>
                <th scope="col">Competência</th>
                <th scope="col">Receita faturada</th>
              </tr>
            </thead>
            <tbody>
              {visibleData.map((point) => (
                <tr key={point.competencia}>
                  <th scope="row">
                    {formatCompetenciaLabel(point.competencia)}
                    {point.competencia === partialPeriod ? " · parcial" : ""}
                  </th>
                  <td>
                    {point.receitaFaturada == null
                      ? "Indisponível"
                      : formatCurrency(point.receitaFaturada)}
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr>
                <th scope="row">
                  {sourceKind === "synthetic"
                    ? "Soma dos meses exibidos (ilustrativa)"
                    : observed.length === 0
                      ? "Soma indisponível"
                      : observed.length === visibleData.length
                        ? "Soma dos meses exibidos"
                        : `Soma parcial · ${observed.length} de ${visibleData.length} valores observados`}
                </th>
                <td>
                  {observed.length === 0
                    ? "Indisponível"
                    : formatCurrency(totalShown)}
                </td>
              </tr>
            </tfoot>
          </table>
        </div>
      </Modal>
    </section>
  );
}
