import { useId, useLayoutEffect, useRef, useState } from "react";
import Modal from "@/shared/ui/Modal";
import { formatUCCompetence } from "./uc360-format";
import "./uc360-series.css";

type Point = { competencia: string; measured_energy_kwh: number | null };
type ChartPoint = Point & { x: number; y: number | null };

const decimal = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2 });
const axisDecimal = new Intl.NumberFormat("pt-BR", {
  notation: "compact",
  maximumFractionDigits: 1,
});
const chart = {
  width: 720,
  minWidth: 560,
  left: 76,
  rightInset: 16,
  top: 20,
  bottom: 202,
  height: 260,
};

const monthIndex = (month: string) =>
  Number(month.slice(0, 4)) * 12 + Number(month.slice(5, 7));

function formatKwh(value: number | null) {
  return value === null ? "Sem dado" : `${decimal.format(value)} kWh`;
}

function pointGroups(points: ChartPoint[]) {
  const groups: ChartPoint[][] = [];
  let current: ChartPoint[] = [];

  for (const point of points) {
    if (
      point.y === null ||
      (current.length > 0 &&
        monthIndex(point.competencia) !==
          monthIndex(current[current.length - 1].competencia) + 1)
    ) {
      if (current.length > 0) groups.push(current);
      current = [];
    }
    if (point.y !== null) current.push(point);
  }

  if (current.length > 0) groups.push(current);
  return groups;
}

function linePath(points: ChartPoint[]) {
  return points
    .map((point, index) => `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`)
    .join(" ");
}

