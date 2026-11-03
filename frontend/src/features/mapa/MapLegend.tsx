import type { MapLayer } from "./map-state";

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
  return (
    <section
      className="rmr-legend rounded-xl border border-border bg-surface p-4"
      aria-label="Legenda da camada"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="font-heading text-sm font-semibold text-content">
            {labels[layer]}
          </h2>
          <p className="mt-1 text-xs text-muted">
            {start} a {end}
            {layer === "revenue" || layer === "consumption"
              ? ` · observado em ${end}`
              : " · diferença absoluta entre extremos"}
          </p>
        </div>
        <p className="rmr-legend__limits">
          Escala regional:{" "}
          {min === null
            ? "sem valores comparáveis"
            : `${min.toLocaleString("pt-BR")} a ${max?.toLocaleString("pt-BR")}`}
        </p>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-muted">
        <span className="flex items-center gap-2">
          {classes.map((color, index) => (
            <span key={color}>{swatch(color, `Faixa ${index + 1}`)}</span>
          ))}
          {diverging ? "queda · zero · alta" : "menor · maior"}
        </span>
        <span className="flex items-center gap-2">
          {swatch("--map-zero", "Zero observado")}Zero observado
        </span>
        <span className="flex items-center gap-2">
          {swatch("--map-missing", "Sem observação")}Sem observação
        </span>
        <span>Valores parciais mantêm o valor e recebem marcação textual.</span>
      </div>
    </section>
  );
}
