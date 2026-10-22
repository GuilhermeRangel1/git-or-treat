import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { ApiError } from "@/shared/api/client";
import RevenueFiltersForm from "./RevenueFiltersForm";
import RevenueBreakdown from "./RevenueBreakdown";
import RevenueDecomposition from "./RevenueDecomposition";
import RevenueSeries from "./RevenueSeries";
import RevenueSummary from "./RevenueSummary";
import {
  parseRevenueSearchParams,
  revenueRefinementDestination,
  refineRevenueParams,
  updateRevenueBaseParams,
  updateRevenueGroupBy,
} from "./revenue-filters";
import { useRevenue } from "./useRevenue";

function competenceLabel(value: string) {
  const month = Number(value.slice(5, 7));
  const names = [
    "Jan",
    "Fev",
    "Mar",
    "Abr",
    "Mai",
    "Jun",
    "Jul",
    "Ago",
    "Set",
    "Out",
    "Nov",
    "Dez",
  ];
  return names[month - 1] + "/" + value.slice(0, 4);
}

function filterLabel(value: string | null, fallback: string) {
  if (value === null) return fallback;
  return value === "__grid360_missing__" ? "Não informado" : value;
}

export default function ReceitaPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [filtersOpen, setFiltersOpen] = useState(false);
  const filtersDialogRef = useRef<HTMLDialogElement>(null);
  const filtersTriggerRef = useRef<HTMLButtonElement>(null);
  const restoreFiltersFocusRef = useRef(false);
  const searchKey = searchParams.toString();
  const parsed = useMemo(
    () => parseRevenueSearchParams(new URLSearchParams(searchKey)),
    [searchKey],
  );
  const revenue = useRevenue(parsed.query);

  useEffect(() => {
    const dialog = filtersDialogRef.current;
    if (!dialog) return;
    if (filtersOpen && !dialog.open) {
      if (typeof dialog.showModal === "function") dialog.showModal();
      else dialog.setAttribute("open", "");
    }
    if (!filtersOpen && dialog.open) {
      if (typeof dialog.close === "function") dialog.close();
      else dialog.removeAttribute("open");
    }
  }, [filtersOpen]);

  useEffect(() => {
    if (!filtersOpen && restoreFiltersFocusRef.current) {
      filtersTriggerRef.current?.focus();
      restoreFiltersFocusRef.current = false;
    }
  }, [filtersOpen]);

  function closeFilters() {
    restoreFiltersFocusRef.current = true;
    setFiltersOpen(false);
  }

  function applyFilters(
    filters: Parameters<typeof updateRevenueBaseParams>[1],
  ) {
    const next = updateRevenueBaseParams(searchParams, filters);
    setSearchParams(next, { preventScrollReset: true });
    closeFilters();
  }

  function applyGroupBy(groupBy: typeof parsed.groupBy) {
    setSearchParams(updateRevenueGroupBy(searchParams, groupBy), {
      preventScrollReset: true,
    });
  }

  function exploreBreakdownItem(
    item: NonNullable<
      typeof revenue.data
    >["data"]["breakdown"]["items"][number],
  ) {
    const next = refineRevenueParams(
      searchParams,
      envelope?.data.breakdown.dimension ?? parsed.groupBy,
      item.filters,
    );
    setSearchParams(next, { preventScrollReset: true });
  }

  const envelope = revenue.data;
  const appliedFilters = envelope?.metadata.filters ?? {
    municipio: parsed.query?.municipio || null,
    bairro: parsed.query?.bairro || null,
    classe: parsed.query?.classe || null,
    alimentador: parsed.query?.alimentador || null,
  };
  const totalRefinementParams = revenueRefinementDestination(
    searchParams,
    "total",
  );
  const municipalityRefinementParams = revenueRefinementDestination(
    searchParams,
    "municipio",
  );
  const neighborhoodRefinementParams = revenueRefinementDestination(
    searchParams,
    "bairro",
  );
  const unavailableMessage = (() => {
    if (!(revenue.error instanceof ApiError)) {
      return "Não foi possível consultar a receita. Tente novamente.";
    }
    if (revenue.error.kind === "configuration") {
      return "A API de analytics não está configurada para este ambiente.";
    }
    if (revenue.error.kind === "network") {
      return "Não foi possível conectar à API de receita.";
    }
    if (revenue.error.kind === "invalid-response") {
      return "A API de receita retornou uma resposta inválida.";
    }
    if (revenue.error.status === 422) {
      return "A API recusou esta consulta (HTTP 422). Revise os filtros.";
    }
    return (
      "A API de receita respondeu com erro HTTP " + revenue.error.status + "."
    );
  })();

  return (
    <div className="mt-6 grid min-w-0 w-full max-w-[1088px] gap-4">
      <div className="flex min-h-[18px] min-w-0 flex-wrap items-center justify-between gap-2 text-xs">
        <div className="flex flex-wrap items-center gap-2">
          {envelope?.metadata.source.is_demo ? (
            <span className="text-muted">
              Demonstração · dados sintéticos · atualização:{" "}
              {new Intl.DateTimeFormat("pt-BR", {
                day: "2-digit",
                month: "2-digit",
                year: "numeric",
                timeZone: "UTC",
              }).format(new Date(envelope.metadata.source.updated_at))}
            </span>
          ) : null}
          {envelope?.metadata.status === "partial" ? (
            <span role="status" className="text-muted">
              Cobertura parcial
            </span>
          ) : null}
          {envelope?.metadata.status === "unavailable" ? (
            <span role="status" className="text-muted">
              Valores indisponíveis
            </span>
          ) : null}
          {envelope?.metadata.status === "empty" ? (
            <span role="status" className="text-muted">
              Sem registros para este recorte; ausência não equivale a zero.
            </span>
          ) : null}
        </div>
        {revenue.isFetching && envelope ? (
          <span role="status" className="text-muted">
            Atualizando consulta…
          </span>
        ) : null}
      </div>

      <section
        aria-label="Filtros aplicados"
        className="mt-2 flex min-h-[92px] min-w-0 flex-wrap items-center justify-between gap-4 rounded-xl bg-surface px-4 py-4"
      >
        <div
          className={`grid min-w-0 flex-1 grid-cols-2 gap-x-5 gap-y-2 text-sm ${appliedFilters.alimentador ? "md:grid-cols-5" : "md:grid-cols-4"}`}
        >
          {(() => {
            const territory = appliedFilters.bairro
              ? filterLabel(appliedFilters.bairro, "Todos os bairros") +
                (appliedFilters.municipio
                  ? " · " +
                    filterLabel(appliedFilters.municipio, "Não informado")
                  : "")
              : filterLabel(appliedFilters.municipio, "Todos os municípios");
            return (
              <>
                <div>
                  <p className="text-xs text-muted">Competência</p>
                  <p className="mt-1 text-sm font-medium text-content">
                    {competenceLabel(
                      envelope?.metadata.period.end ??
                        parsed.base.competencia_fim,
                    )}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-muted">Comparar com</p>
                  <p className="mt-1 text-sm font-medium text-content">
                    {competenceLabel(
                      envelope?.metadata.period.start ??
                        parsed.base.competencia_inicio,
                    )}
                  </p>
                </div>
                <div className="min-w-0">
                  <p className="text-xs text-muted">Território</p>
                  <p className="mt-1 truncate text-sm font-medium text-content">
                    {territory}
                  </p>
                </div>
                <div className="min-w-0">
                  <p className="text-xs text-muted">Classe</p>
                  <p className="mt-1 truncate text-sm font-medium text-content">
                    {filterLabel(appliedFilters.classe, "Todas as classes")}
                  </p>
                </div>
                {appliedFilters.alimentador ? (
                  <div className="min-w-0">
                    <p className="text-xs text-muted">Alimentador</p>
                    <p className="mt-1 truncate text-sm font-medium text-content">
                      {filterLabel(appliedFilters.alimentador, "Não informado")}
                    </p>
                  </div>
                ) : null}
              </>
            );
          })()}
          {(parsed.refinements.municipio ||
            parsed.refinements.bairro ||
            parsed.refinements.classe) && (
            <nav
              aria-label="Caminho do recorte"
              className={`col-span-2 mt-1 flex flex-wrap items-center gap-1 text-xs ${appliedFilters.alimentador ? "md:col-span-5" : "md:col-span-4"}`}
            >
              <a
                href={`?${totalRefinementParams.toString()}`}
                onClick={(event) => {
                  event.preventDefault();
                  setSearchParams(totalRefinementParams, {
                    preventScrollReset: true,
                  });
                }}
                className="font-medium text-brand underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
              >
                Total
              </a>
              {parsed.refinements.municipio ? (
                <>
                  <span aria-hidden="true" className="text-muted">
                    ›
                  </span>
                  <a
                    href={`?${municipalityRefinementParams.toString()}`}
                    onClick={(event) => {
                      event.preventDefault();
                      setSearchParams(municipalityRefinementParams, {
                        preventScrollReset: true,
                      });
                    }}
                    className="font-medium text-brand underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
                  >
                    Município:{" "}
                    {filterLabel(parsed.refinements.municipio, "Não informado")}
                  </a>
                </>
              ) : null}
              {parsed.refinements.bairro ? (
                <>
                  <span aria-hidden="true" className="text-muted">
                    ›
                  </span>
                  {parsed.refinements.classe ? (
                    <a
                      href={`?${neighborhoodRefinementParams.toString()}`}
                      onClick={(event) => {
                        event.preventDefault();
                        setSearchParams(neighborhoodRefinementParams, {
                          preventScrollReset: true,
                        });
                      }}
                      className="font-medium text-brand underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
                    >
                      Bairro:{" "}
                      {filterLabel(parsed.refinements.bairro, "Não informado")}
                    </a>
                  ) : (
                    <span aria-current="page">
                      Bairro:{" "}
                      {filterLabel(parsed.refinements.bairro, "Não informado")}
                    </span>
                  )}
                </>
              ) : null}
              {parsed.refinements.classe ? (
                <>
                  <span aria-hidden="true" className="text-muted">
                    ›
                  </span>
                  <span aria-current="page">
                    Classe:{" "}
                    {filterLabel(parsed.refinements.classe, "Não informado")}
                  </span>
                </>
              ) : null}
            </nav>
          )}
        </div>
        <button
          ref={filtersTriggerRef}
          type="button"
          className="min-h-11 shrink-0 rounded-lg border border-control bg-canvas px-4 text-sm font-semibold text-content hover:bg-surface-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
          onClick={() => setFiltersOpen(true)}
        >
          <svg
            aria-hidden="true"
            viewBox="0 0 24 24"
            className="mr-2 inline size-4"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.8"
          >
            <path strokeLinecap="round" d="M4 7h9m4 0h3M4 17h3m4 0h9" />
            <circle cx="15" cy="7" r="2" />
            <circle cx="9" cy="17" r="2" />
          </svg>
          Ajustar filtros
        </button>
      </section>

      {filtersOpen ? (
        <dialog
          ref={filtersDialogRef}
          aria-labelledby="revenue-filter-title"
          className="fixed inset-0 m-auto max-h-[90vh] w-[min(720px,calc(100vw-2rem))] min-w-0 overflow-y-auto rounded-2xl border border-border bg-surface p-0 text-content shadow-2xl backdrop:bg-black/50"
          onCancel={(event) => {
            event.preventDefault();
            closeFilters();
          }}
          onClose={closeFilters}
        >
          <section className="grid gap-4 p-5 sm:p-6">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2
                  id="revenue-filter-title"
                  className="font-heading text-xl font-semibold"
                >
                  Ajustar filtros
                </h2>
                <p className="mt-1 text-sm text-muted">
                  Escolha o período e os filtros para consultar a receita.
                </p>
              </div>
              <button
                type="button"
                aria-label="Fechar filtros"
                className="grid size-10 shrink-0 place-items-center rounded-lg border border-control hover:bg-surface-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
                onClick={closeFilters}
              >
                ×
              </button>
            </div>
            <RevenueFiltersForm
              initialFilters={parsed.base}
              searchKey={searchKey}
              envelope={envelope}
              onApply={applyFilters}
            />
          </section>
        </dialog>
      ) : null}

      {parsed.errors.length > 0 ? (
        <div
          role="alert"
          className="rounded-xl border border-danger bg-surface p-4 text-sm text-danger"
        >
          <h2 className="font-semibold">O link contém filtros inválidos.</h2>
          <ul className="mt-2 list-inside list-disc">
            {parsed.errors.map((error) => (
              <li key={error}>{error}</li>
            ))}
          </ul>
          <p className="mt-2 text-content">
            Corrija os campos e aplique os filtros para consultar.
          </p>
        </div>
      ) : null}

      {revenue.isPending && parsed.query ? (
        <p
          role="status"
          className="rounded-xl border border-border bg-surface p-4 text-sm text-muted"
        >
          Carregando a receita para {parsed.base.competencia_inicio} —{" "}
          {parsed.base.competencia_fim}…
        </p>
      ) : null}

      {revenue.isError ? (
        <div
          role="alert"
          className="rounded-xl border border-danger bg-surface p-4 text-sm text-content"
        >
          <p>{unavailableMessage}</p>
          <button
            type="button"
            className="mt-3 min-h-10 rounded-lg border border-control px-4 font-medium text-content hover:bg-surface-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
            onClick={() => void revenue.refetch()}
          >
            Tentar novamente
          </button>
        </div>
      ) : null}

      {envelope ? (
        <>
          <RevenueSummary envelope={envelope} />
          <RevenueDecomposition envelope={envelope} />
          <RevenueBreakdown
            envelope={envelope}
            groupBy={parsed.groupBy}
            onGroupByChange={applyGroupBy}
            onExplore={exploreBreakdownItem}
          />
          <RevenueSeries envelope={envelope} />
        </>
      ) : null}
    </div>
  );
}
