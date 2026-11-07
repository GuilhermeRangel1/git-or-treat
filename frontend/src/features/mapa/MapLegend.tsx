import type { MapLayer } from "./map-state";
import {
  compactLayerValue,
  formatCompetence,
  formatPeriod,
  layerValue,
} from "./map-format";

const labels: Record<MapLayer, string> = {
  revenue: "Faturamento no mês final · R$",
  consumption: "Consumo medido no mês final · kWh",
  revenue_change: "Variação entre os meses extremos · R$",
  consumption_change: "Variação entre os meses extremos · kWh",
};

export default function MapLegend({
  layer,
  start,
  end,
  min,
  max,
  diverging,
}: {
  layer: MapLayer;
  start: string;
  end: string;
  min: number | null;
  max: number | null;
  diverging: boolean;
}) {
  const classes = diverging
    ? ["--map-neg-4", "--map-neg-2", "--map-zero", "--map-pos-2", "--map-pos-4"]
    : [
        "--map-seq-1",
        "--map-seq-2",
        "--map-seq-3",
        "--map-seq-4",
        "--map-seq-5",
      ];
  const swatch = (color: string, title: string) => (
    <span
      className="rmr-legend__swatch"
      style={{ backgroundColor: `var(${color})` }}
      aria-label={title}
    />
  );
  const hasScale = min !== null && max !== null;
  return (
    <section
      className="rmr-legend rounded-xl border border-border bg-surface px-4 py-3"
      aria-label="Legenda da camada"
    >
      <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2">
        <div className="min-w-0">
          <h2 className="font-heading text-sm font-semibold text-content">
            {labels[layer]}
          </h2>
          <p className="mt-0.5 text-xs text-muted">
            {formatPeriod(start, end)}
            {diverging
              ? " · diferença absoluta entre os extremos"
              : ` · observado em ${formatCompetence(end)}`}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-muted">
          {hasScale ? (
            <span
              className="flex items-center gap-2"
              title={`Escala regional: ${layerValue(min, layer)} a ${layerValue(max, layer)}`}
            >
              <span className="tabular-nums">
                {compactLayerValue(min, layer)}
              </span>
              <span className="flex items-center gap-1">
                {classes.map((color, index) => (
                  <span key={color}>{swatch(color, `Faixa ${index + 1}`)}</span>
                ))}
              </span>
              <span className="tabular-nums">
                {compactLayerValue(max, layer)}
              </span>
            </span>
          ) : (
            <span>Sem valores comparáveis</span>
          )}
          <span className="flex items-center gap-2">
            {swatch("--map-zero", "Zero observado")}Zero observado
          </span>
          <span className="flex items-center gap-2">
            {swatch("--map-missing", "Sem observação")}Sem observação
          </span>
        </div>
      </div>
    </section>
  );
}
