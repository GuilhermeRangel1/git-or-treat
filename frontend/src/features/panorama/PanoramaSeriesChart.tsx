import { useId, useRef, useState } from "react";
import type { MonthlyDataPoint } from "../../shared/analytics/types";
import { formatCompetenciaLabel } from "../../shared/analytics/syntheticData";
import Modal from "../../shared/ui/Modal";
import "./panorama-series-chart.css";

interface PanoramaSeriesChartProps {
  data: MonthlyDataPoint[];
  partialPeriod?: string;
  selectedPeriod?: string;
}

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

function monthFromLabel(label: string) {
  return label.split("/")[0];
}

export default function PanoramaSeriesChart({
  data,
  partialPeriod,
  selectedPeriod,
}: PanoramaSeriesChartProps) {
  const [showTable, setShowTable] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const titleId = useId();
  const chartDescriptionId = useId();

  if (!data || data.length === 0) return null;

  const maxValue = Math.max(...data.map((point) => point.receitaFaturada), 0);
  const axisMaximum = getAxisMaximum(maxValue || 1000);
  const ticks = [axisMaximum, axisMaximum / 2, 0];
  const firstPoint = data[0];
  const lastPoint = data[data.length - 1];
  const totalShown = data.reduce(
    (total, point) => total + point.receitaFaturada,
    0,
  );

  return (
    <section aria-labelledby={titleId} className="panorama-series-chart">
      <h2 id={titleId} className="panorama-series-chart__title">
        Receita ao longo do período
      </h2>
      <p className="panorama-series-chart__caption">
        Cenário sintético · R$ mil / mês
      </p>

      <figure className="panorama-series-chart__figure">
        <figcaption id={chartDescriptionId} className="sr-only">
          Receita faturada mensal entre{" "}
          {formatCompetenciaLabel(firstPoint.competencia)} e{" "}
          {formatCompetenciaLabel(lastPoint.competencia)}. O gráfico exibe{" "}
          {data.length} competências e usa uma escala em milhares de reais.
        </figcaption>
        <div
          className="panorama-series-chart__plot"
          role="img"
          aria-labelledby={`${titleId} ${chartDescriptionId}`}
        >
          <div className="panorama-series-chart__axis" aria-hidden="true">
            {ticks.map((tick) => (
              <span key={tick}>{formatAxisValue(tick)}</span>
            ))}
          </div>
          <div
            className="panorama-series-chart__bars"
            aria-hidden="true"
            style={{
              gridTemplateColumns: `repeat(${data.length}, minmax(0, 1fr))`,
            }}
          >
            <div className="panorama-series-chart__gridlines">
              {ticks.map((tick) => (
                <span key={tick} />
              ))}
            </div>
            {data.map((point, index) => {
              const height = (point.receitaFaturada / axisMaximum) * plotHeight;
              const isSelected = point.competencia === selectedPeriod;
              const isPartial = point.competencia === partialPeriod;
              const isCurrent = isSelected && index === data.length - 1;

              return (
                <div
                  key={point.competencia}
                  className="panorama-series-chart__item"
                >
                  <span className="panorama-series-chart__value">
                    {formatAxisValue(point.receitaFaturada)}
                  </span>
                  <div
                    className={`panorama-series-chart__bar${isSelected && height > 0 ? " is-selected" : ""}`}
                    style={{ height: `${height}px` }}
                    data-partial={isPartial || undefined}
                  />
                  <span className="panorama-series-chart__month">
                    <span className="panorama-series-chart__month-short">
                      {monthFromLabel(
                        formatCompetenciaLabel(point.competencia),
                      )}
                      {isPartial ? "*" : ""}
                    </span>
                    <span className="panorama-series-chart__month-full">
                      {formatCompetenciaLabel(point.competencia)}
                      {isPartial ? "*" : ""}
                    </span>
                    {isCurrent ? (
                      <span className="panorama-series-chart__current">
                        Atual
                      </span>
                    ) : null}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
        <p className="panorama-series-chart__summary">
          Receita faturada de {formatCurrency(firstPoint.receitaFaturada)} em{" "}
          {formatCompetenciaLabel(firstPoint.competencia)} a{" "}
          {formatCurrency(lastPoint.receitaFaturada)} em{" "}
          {formatCompetenciaLabel(lastPoint.competencia)}.
          {partialPeriod
            ? " * Competência parcial; valor ainda não consolidado."
            : ""}
        </p>
      </figure>

      <button
        ref={triggerRef}
        type="button"
        className="panorama-series-chart__details-link"
        aria-haspopup="dialog"
        onClick={() => setShowTable(true)}
      >
        Ver dados da receita →
      </button>

      <Modal
        open={showTable}
        onClose={() => setShowTable(false)}
        triggerRef={triggerRef}
        title="Dados da receita"
        description="Receita faturada por competência no recorte exibido."
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
              {data.map((point) => (
                <tr key={point.competencia}>
                  <th scope="row">
                    {formatCompetenciaLabel(point.competencia)}
                    {point.competencia === partialPeriod ? " · parcial" : ""}
                  </th>
                  <td>{formatCurrency(point.receitaFaturada)}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr>
                <th scope="row">Soma dos meses exibidos (ilustrativa)</th>
                <td>{formatCurrency(totalShown)}</td>
              </tr>
            </tfoot>
          </table>
        </div>
      </Modal>
    </section>
  );
}