export default function UC360Series({
  data,
  previous,
  pending,
  error,
  onRetry,
}: {
  data?: { items: Point[] };
  previous?: {
    data?: { items: Point[] };
    pending: boolean;
    error: Error | null;
  };
  pending: boolean;
  error: Error | null;
  onRetry: () => void;
}) {
  const rows = [...(data?.items ?? [])].sort((a, b) =>
    a.competencia.localeCompare(b.competencia),
  );
  const previousValues = new Map(
    previous?.data?.items.map((item) => [
      item.competencia,
      item.measured_energy_kwh,
    ]),
  );
  const chartRef = useRef<SVGSVGElement>(null);
  const tableTriggerRef = useRef<HTMLButtonElement>(null);
  const [chartWidth, setChartWidth] = useState(chart.width);
  const [activeCompetence, setActiveCompetence] = useState<string | null>(null);
  const [showTable, setShowTable] = useState(false);
  const tooltipId = useId();
  const hasChart =
    !pending && !error && rows.some((row) => row.measured_energy_kwh !== null);

  useLayoutEffect(() => {
    const svg = chartRef.current;
    if (!svg || !hasChart) return;

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
  }, [hasChart]);

  const values = rows.flatMap((row) =>
    row.measured_energy_kwh === null ? [] : [row.measured_energy_kwh],
  );
  const minimum = Math.min(0, ...values);
  const observedMaximum = Math.max(0, ...values);
  const maximum = observedMaximum || 1;
  const span = maximum - minimum || 1;
  const plotWidth = Math.max(1, chartWidth - chart.left - chart.rightInset);
  const points: ChartPoint[] = rows.map((row, index) => ({
    ...row,
    x:
      rows.length < 2
        ? chart.left + plotWidth / 2
        : chart.left +
          ((chartWidth - chart.left - chart.rightInset) * index) /
            (rows.length - 1),
    y:
      row.measured_energy_kwh === null
        ? null
        : chart.top +
          ((maximum - row.measured_energy_kwh) / span) *
            (chart.bottom - chart.top),
  }));
  const groups = pointGroups(points);
  const pointByCompetence = new Map(
    points.map((point) => [point.competencia, point]),
  );
  const activePoint = points.find(
    (point) =>
      point.competencia === activeCompetence &&
      point.measured_energy_kwh !== null,
  );
  const ticks = Array.from(
    { length: 5 },
    (_, index) => maximum - (span * index) / 4,
  );
  const tickStep = Math.max(
    1,
    Math.ceil(
      rows.length / Math.max(2, Math.floor((chartWidth - chart.left) / 90)),
    ),
  );
  const monthTicks = rows.filter(
    (_, index) => index % tickStep === 0 || index === rows.length - 1,
  );
  const hasPreviousData = Boolean(previous?.data);
  const accessibleSummary = rows
    .map(
      (row) =>
        `${formatUCCompetence(row.competencia)}: ${formatKwh(row.measured_energy_kwh)}`,
    )
    .join("; ");

  return (
    <section
      aria-label="Série mensal de consumo"
      className="uc360-series min-w-0 rounded-xl border border-border bg-surface p-4 text-content sm:p-5"
    >
      <h2 className="uc360-series__title">Série mensal de consumo medido</h2>
      <p className="mt-1 text-sm text-muted">
        Consumo medido por competência (kWh). Meses sem valor ou registro não
        representam consumo zero.
      </p>

      {pending && (
        <p role="status" className="mt-3 text-sm text-muted">
          Carregando série…
        </p>
      )}
      {error && (
        <p role="alert" className="mt-3 text-sm text-muted">
          Não foi possível carregar a série de consumo.{" "}
          <button type="button" className="underline" onClick={onRetry}>
            Tentar novamente
          </button>
        </p>
      )}
      {!pending && !error && values.length === 0 && (
        <p className="mt-3 text-sm text-muted">
          Sem valores de consumo disponíveis para este período.
        </p>
      )}

      {hasChart && (
        <figure className="uc360-series__figure">
          <figcaption className="sr-only">
            Consumo medido mensal entre{" "}
            {formatUCCompetence(rows[0].competencia)} e{" "}
            {formatUCCompetence(rows[rows.length - 1].competencia)}. Valores
            observados: {accessibleSummary}
          </figcaption>
          <div className="uc360-series__plot-wrap bg-canvas/50">
            <div className="uc360-series__chart-enter">
              <svg
                ref={chartRef}
                className="block h-64 min-w-[560px] w-full"
                viewBox={`0 0 ${chartWidth} ${chart.height}`}
                role="img"
                aria-label={`Consumo medido mensal em kWh. ${accessibleSummary}`}
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
                        {axisDecimal.format(tick)}
                      </text>
                    </g>
                  );
                })}

                {groups.map((group) =>
                  group.length > 1 ? (
                    <path
                      key={`line-${group[0].competencia}`}
                      d={linePath(group)}
                      pathLength="1"
                      fill="none"
                      className="uc360-series__line stroke-brand"
                      strokeWidth="3"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  ) : null,
                )}

                {points.map((point) => {
                  if (point.measured_energy_kwh === null || point.y === null)
                    return null;
                  const label = formatUCCompetence(point.competencia);
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
                        r={point.competencia === activeCompetence ? 5.5 : 4.5}
                        className="uc360-series__point fill-surface stroke-brand"
                        strokeWidth="3"
                        tabIndex={0}
                        role="img"
                        aria-describedby={
                          point.competencia === activeCompetence
                            ? tooltipId
                            : undefined
                        }
                        aria-label={`Exibir ${label}, consumo medido ${formatKwh(point.measured_energy_kwh)}`}
                        onMouseEnter={() =>
                          setActiveCompetence(point.competencia)
                        }
                        onMouseLeave={() => setActiveCompetence(null)}
                        onFocus={() => setActiveCompetence(point.competencia)}
                        onBlur={() => setActiveCompetence(null)}
                      >
                        <title>
                          {formatUCCompetence(point.competencia)}:{" "}
                          {formatKwh(point.measured_energy_kwh)}
                        </title>
                      </circle>
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
                      {formatUCCompetence(row.competencia)}
                    </text>
                  );
                })}

                {activePoint &&
                activePoint.measured_energy_kwh !== null &&
                activePoint.y !== null ? (
                  <g
                    id={tooltipId}
                    role="tooltip"
                    aria-label={`${formatUCCompetence(activePoint.competencia)}: ${formatKwh(activePoint.measured_energy_kwh)}`}
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
                      Mês · {formatUCCompetence(activePoint.competencia)}
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
                      {formatKwh(activePoint.measured_energy_kwh)}
                    </text>
                  </g>
                ) : null}
              </svg>
            </div>
          </div>
        </figure>
      )}

      {rows.length > 0 && !pending && !error ? (
        <button
          ref={tableTriggerRef}
          type="button"
          className="uc360-series__details-link"
          aria-haspopup="dialog"
          onClick={() => setShowTable(true)}
        >
          Ver tabela da série →
        </button>
      ) : null}

      <Modal
        open={showTable}
        onClose={() => setShowTable(false)}
        triggerRef={tableTriggerRef}
        title="Tabela da série"
        description="Consumo medido por competência e comparação com o mesmo mês do ano anterior."
        closeLabel="Fechar dados da série"
        size="md"
        header="inline"
      >
        {previous?.pending ? (
          <p role="status" className="text-sm text-muted">
            Carregando comparação com o ano anterior…
          </p>
        ) : null}
        {previous?.error ? (
          <p role="alert" className="text-sm text-muted">
            Não foi possível carregar a comparação com o ano anterior.{" "}
            <button type="button" className="underline" onClick={onRetry}>
              Tentar novamente
            </button>
          </p>
        ) : null}
        {!hasPreviousData && !previous?.pending && !previous?.error ? (
          <p className="text-sm text-muted">
            A comparação com o ano anterior não está disponível.
          </p>
        ) : null}
        <div className="uc360-series__table-wrap">
          <table className="uc360-series__table font-sans">
            <caption className="sr-only">
              Consumo medido mensal e comparação com o mesmo mês do ano anterior
            </caption>
            <colgroup>
              <col className={hasPreviousData ? "w-1/4" : "w-1/2"} />
              <col className={hasPreviousData ? "w-[37.5%]" : "w-1/2"} />
              {hasPreviousData ? <col className="w-[37.5%]" /> : null}
            </colgroup>
            <thead className="font-mono text-xs leading-[18px] text-muted [&_th]:font-normal">
              <tr>
                <th scope="col">Competência</th>
                <th scope="col">Consumo no mês</th>
                {hasPreviousData ? (
                  <th scope="col">Mesmo mês do ano anterior</th>
                ) : null}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const priorMonth = `${String(Number(row.competencia.slice(0, 4)) - 1).padStart(4, "0")}${row.competencia.slice(4)}`;
                return (
                  <tr key={row.competencia}>
                    <th scope="row">{formatUCCompetence(row.competencia)}</th>
                    <td>{formatKwh(row.measured_energy_kwh)}</td>
                    {hasPreviousData ? (
                      <td>
                        {formatKwh(previousValues.get(priorMonth) ?? null)}
                      </td>
                    ) : null}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Modal>
    </section>
  );
}
