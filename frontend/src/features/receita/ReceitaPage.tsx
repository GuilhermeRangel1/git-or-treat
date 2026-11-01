import { useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { ApiError } from "@/shared/api/client";
import Button from "@/shared/ui/Button";
import Modal from "@/shared/ui/Modal";
import { useSourceOptions } from "@/shared/analytics/sourceOptions";
import RevenueFiltersForm from "./RevenueFiltersForm";
import RevenueBreakdown from "./RevenueBreakdown";
import RevenueDecomposition from "./RevenueDecomposition";
import RevenueSeries from "./RevenueSeries";
import RevenueSummary from "./RevenueSummary";
import {
  parseRevenueSearchParams,
  defaultRevenueFilters,
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
  const filtersTriggerRef = useRef<HTMLButtonElement>(null);
  const searchKey = searchParams.toString();
  const catalog = useSourceOptions();
  const defaults = useMemo(() => {
    const months = catalog.data?.data.competencias;
    if (catalog.data?.source.kind !== "gold_csv" || !months?.length)
      return defaultRevenueFilters;
    return {
      ...defaultRevenueFilters,
      competencia_inicio: months[Math.max(0, months.length - 12)],
      competencia_fim: months[months.length - 1],
    };
  }, [catalog.data]);
  const parsed = useMemo(
    () => parseRevenueSearchParams(new URLSearchParams(searchKey), defaults),
    [searchKey, defaults],
  );
  const revenue = useRevenue(parsed.query);

  function applyFilters(
    filters: Parameters<typeof updateRevenueBaseParams>[1],
  ) {
    const next = updateRevenueBaseParams(searchParams, filters);
    setSearchParams(next, { preventScrollReset: true });
    setFiltersOpen(false);
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
  const refinementLabels = [
    parsed.refinements.municipio
      ? `Município: ${filterLabel(parsed.refinements.municipio, "Não informado")}`
      : null,
    parsed.refinements.bairro
      ? `Bairro: ${filterLabel(parsed.refinements.bairro, "Não informado")}`
      : null,
    parsed.refinements.classe
      ? `Classe: ${filterLabel(parsed.refinements.classe, "Não informado")}`
      : null,
  ].filter((label): label is string => label !== null);
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
    <div className="mt-6 grid min-w-0 w-full gap-4">
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

      {refinementLabels.length > 0 ? (
        <section
          aria-label="Recorte explorado"
          className="flex min-w-0 flex-wrap items-center justify-between gap-3 rounded-xl border border-brand/40 bg-brand/5 px-4 py-3"
        >
          <p className="min-w-0 text-sm text-content">
            <span className="font-semibold">Explorando:</span>{" "}
            {refinementLabels.join(" · ")}
          </p>
          <Button
            type="button"
            variant="accent"
            size="sm"
            onClick={() =>
              setSearchParams(totalRefinementParams, {
                preventScrollReset: true,
              })
            }
          >
            Voltar ao total
          </Button>
        </section>
      ) : null}

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
                  <p className="text-xs text-muted">Período</p>
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
        <Button
          ref={filtersTriggerRef}
          type="button"
          variant="control"
          className="shrink-0"
          onClick={() => setFiltersOpen(true)}
          leftIcon={
            <svg
              aria-hidden="true"
              viewBox="0 0 24 24"
              className="size-4"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
            >
              <path strokeLinecap="round" d="M4 7h9m4 0h3M4 17h3m4 0h9" />
              <circle cx="15" cy="7" r="2" />
              <circle cx="9" cy="17" r="2" />
            </svg>
          }
        >
          Ajustar filtros
        </Button>
      </section>

      <Modal
        open={filtersOpen}
        onClose={() => setFiltersOpen(false)}
        triggerRef={filtersTriggerRef}
        title="Ajustar filtros"
        description="Escolha o período e os filtros para consultar a receita."
        closeLabel="Fechar filtros"
        size="md"
        header="inline"
      >
        {filtersOpen ? (
          <RevenueFiltersForm
            options={catalog.data?.data}
            initialFilters={parsed.base}
            searchKey={searchKey}
            envelope={envelope}
            onApply={applyFilters}
          />
        ) : null}
      </Modal>

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
          Carregando a receita para{" "}
          {competenceLabel(parsed.base.competencia_inicio)} —{" "}
          {competenceLabel(parsed.base.competencia_fim)}…
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
          <div className="grid min-w-0 gap-4 min-[1850px]:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]">
            <RevenueDecomposition envelope={envelope} />
            <RevenueBreakdown
              key={JSON.stringify([
                envelope.metadata.filters,
                envelope.metadata.period,
                parsed.groupBy,
              ])}
              envelope={envelope}
              groupBy={parsed.groupBy}
              onGroupByChange={applyGroupBy}
              onExplore={exploreBreakdownItem}
            />
          </div>
          <RevenueSeries envelope={envelope} />
        </>
      ) : null}
    </div>
  );
}
