import { currentAuthorizationGeneration } from "../auth/authorization";
import { getGoldGeneration } from "./goldPublication";
import DistributionGraphic from "./DistributionGraphic";
import { visualValue } from "./visual-format";
import { useEffect, useId, useRef, useState } from "react";
import { Download, Table2 } from "lucide-react";
import { exportChartPng, exportChartCsv } from "./visual-export";
import type { VisualReading } from "./visualReading";
import ChartBoundary from "./ChartBoundary";

export interface VisualEvidenceData {
  reading?: VisualReading | null;
  kind?: "bars" | "horizontal" | "donut" | "line" | "waterfall";
  total?: number;
  note?: string;
  tablePoints?: VisualEvidenceData["points"];
  categoryLabel?: string;
  isDemo?: boolean;
  title: string;
  unit: string;
  precision?: number;
  scope: string;
  points: { label: string; value: number | null; percentage?: number | null }[];
}

/** Presentation only: values have already been computed by the authorized source. */
export default function VisualEvidence({
  data,
  canExport = () => true,
  exportsEnabled = true,
  tableEnabled = true,
}: {
  data: VisualEvidenceData;
  canExport?: () => boolean | Promise<boolean>;
  exportsEnabled?: boolean;
  tableEnabled?: boolean;
}) {
  const id = useId();
  const svg = useRef<SVGSVGElement>(null);
  const active = useRef(true);
  const authorization = useRef(currentAuthorizationGeneration());
  const publication = useRef(getGoldGeneration());
  const busy = useRef(false);
  useEffect(() => {
    active.current = true;
    return () => {
      active.current = false;
    };
  }, []);
  const [table, setTable] = useState(false);
  const [page, setPage] = useState(0);
  const tablePoints = data.tablePoints ?? data.points;
  const pageCount = Math.ceil(tablePoints.length / 20);
  const [error, setError] = useState("");
  const [exporting, setExporting] = useState(false);
  if (
    !data.points.length ||
    data.points.length > 24 ||
    tablePoints.length > 1000 ||
    data.points.some((p) => p.value !== null && !Number.isFinite(p.value))
  )
    return null;
  const hasPercentages = tablePoints.some((p) => p.percentage != null);
  const values = data.points
    .map((p) => p.value)
    .filter((v): v is number => v !== null);
  // A single observation is a metric, not an invented comparison.
  const comparable = values.length > 1;
  let running = 0;
  const steps = data.kind === "waterfall" ? values.map((value) => {
    const start = running;
    running += value;
    return { start, end: running };
  }) : [];
  const minimum = Math.min(0, ...values, ...steps.map((step) => step.end));
  const maximum = Math.max(0, ...values, ...steps.map((step) => step.end));
  const span = maximum - minimum || 1;
  const y = (v: number) => 210 - ((v - minimum) / span) * 160;
  const cellWidth = Math.max(
    110,
    ...data.points.map((p) =>
      Math.max(
        p.label.length,
        visualValue(p.value, data.unit, data.precision).length,
      ) * 10 + 24,
    ),
  );
  const width = Math.max(400, data.points.length * cellWidth + 80);
  const cell = (width - 80) / data.points.length;
  async function download(kind: "png" | "csv") {
    if (busy.current) return;
    busy.current = true;
    setError("");
    setExporting(true);
    const allowed = async () => {
      const current = () =>
        active.current &&
        authorization.current === currentAuthorizationGeneration() &&
        publication.current === getGoldGeneration();
      if (!current()) return false;
      const permitted = await canExport();
      return permitted && current();
    };
    try {
      if (kind === "csv") {
        if (!(await allowed())) {
          if (active.current)
            setError(
              "Os dados mudaram ou o acesso não pôde ser confirmado. Atualize a consulta antes de baixar.",
            );
          return;
        }
        exportChartCsv(data);
      } else if (svg.current) {
        await exportChartPng(svg.current, data, allowed);
      } else
        throw new Error("Gráfico indisponível; consulte a tabela ou o CSV.");
    } catch {
      if (active.current)
        setError(
          "Não foi possível confirmar o acesso ou baixar o arquivo. Atualize a consulta e tente novamente.",
        );
    } finally {
      busy.current = false;
      if (active.current) setExporting(false);
    }
  }
  return (
    <section
      aria-labelledby={`${id}-title`}
      className="min-w-0 rounded-xl border border-divider bg-surface p-4 sm:p-5"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted">
            Dados do recorte
          </p>
          <h3
            id={`${id}-title`}
            className="mt-1 font-heading text-lg font-semibold text-content"
          >
            {data.title}
          </h3>
          <p className="mt-1 break-words text-xs leading-5 text-muted">
            {data.scope}
          </p>
        </div>
        {tableEnabled && (
          <button
            type="button"
            aria-expanded={table}
            aria-controls={`${id}-table`}
            onClick={() => setTable(!table)}
            className="inline-flex min-h-10 items-center gap-2 rounded-lg border border-divider px-3 text-xs font-medium text-content hover:bg-surface-hover focus-visible:outline-2 focus-visible:outline-brand"
          >
            <Table2 className="size-4" aria-hidden="true" />
            {table
              ? "Ocultar tabela"
              : tablePoints.length > data.points.length
                ? `Ver lista completa (${tablePoints.length})`
                : "Ver tabela"}
          </button>
        )}
      </div>
      <ChartBoundary>
        {comparable ? (
          <div
            className={`mt-3 overflow-x-auto ${data.kind === "horizontal" ? "max-h-[320px] overflow-y-auto" : ""}`}
            role="region"
            aria-label="Gráfico com rolagem"
            tabIndex={0}
          >
            {data.kind === "horizontal" || data.kind === "donut" ? (
              <DistributionGraphic data={data} svgRef={svg} id={id} />
            ) : (
              <svg
                ref={svg}
                role="img"
                aria-labelledby={`${id}-chart-title`}
                aria-describedby={`${id}-chart-desc`}
                viewBox={`0 0 ${width} 270`}
                preserveAspectRatio="xMinYMin meet"
                style={{
                  minWidth: Math.max(260, data.points.length * cellWidth),
                }}
                className="w-full min-w-[260px] max-h-[210px] text-content"
              >
                <title id={`${id}-chart-title`}>{data.title}</title>
                <desc id={`${id}-chart-desc`}>
                  {data.points
                    .map(
                      (p) =>
                        `${p.label}: ${visualValue(p.value, data.unit, data.precision)}`,
                    )
                    .join("; ")}
                </desc>
                <text x="40" y="20" fill="currentColor" fontSize="12">
                  {data.unit}
                </text>
                {[0, 0.5, 1].map((t) => (
                  <line
                    key={t}
                    x1="40"
                    x2={width - 40}
                    y1={50 + t * 160}
                    y2={50 + t * 160}
                    stroke="var(--line)"
                    strokeDasharray="4 5"
                  />
                ))}
                <line
                  x1="40"
                  x2={width - 40}
                  y1={y(0)}
                  y2={y(0)}
                  stroke="var(--line)"
                />
                {data.kind === "line" && (
                  <polyline
                    fill="none"
                    stroke="var(--accent-goiaba)"
                    strokeWidth="2.5"
                    points={
                      data.points.every((p) => p.value !== null)
                        ? data.points
                            .map(
                              (p, i) =>
                                `${40 + i * cell + cell / 2},${y(p.value!)}`,
                            )
                            .join(" ")
                        : ""
                    }
                  />
                )}
                {data.points.map((point, i) => {
                  const x = 40 + i * cell + cell / 2;
                  const valueY = y(steps[i]?.end ?? point.value ?? 0);
                  const baseY = y(steps[i]?.start ?? 0);
                  return (
                    <g key={`${i}-${point.label}`}>
                      {point.value !== null && data.kind === "line" && (
                        <circle
                          cx={x}
                          cy={valueY}
                          r="4"
                          fill="var(--accent-goiaba)"
                        >
                          <title>
                            {point.label}:{" "}
                            {visualValue(
                              point.value,
                              data.unit,
                              data.precision,
                            )}
                          </title>
                        </circle>
                      )}
                      {point.value !== null && data.kind !== "line" && (
                        <rect
                          x={x - Math.min(cell * 0.3, 42)}
                          y={Math.min(baseY, valueY)}
                          width={Math.min(cell * 0.6, 84)}
                          height={Math.abs(baseY - valueY)}
                          rx="5"
                          fill={
                            i === data.points.length - 1
                              ? "var(--accent-goiaba)"
                              : "var(--accent-pistache)"
                          }
                        >
                          <title>
                            {point.label}:{" "}
                            {visualValue(
                              point.value,
                              data.unit,
                              data.precision,
                            )}
                          </title>
                        </rect>
                      )}
                      <text
                        x={x}
                        y={Math.max(
                          36,
                          Math.min(
                            230,
                            valueY +
                              (point.value !== null && point.value < 0
                                ? 22
                                : -10),
                          ),
                        )}
                        textAnchor="middle"
                        fill="currentColor"
                        fontSize="16"
                        fontWeight="600"
                      >
                        {point.value === null
                          ? "N/D"
                          : visualValue(point.value, data.unit, data.precision)}
                      </text>
                      <text
                        x={x}
                        y="244"
                        textAnchor="middle"
                        fill="currentColor"
                        fontSize="16"
                      >
                        {point.label}
                      </text>
                    </g>
                  );
                })}
              </svg>
            )}
          </div>
        ) : (
          <div className="mt-5 space-y-1 border-l-4 border-[var(--accent-goiaba)] pl-4">
            {data.points.map((point, i) => (
              <div key={`${i}-${point.label}`} className="py-1">
                <p className="font-heading text-2xl font-semibold text-content">
                  {visualValue(point.value, data.unit, data.precision)}
                </p>
                <p className="text-sm text-muted">{point.label}</p>
              </div>
            ))}
          </div>
        )}
      </ChartBoundary>
      {data.note && (
        <p className="mt-3 text-xs leading-5 text-muted">{data.note}</p>
      )}
      {data.reading && (
        <div
          className="mt-4 space-y-2 border-l-2 border-[var(--accent-pistache)] pl-3 text-sm leading-6 text-content"
          aria-label="Leitura do gráfico"
        >
          <p className="font-semibold">Leitura do gráfico</p>
          <p>{data.reading.summary}</p>
          <p className="text-muted">
            <strong className="font-medium">Próximo passo: </strong>
            {data.reading.next_step}
          </p>
        </div>
      )}
      {table && (
        <div
          id={`${id}-table`}
          className="mt-4 overflow-x-auto rounded-lg border border-divider"
          tabIndex={0}
          role="region"
          aria-label="Tabela do gráfico"
        >
          <table className="w-full text-left text-sm">
            <caption className="sr-only">
              {data.title} — lista completa do recorte
            </caption>
            <thead className="bg-canvas text-muted">
              <tr>
                <th scope="col" className="p-3">
                  {data.categoryLabel ?? "Período"}
                </th>
                <th scope="col" className="p-3 text-right">
                  Valor ({data.unit})
                </th>
                {hasPercentages && (
                  <th scope="col" className="p-3 text-right">
                    Participação
                  </th>
                )}
              </tr>
            </thead>
            <tbody>
              {tablePoints.slice(page * 20, (page + 1) * 20).map((p, i) => (
                <tr key={i} className="border-t border-divider">
                  <th scope="row" className="p-3 font-normal">
                    {p.label}
                  </th>
                  <td className="p-3 text-right tabular-nums">
                    {visualValue(p.value, data.unit, data.precision)}
                  </td>
                  {hasPercentages && (
                    <td className="p-3 text-right">
                      {p.percentage == null
                        ? "—"
                        : `${p.percentage.toLocaleString("pt-BR")}%`}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
          {pageCount > 1 && (
            <div className="flex flex-wrap items-center justify-between gap-2 border-t border-divider p-3 text-xs">
              <button
                type="button"
                disabled={page === 0}
                onClick={() => setPage(page - 1)}
                className="min-h-10 rounded px-2 font-semibold text-brand disabled:opacity-40 focus-visible:outline-2 focus-visible:outline-brand"
              >
                Anterior
              </button>
              <span role="status">
                Página {page + 1} de {pageCount} · {tablePoints.length} grupos
              </span>
              <button
                type="button"
                disabled={page + 1 === pageCount}
                onClick={() => setPage(page + 1)}
                className="min-h-10 rounded px-2 font-semibold text-brand disabled:opacity-40 focus-visible:outline-2 focus-visible:outline-brand"
              >
                Próxima
              </button>
            </div>
          )}
        </div>
      )}
      {exportsEnabled && (
        <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-divider pt-3">
          {comparable && (
            <button
              type="button"
              disabled={exporting}
              onClick={() => void download("png")}
              className="inline-flex min-h-10 items-center gap-2 rounded-md px-1 text-xs font-semibold text-brand focus-visible:outline-2 focus-visible:outline-brand disabled:opacity-50"
            >
              <Download className="size-4" aria-hidden="true" />
              Baixar gráfico (PNG)
            </button>
          )}
          <button
            type="button"
            disabled={exporting}
            onClick={() => void download("csv")}
            className="inline-flex min-h-10 items-center gap-2 rounded-md px-1 text-xs font-semibold text-brand focus-visible:outline-2 focus-visible:outline-brand disabled:opacity-50"
          >
            <Download className="size-4" aria-hidden="true" />
            Baixar dados (CSV)
          </button>
          <span className="text-xs text-muted">
            {data.isDemo ? "Dados de demonstração" : "Fonte de dados interna"}
          </span>
        </div>
      )}
      {error && (
        <p role="alert" className="mt-2 text-sm text-[var(--status-danger)]">
          {error}
        </p>
      )}
    </section>
  );
}
