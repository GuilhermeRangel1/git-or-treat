import { useId, useRef, useState } from "react";
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

const plotHeight = 164;

function formatCurrency(value: number) {
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
    maximumFractionDigits: 2,
  }).format(value);
}

function formatAxisValue(value: number) {
  return (value / 1000).toLocaleString("pt-BR", {
    maximumFractionDigits: 1,
  });
}

function getAxisMaximum(maxValue: number) {
  const rawStep = maxValue / 1000 / 2;
  const magnitude = 10 ** Math.floor(Math.log10(Math.max(rawStep, 1)));
  const normalizedStep = rawStep / magnitude;
  const niceStep =
    normalizedStep <= 1
      ? 1
      : normalizedStep <= 2
        ? 2
        : normalizedStep <= 5
          ? 5
          : 10;
  return Math.max(niceStep * magnitude * 2 * 1000, 1);
}

export default function PanoramaSeriesChart({
  data,
  partialPeriod,
  selectedPeriod,
  sourceKind = "synthetic",
}: PanoramaSeriesChartProps) {
  const [showTable, setShowTable] = useState(false);
  const [windowSize, setWindowSize] = useState<WindowSize>(12);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const titleId = useId();
  const chartDescriptionId = useId();

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
  const maxValue = Math.max(...observed, 0);
  const axisMaximum = getAxisMaximum(maxValue || 1000);
  const ticks = [axisMaximum, axisMaximum / 2, 0];
  const firstPoint = visibleData[0];
  const lastPoint = visibleData[visibleData.length - 1];
  const totalShown = visibleData.reduce(
    (total, point) => total + (point.receitaFaturada ?? 0),
    0,
  );
  const plotWidth = Math.max(visibleData.length - 1, 1) * 44;
  const xPosition = (index: number) =>
    visibleData.length === 1 ? plotWidth / 2 : index * 44;
  const spacedLabels = (count: number) =>
    new Set(
      visibleData.length <= count
        ? visibleData.map((_, index) => index)
        : Array.from({ length: count }, (_, index) =>
            Math.round((index * (visibleData.length - 1)) / (count - 1)),
          ),
    );
  const mobileLabelIndices = spacedLabels(Math.min(4, visibleData.length));
  const desktopLabelIndices =
    visibleData.length <= 12
      ? new Set(visibleData.map((_, index) => index))
      : spacedLabels(Math.min(6, visibleData.length));
  const yPosition = (value: number) =>
    28 + plotHeight - (value / axisMaximum) * plotHeight;
  const seriesSegments: string[] = [];
  let activeSegment: string[] = [];
  visibleData.forEach((point, index) => {
    if (point.receitaFaturada == null) {
      if (activeSegment.length) seriesSegments.push(activeSegment.join(" "));
      activeSegment = [];
      return;
    }
    activeSegment.push(
      `${activeSegment.length ? "L" : "M"} ${xPosition(index)} ${yPosition(point.receitaFaturada)}`,
    );
  });
  if (activeSegment.length) seriesSegments.push(activeSegment.join(" "));

  return (
    <section aria-labelledby={titleId} className="panorama-series-chart">
      <h2 id={titleId} className="panorama-series-chart__title">
        Receita por competência
      </h2>
      <p className="panorama-series-chart__caption">
        Valores em R$ mil por mês
      </p>

      <div
        className="flex flex-wrap items-center gap-2"
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
          {formatCompetenciaLabel(lastPoint.competencia)}. O gráfico exibe{" "}
          {visibleData.length} competências e usa uma escala em milhares de
          reais.
        </figcaption>
        <div
          className="panorama-series-chart__plot"
          role="group"
          aria-labelledby={`${titleId} ${chartDescriptionId}`}
        >
          <div className="panorama-series-chart__axis" aria-hidden="true">
            {ticks.map((tick) => (
              <span key={tick}>{formatAxisValue(tick)}</span>
            ))}
          </div>
          <div className="panorama-series-chart__line-wrap">
            <svg
              className="panorama-series-chart__line"
              viewBox={`0 0 ${plotWidth} 236`}
              preserveAspectRatio="none"
              role="img"
              aria-label="Tendência mensal da receita faturada"
            >
              {ticks.map((tick) => (
                <line
                  key={tick}
                  x1="0"
                  x2={plotWidth}
                  y1={yPosition(tick)}
                  y2={yPosition(tick)}
                  className="panorama-series-chart__gridline"
                />
              ))}
              {seriesSegments.map((segment, index) => (
                <path
                  key={index}
                  d={segment}
                  className="panorama-series-chart__path"
                />
              ))}
            </svg>
            {visibleData.map((point, index) => {
              const value = point.receitaFaturada;
              const monthLabel = formatCompetenciaLabel(point.competencia);
              const selected = point.competencia === selectedPeriod;
              if (value == null) return null;
              return (
                <button
                  key={point.competencia}
                  type="button"
                  className={`panorama-series-chart__point${selected ? " is-selected" : ""}`}
                  style={{
                    left: `${visibleData.length === 1 ? 50 : (index / (visibleData.length - 1)) * 100}%`,
                    top: `${yPosition(value)}px`,
                  }}
                  title={`${monthLabel} · ${formatCurrency(value)}`}
                  aria-label={`${monthLabel}: ${formatCurrency(value)}${selected ? ", competência selecionada" : ""}${point.competencia === partialPeriod ? ", competência parcial" : ""}`}
                  data-partial={
                    point.competencia === partialPeriod || undefined
                  }
                >
                  <span className="sr-only">{monthLabel}</span>
                </button>
              );
            })}
          </div>
          <div
            className="panorama-series-chart__x-axis"
            aria-hidden="true"
            style={{
              gridTemplateColumns: `repeat(${visibleData.length}, minmax(0, 1fr))`,
            }}
          >
            {visibleData.map((point, index) => {
              const monthLabel = formatCompetenciaLabel(point.competencia);
              return (
                <span key={point.competencia}>
                  {mobileLabelIndices.has(index) ? (
                    <span className="panorama-series-chart__tick--mobile">
                      {monthLabel}
                      {point.receitaFaturada == null ? " · —" : ""}
                    </span>
                  ) : null}
                  {desktopLabelIndices.has(index) ? (
                    <span className="panorama-series-chart__tick--desktop">
                      {monthLabel}
                      {point.receitaFaturada == null ? " · —" : ""}
                    </span>
                  ) : null}
                </span>
              );
            })}
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
