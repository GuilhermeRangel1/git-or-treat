import type { RefObject } from "react";
import type { VisualEvidenceData } from "./VisualEvidence";
import { visualValue } from "./visual-format";

const colors = [
  "var(--accent-goiaba)",
  "var(--accent-pistache)",
  "#a47653",
  "#667c91",
  "#ad7294",
  "#99904b",
];

function labelLines(label: string) {
  const lines: string[] = [""];
  for (const word of label.split(/\s+/)) {
    const parts = word.match(/.{1,36}/gu) ?? [word];
    for (const part of parts) {
      const last = lines.length - 1;
      if (lines[last] && lines[last].length + part.length + 1 > 38)
        lines.push(part);
      else lines[last] += (lines[last] ? " " : "") + part;
    }
  }
  return lines;
}

export default function DistributionGraphic({
  data,
  svgRef,
  id,
}: {
  data: VisualEvidenceData;
  svgRef: RefObject<SVGSVGElement | null>;
  id: string;
}) {
  const donut =
    data.kind === "donut" &&
    data.points.length <= 6 &&
    (data.total ?? 0) > 0 &&
    data.points.every(
      (p) => p.value !== null && p.value >= 0 && p.percentage != null,
    );
  let nextY = donut ? 185 : 25;
  const rows: { lines: string[]; y: number }[] = [];
  for (const point of data.points) {
    const lines = labelLines(point.label);
    const y = nextY;
    nextY += lines.length * 16 + (donut ? 30 : 60);
    rows.push({ lines, y });
  }
  const height = nextY;
  const min = Math.min(0, ...data.points.map((p) => p.value ?? 0));
  const max = Math.max(0, ...data.points.map((p) => p.value ?? 0));
  const x = (value: number) => 20 + ((value - min) / (max - min || 1)) * 360;
  return (
    <>
      <svg
        ref={svgRef}
        role="img"
        aria-labelledby={`${id}-distribution-title`}
        aria-describedby={`${id}-distribution-description`}
        viewBox={donut ? "60 0 280 180" : `0 0 400 ${height}`}
        data-export-viewbox={donut ? `0 0 400 ${height}` : undefined}
        className={`mx-auto w-full text-content ${donut ? "max-w-[260px]" : "min-w-[260px] max-w-[340px]"}`}
      >
        <title id={`${id}-distribution-title`}>{data.title}</title>
        <desc id={`${id}-distribution-description`}>
          {data.points
            .map(
              (p) =>
                `${p.label}: ${visualValue(p.value, data.unit, data.precision)}${p.percentage == null ? "" : ` (${p.percentage}%)`}`,
            )
            .join("; ")}
        </desc>
        {donut && (
          <>
            {data.points.map((p, i) => {
              const current = data.points
                .slice(0, i)
                .reduce((sum, item) => sum + (item.percentage ?? 0), 0);
              return (
                <circle
                  key={p.label}
                  cx="200"
                  cy="88"
                  r="60"
                  fill="none"
                  stroke={colors[i]}
                  strokeWidth="24"
                  pathLength="100"
                  strokeDasharray={`${p.percentage} ${100 - (p.percentage ?? 0)}`}
                  strokeDashoffset={-current}
                  transform="rotate(-90 200 88)"
                >
                  <title>
                    {p.label}: {visualValue(p.value, data.unit, data.precision)}
                  </title>
                </circle>
              );
            })}
            <text
              x="200"
              y="82"
              textAnchor="middle"
              fill="currentColor"
              fontSize="12"
            >
              Total do recorte
            </text>
            <text
              x="200"
              y="105"
              textAnchor="middle"
              fill="currentColor"
              fontSize="17"
              fontWeight="600"
            >
              {data.total == null
                ? "—"
                : new Intl.NumberFormat("pt-BR", {
                    notation: "compact",
                    maximumFractionDigits: 1,
                  }).format(data.total)}
            </text>
            <text
              x="200"
              y="123"
              textAnchor="middle"
              fill="currentColor"
              fontSize="11"
            >
              {data.unit}
            </text>
          </>
        )}
        <g
          data-export-only={donut ? "true" : undefined}
          style={donut ? { display: "none" } : undefined}
        >
          {data.points.map((p, i) => {
            const { lines, y } = rows[i];
            return (
              <g key={p.label}>
                {donut && <circle cx="12" cy={y - 5} r="5" fill={colors[i]} />}
                <text
                  x={donut ? 28 : 20}
                  y={y}
                  fill="currentColor"
                  fontSize="14"
                  fontWeight="500"
                >
                  {lines.map((line, j) => (
                    <tspan key={j} x={donut ? 28 : 20} dy={j === 0 ? 0 : 16}>
                      {line}
                    </tspan>
                  ))}
                </text>
                <text
                  x={donut ? 28 : 20}
                  y={y + Math.max(1, lines.length - 1) * 16 + 9}
                  fill="currentColor"
                  fontSize="13"
                >
                  {visualValue(p.value, data.unit, data.precision)}
                  {p.percentage == null
                    ? ""
                    : ` · ${p.percentage.toLocaleString("pt-BR", { maximumFractionDigits: 2 })}%`}
                </text>
                {!donut && p.value !== null && (
                  <rect
                    x={Math.min(x(0), x(p.value))}
                    y={y + lines.length * 16 + 28}
                    width={Math.max(0, Math.abs(x(p.value) - x(0)))}
                    height="12"
                    rx="4"
                    fill="var(--accent-goiaba)"
                  />
                )}
              </g>
            );
          })}
        </g>
      </svg>
      {donut && (
        <ul
          tabIndex={0}
          aria-label="Legenda do gráfico; role para ver todos os setores"
          className="mt-2 grid max-h-[144px] gap-x-5 gap-y-2 overflow-y-auto overscroll-contain pr-1 focus-visible:outline-2 focus-visible:outline-brand sm:max-h-none sm:grid-cols-2"
        >
          {data.points.map((p, i) => (
            <li
              key={p.label}
              className="flex min-w-0 items-start justify-between gap-2 border-b border-divider/50 py-1.5 last:border-b-0"
            >
              <span className="flex min-w-0 gap-2 text-sm leading-5 text-content">
                <span
                  aria-hidden="true"
                  className="mt-1.5 size-2 shrink-0 rounded-full"
                  style={{ background: colors[i] }}
                />
                {p.label}
              </span>
              <span className="shrink-0 text-right text-xs leading-5 text-muted">
                {visualValue(p.value, data.unit, data.precision)}
                <br />
                <strong className="font-semibold text-content">
                  {p.percentage?.toLocaleString("pt-BR", {
                    maximumFractionDigits: 2,
                  })}
                  %
                </strong>
              </span>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
