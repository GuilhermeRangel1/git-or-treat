import type { MunicipalityMetric } from "./contract";
import type { MapLayer } from "./map-state";
import { valueForLayer } from "./map-values";

function formattedValue(value: number | null, layer: MapLayer) {
  if (value === null) return "Sem observação";
  if (layer === "revenue" || layer === "revenue_change") {
    return new Intl.NumberFormat("pt-BR", {
      style: "currency",
      currency: "BRL",
      maximumFractionDigits: 2,
    }).format(value);
  }
  return `${value.toLocaleString("pt-BR", { maximumFractionDigits: 2 })} kWh`;
}

export default function MunicipalityTable({
  items,
  selectedCode,
  layer,
  partialCodes,
  dataAvailable,
  onSelect,
}: {
  items: MunicipalityMetric[];
  selectedCode: string;
  layer: MapLayer;
  partialCodes: ReadonlySet<string>;
  dataAvailable: boolean;
  onSelect: (code: string) => void;
}) {
  return (
    <section
      className="min-w-0 rounded-xl border border-border bg-surface p-4"
      aria-label="Dados por município"
    >
      <h2 className="font-heading text-base font-semibold text-content">
        Municípios da RMR
      </h2>
      <p className="mt-1 text-sm text-muted">
        Selecione uma linha para abrir a série e os bairros. A lista oferece a
        mesma seleção do mapa.
      </p>
      <div className="mt-3 max-h-[420px] overflow-auto rounded-lg border border-border">
        <table className="w-full min-w-[360px] border-collapse text-left text-sm">
          <caption className="sr-only">
            Valores da camada selecionada por município
          </caption>
          <thead className="sticky top-0 bg-surface text-xs text-muted">
            <tr>
              <th className="px-3 py-2 font-medium">Município</th>
              <th className="px-3 py-2 text-right font-medium">Valor</th>
              <th className="px-3 py-2 text-right font-medium">Cobertura</th>
            </tr>
          </thead>
          <tbody>
            {items.map(({ municipality, item }) => {
              const value = valueForLayer(item, layer);
              const partial = partialCodes.has(municipality.code);
              const selected = selectedCode === municipality.code;
              return (
                <tr
                  key={municipality.code}
                  className={`border-t border-border ${selected ? "bg-selected" : ""}`}
                  aria-selected={selected}
                >
                  <th
                    scope="row"
                    className="px-3 py-1.5 font-normal text-content"
                  >
                    <button
                      type="button"
                      aria-pressed={selected}
                      aria-label={`Selecionar ${municipality.name}${selected ? ", selecionado" : ""}`}
                      onClick={() => onSelect(municipality.code)}
                      className="min-h-10 rounded px-1 text-left font-medium underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
                    >
                      {municipality.name}
                      {selected ? (
                        <span className="ml-2 text-xs text-brand">
                          Selecionado
                        </span>
                      ) : null}
                    </button>
                  </th>
                  <td className="px-3 py-1.5 text-right tabular-nums text-content">
                    {dataAvailable
                      ? formattedValue(value, layer)
                      : "Dados indisponíveis"}
                  </td>
                  <td className="px-3 py-1.5 text-right text-xs text-muted">
                    {!dataAvailable
                      ? "Aguardando dados"
                      : value === null
                        ? "Sem observação"
                        : partial
                          ? "Parcial"
                          : "Observado"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
