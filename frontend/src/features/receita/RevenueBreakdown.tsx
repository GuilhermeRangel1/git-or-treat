import { useState } from "react";
import type { RevenueEnvelope } from "./contract";
import type { RevenueGroupBy } from "./revenue-filters";
import { signedValueTone } from "@/shared/ui/signedValue";

const money = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
});

const dimensionLabels: Record<RevenueGroupBy, string> = {
  municipio: "Município",
  bairro: "Bairro",
  classe: "Classe",
};

function displayValue(value: string | null, fallback: string) {
  if (value === null) return fallback;
  return value === "__grid360_missing__" ? "Não informado" : value;
}

function signedMoney(value: number | null) {
  if (value === null) return "Indisponível";
  return (
    (value < 0 ? "−" : value > 0 ? "+" : "") + money.format(Math.abs(value))
  );
}

function knownMoney(value: number | null) {
  return value === null ? "Indisponível" : money.format(value);
}

export default function RevenueBreakdown({
  envelope,
  groupBy,
  onGroupByChange,
  onExplore,
}: {
  envelope: RevenueEnvelope;
  groupBy: RevenueGroupBy;
  onGroupByChange: (value: RevenueGroupBy) => void;
  onExplore: (
    item: RevenueEnvelope["data"]["breakdown"]["items"][number],
  ) => void;
}) {
  const breakdown = envelope.data.breakdown;
  const [page, setPage] = useState(1);
  const pageSize = 20;
  const totalPages = Math.max(1, Math.ceil(breakdown.items.length / pageSize));
  const currentPage = Math.min(page, totalPages);
  const visibleItems = breakdown.items.slice(
    (currentPage - 1) * pageSize,
    currentPage * pageSize,
  );
  const reconciliation = breakdown.reconciliation;
  const sharedLimitations =
    breakdown.items.length > 1
      ? [...new Set(breakdown.items[0].quality.limitations)].filter((note) =>
          breakdown.items.every((item) =>
            item.quality.limitations.includes(note),
          ),
        )
      : [];
  const closesWithTotal =
    reconciliation.status === "available" &&
    reconciliation.non_comparable_group_count === 0 &&
    reconciliation.residual_brl === 0;
  const canExplore = (item: (typeof breakdown.items)[number]) =>
    (breakdown.dimension === "municipio" && item.filters.municipio) ||
    (breakdown.dimension === "bairro" &&
      item.filters.municipio &&
      item.filters.bairro) ||
    (breakdown.dimension === "classe" && item.filters.classe);

  return (
    <section
      aria-label="Decomposição por recorte"
      className="min-w-0 rounded-xl bg-surface p-4"
    >
      {breakdown.items.length === 0 ? (
        <p className="py-4 text-sm text-muted">
          A consulta não retornou grupos para este recorte.
        </p>
      ) : (
        <>
          {sharedLimitations.length > 0 && (
            <p className="mb-3 text-sm text-muted">
              {sharedLimitations.join(" ")}
            </p>
          )}
          <div className="min-w-0 max-w-full overflow-x-auto">
            <table className="w-full min-w-[880px] border-collapse text-left font-sans text-sm">
              <caption className="sr-only">
                Comparação de receita por{" "}
                {dimensionLabels[breakdown.dimension].toLocaleLowerCase(
                  "pt-BR",
                )}
              </caption>
              <thead className="h-11 border-b border-border font-mono text-xs leading-[18px] text-muted [&_th]:font-normal">
                <tr>
                  <th scope="col" className="px-3 py-2 font-medium">
                    <label className="flex items-center gap-2">
                      <span className="sr-only">Agrupar recortes</span>
                      <select
                        aria-label="Agrupar recortes"
                        className="min-h-9 rounded-md border border-control bg-canvas px-2 font-sans text-sm font-medium text-content focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
                        value={groupBy}
                        onChange={(event) =>
                          onGroupByChange(event.target.value as RevenueGroupBy)
                        }
                      >
                        {Object.entries(dimensionLabels).map(
                          ([value, label]) => (
                            <option key={value} value={value}>
                              {label}
                            </option>
                          ),
                        )}
                      </select>
                    </label>
                  </th>
                  <th scope="col" className="px-3 py-2 font-medium">
                    Faturado inicial
                  </th>
                  <th scope="col" className="px-3 py-2 font-medium">
                    Faturado final
                  </th>
                  <th scope="col" className="px-3 py-2 font-medium">
                    Variação absoluta
                  </th>
                  <th scope="col" className="px-3 py-2 text-right font-medium">
                    Ação
                  </th>
                </tr>
              </thead>
              <tbody>
                {visibleItems.map((item) => {
                  const neighborhood = displayValue(
                    item.label,
                    "Não informado",
                  );
                  const municipality = displayValue(
                    item.filters.municipio,
                    "Não informado",
                  );
                  const rowLabel =
                    breakdown.dimension === "bairro" && item.filters.municipio
                      ? `${neighborhood} · ${municipality}`
                      : neighborhood;
                  const baseDescription = item.quality.small_base
                    ? "Base pequena"
                    : item.comparison.initial.billed_uc_count === null ||
                        item.comparison.final.billed_uc_count === null
                      ? "Base desconhecida"
                      : "Base adequada";
                  const rowLimitations = item.quality.limitations.filter(
                    (note) => !sharedLimitations.includes(note),
                  );

                  return (
                    <tr
                      key={item.key}
                      className="h-14 border-b border-border last:border-0"
                    >
                      <th
                        scope="row"
                        className="max-w-80 px-3 py-2 font-semibold [overflow-wrap:anywhere] text-content"
                      >
                        <span>{rowLabel}</span>
                        <span className="ml-2 inline-flex flex-wrap items-center gap-x-1 text-xs font-normal text-muted">
                          <span
                            className={
                              item.quality.small_base
                                ? "font-medium text-danger"
                                : "font-medium text-muted"
                            }
                          >
                            {baseDescription}
                          </span>
                          <span aria-hidden="true">·</span>
                          <span>
                            Antes:{" "}
                            {item.comparison.initial.billed_uc_count ?? "—"}
                            {" → "}
                            Final:{" "}
                            {item.comparison.final.billed_uc_count ?? "—"} UCs
                          </span>
                        </span>
                        {rowLimitations.length ? (
                          <span className="block text-xs font-normal text-muted">
                            {rowLimitations.join(" ")}
                          </span>
                        ) : !item.quality.percent_change_eligible &&
                          item.quality.limitations.length === 0 ? (
                          <span className="block text-xs font-normal text-muted">
                            Percentual indisponível
                          </span>
                        ) : null}
                      </th>
                      <td
                        className={`px-3 py-2 ${signedValueTone(item.comparison.initial.billed_amount, false)}`}
                      >
                        {knownMoney(item.comparison.initial.billed_amount)}
                      </td>
                      <td
                        className={`px-3 py-2 ${signedValueTone(item.comparison.final.billed_amount, false)}`}
                      >
                        {knownMoney(item.comparison.final.billed_amount)}
                      </td>
                      <td
                        className={`px-3 py-2 ${signedValueTone(item.comparison.billed_amount_change_brl)}`}
                      >
                        {signedMoney(item.comparison.billed_amount_change_brl)}
                      </td>
                      <td className="px-3 py-2 text-right">
                        {canExplore(item) ? (
                          <button
                            type="button"
                            className="min-h-9 rounded-lg border border-control px-3 font-medium text-content hover:bg-surface-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
                            onClick={() => onExplore(item)}
                            aria-label={`Explorar ${rowLabel}`}
                          >
                            Explorar
                          </button>
                        ) : (
                          <span className="text-muted">
                            Sem recorte disponível
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
              <tfoot className="border-t border-border bg-canvas/60 font-semibold text-content">
                <tr>
                  <th scope="row" className="px-3 py-3 text-left">
                    Soma conhecida dos recortes
                    <span className="block text-xs font-normal text-muted">
                      Variação apenas dos grupos comparáveis
                    </span>
                  </th>
                  <td
                    className={`px-3 py-3 ${signedValueTone(reconciliation.initial_known_sum_brl, false)}`}
                  >
                    {knownMoney(reconciliation.initial_known_sum_brl)}
                  </td>
                  <td
                    className={`px-3 py-3 ${signedValueTone(reconciliation.final_known_sum_brl, false)}`}
                  >
                    {knownMoney(reconciliation.final_known_sum_brl)}
                  </td>
                  <td
                    className={`px-3 py-3 ${signedValueTone(reconciliation.comparable_change_sum_brl)}`}
                  >
                    {signedMoney(reconciliation.comparable_change_sum_brl)}
                  </td>
                  <td aria-hidden="true" />
                </tr>
              </tfoot>
            </table>
          </div>
          {totalPages > 1 ? (
            <nav
              aria-label="Paginação dos recortes"
              className="mt-3 flex flex-wrap items-center justify-between gap-3 text-sm"
            >
              <span>
                Página {currentPage} de {totalPages} · {breakdown.items.length}{" "}
                recortes
              </span>
              <div className="flex gap-2">
                <button
                  type="button"
                  className="rounded-lg border border-control px-3 py-2 disabled:opacity-50"
                  disabled={currentPage === 1}
                  onClick={() => setPage(currentPage - 1)}
                >
                  Anterior
                </button>
                <button
                  type="button"
                  className="rounded-lg border border-control px-3 py-2 disabled:opacity-50"
                  disabled={currentPage === totalPages}
                  onClick={() => setPage(currentPage + 1)}
                >
                  Próxima
                </button>
              </div>
            </nav>
          ) : null}
          {closesWithTotal ? (
            <p className="mt-3 text-sm text-muted">
              Os recortes fecham com o total.
            </p>
          ) : (
            <div role="status" className="mt-3 space-y-1 text-sm text-muted">
              <p>
                {reconciliation.status === "partial"
                  ? "Fechamento parcial dos recortes."
                  : "Fechamento dos recortes indisponível."}
              </p>
              {reconciliation.non_comparable_group_count > 0 ? (
                <>
                  <p>
                    {reconciliation.non_comparable_group_count}{" "}
                    {reconciliation.non_comparable_group_count === 1
                      ? "grupo sem comparação."
                      : "grupos sem comparação."}
                  </p>
                  <p>
                    Diferença não atribuída:{" "}
                    <span
                      className={signedValueTone(
                        reconciliation.unattributed_change_brl,
                      )}
                    >
                      {signedMoney(reconciliation.unattributed_change_brl)}
                    </span>
                    .
                  </p>
                </>
              ) : null}
              {reconciliation.residual_brl !== null &&
              reconciliation.residual_brl !== 0 ? (
                <p>
                  Diferença para o total:{" "}
                  <span
                    className={signedValueTone(reconciliation.residual_brl)}
                  >
                    {signedMoney(reconciliation.residual_brl)}
                  </span>
                  .
                </p>
              ) : null}
              {reconciliation.limitations.length > 0 ? (
                <p>{reconciliation.limitations.join(" ")}</p>
              ) : null}
            </div>
          )}
        </>
      )}
    </section>
  );
}
