import { SlidersHorizontal } from "lucide-react";
import { filterLabels } from "./queue-query";
import {
  inspectionAction,
  inspectionControl,
  inspectionPrimary,
} from "./inspection-ui";
import type { Metadata } from "./contract";

export default function InspectionFilters({
  params,
  request,
  options,
  metadata,
  onChange,
}: {
  params: URLSearchParams;
  request: string;
  options: Record<string, string[]>;
  metadata?: Metadata;
  onChange: (next: URLSearchParams) => void;
}) {
  const selected = Object.keys(filterLabels).filter((key) => params.has(key));
  return (
    <section
      className="rounded-xl border border-border bg-surface"
      aria-label="Recorte e filtros"
    >
      <details>
        <summary className="flex min-h-20 cursor-pointer list-none flex-wrap items-center justify-between gap-4 p-5 [&::-webkit-details-marker]:hidden focus-visible:outline-2 focus-visible:outline-brand">
          <span className="grid flex-1 grid-cols-2 gap-x-6 gap-y-3 text-sm sm:grid-cols-3">
            <span>
              <span className="block text-xs text-muted">
                Janela da evidência
              </span>
              <span className="mt-1 block font-medium">
                {metadata
                  ? `${metadata.period.start} a ${metadata.period.end}`
                  : "Consultando…"}
              </span>
            </span>
            <span>
              <span className="block text-xs text-muted">Território</span>
              <span className="mt-1 block font-medium">
                {params.get("municipio") ?? "Todos os municípios"}
              </span>
            </span>
            <span>
              <span className="block text-xs text-muted">Classe</span>
              <span className="mt-1 block font-medium">
                {params.get("classe") ?? "Todas as classes"}
              </span>
            </span>
          </span>
          <span className={inspectionAction}>
            <SlidersHorizontal size={16} aria-hidden="true" />
            Ajustar filtros{selected.length > 0 ? ` (${selected.length})` : ""}
          </span>
        </summary>
        <form
          key={request}
          aria-label="Filtros da fila"
          className="grid gap-4 border-t border-border p-5 sm:grid-cols-2 lg:grid-cols-4"
          onSubmit={(event) => {
            event.preventDefault();
            const fields = new FormData(event.currentTarget),
              next = new URLSearchParams();
            for (const [key, value] of fields.entries())
              if (typeof value === "string" && value) next.set(key, value);
            next.set("page", "1");
            onChange(next);
          }}
        >
          {Object.entries(filterLabels).map(([key, label]) => (
            <label key={key} className="space-y-2 text-sm">
              <span>{label}</span>
              <select
                name={key}
                className={inspectionControl}
                defaultValue={params.get(key) ?? ""}
              >
                <option value="">Todos</option>
                {Array.from(
                  new Set([
                    ...(options[key] ?? []),
                    ...(params.get(key) ? [params.get(key)!] : []),
                  ]),
                ).map((value) => (
                  <option key={value}>{value}</option>
                ))}
              </select>
            </label>
          ))}
          <label className="space-y-2 text-sm">
            <span>Ordenar por</span>
            <select
              name="order_by"
              className={inspectionControl}
              defaultValue={params.get("order_by") ?? "priority"}
            >
              <option value="priority">Prioridade</option>
              <option value="potential_recoverable_energy_kwh">
                Energia estimada
              </option>
              <option value="uc_id">Número da UC</option>
            </select>
          </label>
          <label className="space-y-2 text-sm">
            <span>Direção</span>
            <select
              name="direction"
              className={inspectionControl}
              defaultValue={params.get("direction") ?? "desc"}
            >
              <option value="desc">Decrescente</option>
              <option value="asc">Crescente</option>
            </select>
          </label>
          <label className="space-y-2 text-sm">
            <span>UCs por página</span>
            <select
              name="page_size"
              className={inspectionControl}
              defaultValue={params.get("page_size") ?? "10"}
            >
              {Array.from(
                new Set([1, 10, 20, 50, Number(params.get("page_size") ?? 10)]),
              )
                .sort((a, b) => a - b)
                .map((size) => (
                  <option key={size}>{size}</option>
                ))}
            </select>
          </label>
          <div className="flex items-end gap-2">
            <button type="submit" className={inspectionPrimary}>
              Aplicar
            </button>
            <button
              type="button"
              className={inspectionAction}
              onClick={() => onChange(new URLSearchParams())}
            >
              Limpar
            </button>
          </div>
        </form>
      </details>
      {selected.length > 0 && (
        <p className="border-t border-border px-5 py-3 text-xs text-muted">
          Recorte aplicado:{" "}
          {selected
            .map((key) => `${filterLabels[key]}: ${params.get(key)}`)
            .join(" · ")}
        </p>
      )}
    </section>
  );
}
