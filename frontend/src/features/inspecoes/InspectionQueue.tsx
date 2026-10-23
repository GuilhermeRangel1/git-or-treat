import { ArrowUpRight, ChevronLeft, ChevronRight, Search } from "lucide-react";
import { Link } from "react-router-dom";
import type { QueueEnvelope } from "./contract";
import { energy } from "./format";
import { inspectionAction, inspectionPrimary } from "./inspection-ui";
import PriorityScore from "./PriorityScore";

export default function InspectionQueue({
  result,
  params,
  onChange,
}: {
  result: QueueEnvelope;
  params: URLSearchParams;
  onChange: (next: URLSearchParams) => void;
}) {
  const { items } = result.data,
    page = result.pagination;
  function goTo(number: number) {
    const next = new URLSearchParams(params);
    next.set("page", String(number));
    onChange(next);
  }
  const field = params.get("order_by") ?? "priority",
    direction = params.get("direction") ?? "desc";
  const sortDescription = `${field === "priority" ? "Prioridade" : field === "uc_id" ? "Número da UC" : "Energia estimada"} ${direction === "desc" ? "decrescente" : "crescente"}`;
  return (
    <section
      aria-label="Fila de inspeção"
      className="overflow-hidden rounded-xl border border-border bg-surface"
    >
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border p-5">
        <div>
          <h2 className="font-heading text-lg font-semibold">
            Fila priorizada
          </h2>
          <p className="mt-1 text-xs text-muted">
            {sortDescription} · Desempate pela energia disponível e número da UC
          </p>
        </div>
        <span className="rounded-full border border-border px-3 py-1 font-mono text-xs text-muted">
          {page.total} UC(s)
        </span>
      </div>
      {items.length === 0 ? (
        <div className="flex flex-col items-center gap-3 px-5 py-12 text-center">
          <Search size={28} className="text-muted" aria-hidden="true" />
          <h3 className="font-heading text-lg font-semibold">
            {page.total === 0
              ? "Nenhuma UC nesta fila"
              : "Página sem resultados"}
          </h3>
          <p className="max-w-md text-sm text-muted">
            {page.total === 0
              ? "Nenhuma suspeita neste recorte. Isso não comprova ausência de perdas."
              : "Esta página não contém UCs. Volte à primeira página."}
          </p>
          <button
            className={inspectionAction}
            onClick={() =>
              page.total === 0 ? onChange(new URLSearchParams()) : goTo(1)
            }
          >
            {page.total === 0 ? "Limpar filtros" : "Primeira página"}
          </button>
        </div>
      ) : (
        <div
          className="overflow-x-auto"
          role="region"
          aria-label="Tabela de suspeitas; role horizontalmente em telas estreitas"
          tabIndex={0}
        >
          <p className="px-5 py-3 text-xs text-muted sm:hidden">
            Deslize a tabela para ver a energia e abrir as evidências.
          </p>
          <table className="w-full text-left text-sm">
            <caption className="sr-only">
              Suspeitas com prioridade, motivo, indicadores, energia estimada e
              acesso às evidências
            </caption>
            <thead className="bg-canvas font-mono text-[11px] text-muted">
              <tr>
                {[
                  "UC / prioridade",
                  "Motivo e indicadores",
                  "Energia estimada",
                  "Ação",
                ].map((label) => (
                  <th scope="col" className="px-5 py-3 font-normal" key={label}>
                    {label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {items.map((item) => {
                const next = new URLSearchParams(params);
                next.set("uc", item.uc_id);
                return (
                  <tr
                    key={item.uc_id}
                    className="border-t border-border transition-colors hover:bg-surface-hover"
                  >
                    <th
                      scope="row"
                      className="min-w-44 space-y-3 px-5 py-5 font-normal"
                    >
                      <p className="font-mono font-semibold">{item.uc_id}</p>
                      <PriorityScore value={item.priority} />
                    </th>
                    <td className="min-w-64 max-w-sm px-5 py-5">
                      <p className="font-medium leading-6">{item.reason}</p>
                      <p className="mt-1 text-xs text-muted">
                        {item.municipality} · {item.neighborhood} ·{" "}
                        {item.class_name} · {item.feeder_id}
                      </p>
                      <ul
                        className="mt-3 flex flex-wrap gap-1.5"
                        aria-label={`Indicadores de ${item.uc_id}`}
                      >
                        {item.signals.map((signal) => (
                          <li
                            key={signal.id}
                            className="rounded-md border border-border bg-canvas px-2 py-1 text-xs text-muted"
                          >
                            {signal.label}
                          </li>
                        ))}
                      </ul>
                    </td>
                    <td className="min-w-40 px-5 py-5">
                      <p
                        className={`font-heading text-lg font-semibold ${item.potential_recoverable_energy_kwh === null ? "text-muted" : "text-content"}`}
                      >
                        {energy(item.potential_recoverable_energy_kwh)}
                      </p>
                      <p className="mt-1 max-w-40 text-xs leading-5 text-muted">
                        {item.potential_recoverable_energy_kwh === null
                          ? "Faltam insumos comparáveis"
                          : "Projeção mensal hipotética"}
                      </p>
                    </td>
                    <td className="px-5 py-5">
                      <Link
                        className={`${inspectionPrimary} whitespace-nowrap`}
                        to={`?${next}`}
                        aria-label={`Ver evidências de ${item.uc_id}`}
                      >
                        Ver evidências
                        <ArrowUpRight size={15} aria-hidden="true" />
                      </Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      {page.total > 0 && (
        <nav
          aria-label="Paginação da fila"
          className="flex flex-wrap items-center justify-between gap-3 border-t border-border px-5 py-4"
        >
          <p className="text-xs text-muted">
            <span>
              Página {page.page} de {page.total_pages}
            </span>{" "}
            · {page.total} UC(s) no recorte
          </p>
          <div className="flex gap-2">
            <button
              className={inspectionAction}
              disabled={page.page <= 1}
              onClick={() => goTo(page.page - 1)}
            >
              <ChevronLeft size={15} aria-hidden="true" />
              Anterior
            </button>
            <button
              className={inspectionAction}
              disabled={page.page >= page.total_pages}
              onClick={() => goTo(page.page + 1)}
            >
              Próxima
              <ChevronRight size={15} aria-hidden="true" />
            </button>
          </div>
        </nav>
      )}
    </section>
  );
}
