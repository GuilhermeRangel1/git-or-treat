import { useMemo } from "react";
import { signedValueTone } from "@/shared/ui/signedValue";
import type { MunicipalityMetric } from "./contract";
import { layerValue } from "./map-format";
import type { MapLayer } from "./map-state";
import { valueForLayer } from "./map-values";

type Row = {
  code: string;
  name: string;
  value: number | null;
  partial: boolean;
};

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
  const diverging = layer.endsWith("change");
  const rows = useMemo(() => {
    const list: Row[] = items.map(({ municipality, item }) => ({
      code: municipality.code,
      name: municipality.name,
      value: valueForLayer(item, layer),
      partial: partialCodes.has(municipality.code),
    }));
    // Maior valor primeiro; nas variações, a maior queda primeiro (é onde a
    // pergunta comercial começa). Sem observação vai para o fim.
    return list.sort((a, b) => {
      if (a.value === null && b.value === null)
        return a.name.localeCompare(b.name, "pt-BR");
      if (a.value === null) return 1;
      if (b.value === null) return -1;
      return diverging ? a.value - b.value : b.value - a.value;
    });
  }, [items, layer, partialCodes, diverging]);

  const observed = rows.filter((row) => row.value !== null);
  // Quando todos os municípios têm o mesmo estado, repeti-lo em cada linha só
  // faz ruído: um aviso único dá a mesma informação.
  const allPartial =
    dataAvailable && observed.length > 0 && observed.every((r) => r.partial);
  const someMissing = rows.some((row) => row.value === null);
  const showCoverageColumn =
    dataAvailable && !allPartial && observed.some((row) => row.partial);
  const maxAbs = observed.reduce(
    (bound, row) => Math.max(bound, Math.abs(row.value ?? 0)),
    0,
  );

  return (
    <section
      className="min-w-0 rounded-xl border border-border bg-surface p-4"
      aria-label="Dados por município"
    >
      <h2 className="font-heading text-base font-semibold text-content">
        Municípios da RMR
      </h2>
      <p className="mt-1 text-sm text-muted">
        Clique em um município para ver bairros e série mensal.
      </p>
      <p className="mt-0.5 text-xs text-muted">
        {diverging
          ? "Ordenado da maior queda para a maior alta."
          : "Ordenado do maior para o menor valor."}
      </p>
      {allPartial ? (
        <p
          role="status"
          className="mt-3 flex items-start gap-2 rounded-lg bg-[var(--status-warning-bg)] px-3 py-2 text-xs text-content"
        >
          <span aria-hidden="true">●</span>
          <span>
            Cobertura parcial em todos os municípios neste período. Os valores
            observados permanecem visíveis.
          </span>
        </p>
      ) : null}
      <div className="mt-3 max-h-[420px] overflow-auto rounded-lg border border-border">
        <table className="w-full min-w-[320px] border-collapse text-left text-sm">
          <caption className="sr-only">
            Valores da camada selecionada por município
          </caption>
          <thead className="sticky top-0 bg-surface text-xs text-muted">
            <tr>
              <th className="px-3 py-2 font-medium">Município</th>
              <th className="px-3 py-2 text-right font-medium">Valor</th>
              {showCoverageColumn ? (
                <th className="px-3 py-2 text-right font-medium">Cobertura</th>
              ) : null}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const selected = selectedCode === row.code;
              return (
                <tr
                  key={row.code}
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
                      aria-label={`Selecionar ${row.name}${selected ? ", selecionado" : ""}`}
                      onClick={() => onSelect(row.code)}
                      className="min-h-10 rounded px-1 text-left font-medium underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
                    >
                      {row.name}
                      {selected ? (
                        <span className="ml-2 text-xs text-brand">
                          Selecionado
                        </span>
                      ) : null}
                    </button>
                  </th>
                  <td className="px-3 py-1.5 text-right">
                    {!dataAvailable ? (
                      <span className="text-muted">Dados indisponíveis</span>
                    ) : row.value === null ? (
                      <span className="text-muted">Sem observação</span>
                    ) : (
                      <>
                        <span
                          className={`tabular-nums ${diverging ? `font-medium ${signedValueTone(row.value)}` : "text-content"}`}
                        >
                          {diverging && row.value !== 0 ? (
                            <span aria-hidden="true" className="mr-1 text-xs">
                              {row.value > 0 ? "▲" : "▼"}
                            </span>
                          ) : null}
                          {layerValue(row.value, layer)}
                        </span>
                        {row.partial ? (
                          <span className="sr-only"> · cobertura parcial</span>
                        ) : null}
                        {!diverging && maxAbs > 0 ? (
                          <span
                            aria-hidden="true"
                            className="mt-1 block h-1 rounded-full bg-border"
                          >
                            <span
                              className="block h-1 rounded-full bg-brand/60"
                              style={{
                                width: `${Math.max(2, (Math.abs(row.value) / maxAbs) * 100)}%`,
                              }}
                            />
                          </span>
                        ) : null}
                      </>
                    )}
                  </td>
                  {showCoverageColumn ? (
                    <td className="px-3 py-1.5 text-right text-xs text-muted">
                      {row.value !== null && row.partial ? "Parcial" : ""}
                    </td>
                  ) : null}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {someMissing && dataAvailable ? (
        <p className="mt-2 text-xs text-muted">
          Municípios sem observação não são tratados como zero.
        </p>
      ) : null}
    </section>
  );
}
