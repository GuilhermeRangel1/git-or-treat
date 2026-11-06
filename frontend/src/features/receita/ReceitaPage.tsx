import IndicatorHelp from "@/shared/help/IndicatorHelp";
import { useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { ApiError } from "@/shared/api/client";
import Button from "@/shared/ui/Button";
import Modal from "@/shared/ui/Modal";
import { useSourceOptions } from "@/shared/analytics/sourceOptions";
import RevenueFiltersForm from "./RevenueFiltersForm";
import RevenueBreakdown from "./RevenueBreakdown";
import RevenueDecomposition from "./RevenueDecomposition";
import RevenueHistory from "./RevenueHistory";
import RevenueSummary from "./RevenueSummary";
import RevenueOverview from "./RevenueOverview";
import RevenueInvestigation from "./RevenueInvestigation";
import type { RevenueWindowItem } from "./contract";
import {
  parseRevenueSearchParams,
  defaultRevenueFilters,
  revenueRefinementDestination,
  refineRevenueParams,
  updateRevenueBaseParams,
  updateRevenueGroupBy,
} from "./revenue-filters";
import { useRevenue, useRevenueDiagnosis } from "./useRevenue";

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
  const sections = [
    { key: "resumo", label: "Resumo" },
    { key: "investigar", label: "Investigar queda" },
  ] as const;
  const section =
    sections.find((item) => item.key === searchParams.get("aba"))?.key ??
    "resumo";
  const historyOpen =
    searchParams.get("historico") === "aberto" ||
    searchParams.get("aba") === "evolucao";
  const historyTriggerRef = useRef<HTMLButtonElement>(null);
  function selectSection(value: string, focus = false) {
    const next = new URLSearchParams(searchParams);
    next.set("aba", value);
    setSearchParams(next, { preventScrollReset: true });
    if (focus)
      requestAnimationFrame(() =>
        document.getElementById(`revenue-tab-${value}`)?.focus(),
      );
  }
  function viewDiagnosis() {
    selectSection("resumo");
    requestAnimationFrame(() =>
      requestAnimationFrame(() =>
        document.getElementById("revenue-overview-title")?.focus(),
      ),
    );
  }
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
  const diagnosis = useRevenueDiagnosis(
    parsed.query,
    section === "resumo" &&
      !historyOpen &&
      !!revenue.data?.data.window_decomposition &&
      revenue.data.data.window_decomposition.status !== "unavailable" &&
      !revenue.isError,
  );

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

  function exploreWindowItem(item: RevenueWindowItem) {
    const next = refineRevenueParams(
      searchParams,
      parsed.groupBy,
      item.filters,
    );
    next.set("aba", "investigar");
    setSearchParams(next, { preventScrollReset: true });
    requestAnimationFrame(() =>
      document.getElementById("investigation-title")?.focus(),
    );
  }
  const envelope = revenue.isError ? undefined : revenue.data;
  const analysisWindows =
    !historyOpen && envelope?.data.window_decomposition?.windows.length === 4
      ? envelope.data.window_decomposition.windows
      : null;
  const catalogMonths = catalog.data?.data.competencias ?? [];
  const businessComparison =
    !!analysisWindows &&
    catalogMonths.length >= 12 &&
    analysisWindows[0] === catalogMonths[0] &&
    analysisWindows[1] === catalogMonths[11] &&
    analysisWindows[2] === catalogMonths[catalogMonths.length - 12] &&
    analysisWindows[3] === catalogMonths[catalogMonths.length - 1];
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
    <div className="mt-6 grid min-w-0 w-full gap-4">
      {envelope?.metadata.source.is_demo ||
      envelope?.metadata.status === "unavailable" ||
      envelope?.metadata.status === "empty" ||
      (revenue.isFetching && envelope) ? (
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
      ) : null}

      <div className="flex justify-end">
        <IndicatorHelp screen="receita" />
      </div>
      <section
        aria-label="Filtros aplicados"
        className="mt-2 flex min-h-[92px] min-w-0 flex-wrap items-center justify-between gap-4 rounded-xl bg-surface px-4 py-4 xl:flex-nowrap"
      >
        <div className="flex min-w-0 flex-1 flex-col gap-2">
          <div className="grid min-w-0 flex-1 gap-3 md:grid-cols-[2fr_3fr]">
            <div className="min-w-0">
              <h2 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted">
                Comparação
              </h2>
              <dl className="grid min-w-0 grid-cols-2 gap-x-5 gap-y-2 text-sm">
                <div className="min-w-0">
                  <dt className="text-xs text-muted">
                    {analysisWindows
                      ? businessComparison
                        ? "Primeiro ano da base"
                        : "Período de referência"
                      : "Série: mês inicial"}
                  </dt>
                  <dd className="mt-1 truncate font-medium text-content">
                    {analysisWindows
                      ? `${competenceLabel(analysisWindows[0])}–${competenceLabel(analysisWindows[1])}`
                      : competenceLabel(
                          envelope?.metadata.period.start ??
                            parsed.base.competencia_inicio,
                        )}
                  </dd>
                </div>
                <div className="min-w-0">
                  <dt className="text-xs text-muted">
                    {analysisWindows
                      ? businessComparison
                        ? "Últimos 12 meses da base"
                        : "Período comparado"
                      : "Série: mês final"}
                  </dt>
                  <dd className="mt-1 truncate font-medium text-content">
                    {analysisWindows
                      ? `${competenceLabel(analysisWindows[2])}–${competenceLabel(analysisWindows[3])}`
                      : competenceLabel(
                          envelope?.metadata.period.end ??
                            parsed.base.competencia_fim,
                        )}
                  </dd>
                </div>
              </dl>
            </div>
            <div className="min-w-0">
              <h2 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted">
                Recorte
              </h2>
              <dl className="grid min-w-0 grid-cols-2 gap-x-5 gap-y-2 text-sm md:grid-cols-3">
                <div className="min-w-0">
                  <dt className="text-xs text-muted">Município</dt>
                  <dd className="mt-1 truncate font-medium text-content">
                    {filterLabel(
                      appliedFilters.municipio,
                      "Todos os municípios",
                    )}
                  </dd>
                </div>
                <div className="min-w-0">
                  <dt className="text-xs text-muted">Bairro</dt>
                  <dd className="mt-1 truncate font-medium text-content">
                    {filterLabel(appliedFilters.bairro, "Todos os bairros")}
                  </dd>
                </div>
                <div className="min-w-0">
                  <dt className="text-xs text-muted">Classe</dt>
                  <dd className="mt-1 truncate font-medium text-content">
                    {filterLabel(appliedFilters.classe, "Todas as classes")}
                  </dd>
                </div>
                {appliedFilters.alimentador ? (
                  <div className="min-w-0">
                    <dt className="text-xs text-muted">Alimentador legado</dt>
                    <dd className="mt-1 flex items-center gap-2 truncate font-medium text-content">
                      {appliedFilters.alimentador || "Todos os alimentadores"}
                      {appliedFilters.alimentador ? (
                        <button
                          type="button"
                          className="shrink-0 text-brand underline"
                          onClick={() => {
                            const next = new URLSearchParams(searchParams);
                            next.delete("alimentador");
                            setSearchParams(next, { preventScrollReset: true });
                          }}
                        >
                          Remover filtro de alimentador
                        </button>
                      ) : null}
                    </dd>
                  </div>
                ) : null}
              </dl>
            </div>
          </div>
          {analysisWindows ? (
            <p className="text-xs text-muted">
              {businessComparison
                ? "Primeiro ano × últimos 12 meses disponíveis. "
                : "Comparação fixada para este diagnóstico. "}
              Os filtros alteram o município, bairro e classe. Para localizar
              quando ocorreu a mudança, consulte o histórico deste recorte.
            </p>
          ) : null}
          {(parsed.refinements.municipio ||
            parsed.refinements.bairro ||
            parsed.refinements.classe) && (
            <nav
              aria-label="Caminho do recorte"
              className="flex flex-wrap items-center gap-1 text-xs"
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
          className="w-full lg:w-auto"
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
        description={
          analysisWindows
            ? "Escolha município, bairro e classe. As janelas da comparação são as publicadas pela Gold."
            : "Escolha o período e os filtros para consultar a receita."
        }
        closeLabel="Fechar filtros"
        size="md"
        header="inline"
      >
        {filtersOpen ? (
          <RevenueFiltersForm
            showPeriod={!analysisWindows}
            options={catalog.data?.data}
            initialFilters={{ ...parsed.base, ...parsed.refinements }}
            defaultFilters={defaults}
            searchKey={searchKey}
            envelope={envelope}
            onApply={applyFilters}
            onCancel={() => setFiltersOpen(false)}
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

      <div className="flex flex-wrap items-center gap-3">
        <div
          role="tablist"
          aria-label="Leituras da receita"
          className="flex gap-1 overflow-x-auto rounded-xl bg-surface p-1.5"
        >
          {sections.map((item, index) => (
            <button
              key={item.key}
              type="button"
              role="tab"
              id={`revenue-tab-${item.key}`}
              aria-selected={section === item.key}
              aria-controls={`revenue-panel-${item.key}`}
              tabIndex={section === item.key ? 0 : -1}
              onClick={() => selectSection(item.key)}
              onKeyDown={(event) => {
                const key = event.key;
                if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(key))
                  return;
                event.preventDefault();
                const next =
                  key === "Home"
                    ? 0
                    : key === "End"
                      ? sections.length - 1
                      : (index +
                          (key === "ArrowRight" ? 1 : -1) +
                          sections.length) %
                        sections.length;
                selectSection(sections[next].key, true);
              }}
              className={`min-h-11 flex-1 whitespace-nowrap rounded-lg px-4 py-2 text-sm font-medium focus-visible:outline-2 focus-visible:outline-brand ${section === item.key ? "bg-brand text-[var(--accent-goiaba-text)]" : "text-muted hover:bg-surface-hover"}`}
            >
              {item.label}
            </button>
          ))}
        </div>
        <Button
          ref={historyTriggerRef}
          type="button"
          variant="control"
          size="sm"
          onClick={() => {
            const next = new URLSearchParams(searchParams);
            next.set("historico", "aberto");
            setSearchParams(next, { preventScrollReset: true });
          }}
        >
          Ver histórico deste recorte
        </Button>
      </div>
      <Modal
        open={historyOpen}
        onClose={() => {
          const next = new URLSearchParams(searchParams);
          next.delete("historico");
          if (next.get("aba") === "evolucao") next.set("aba", "resumo");
          setSearchParams(next, { preventScrollReset: true });
        }}
        triggerRef={historyTriggerRef}
        title="Histórico do recorte"
        closeLabel="Fechar histórico"
        size="lg"
        header="inline"
      >
        <RevenueHistory
          key={`${parsed.base.competencia_inicio}:${parsed.base.competencia_fim}`}
          envelope={envelope}
          start={parsed.base.competencia_inicio}
          end={parsed.base.competencia_fim}
          competencies={catalog.data?.data.competencias ?? []}
          onApply={(start, end) => {
            const next = new URLSearchParams(searchParams);
            next.set("competencia_inicio", start);
            next.set("competencia_fim", end);
            setSearchParams(next, { preventScrollReset: true });
          }}
        />
      </Modal>
      {envelope ? (
        <section
          role="tabpanel"
          id={`revenue-panel-${section}`}
          aria-labelledby={`revenue-tab-${section}`}
          className="min-w-0"
        >
          {section === "resumo" ? (
            envelope.data.window_decomposition ? (
              <RevenueOverview
                envelope={{
                  ...envelope,
                  data: { ...envelope.data, diagnosis: diagnosis.data },
                }}
                diagnosisLoading={diagnosis.isFetching}
                diagnosisError={diagnosis.isError}
                onRetryDiagnosis={() => void diagnosis.refetch()}
                onInvestigate={() => {
                  const next = new URLSearchParams(searchParams);
                  next.set("aba", "investigar");
                  next.set("metrica", "volume");
                  setSearchParams(next, { preventScrollReset: true });
                  requestAnimationFrame(() =>
                    document.getElementById("revenue-tab-investigar")?.focus(),
                  );
                }}
              />
            ) : (
              <div className="grid gap-4">
                <RevenueSummary envelope={envelope} />
                <RevenueDecomposition envelope={envelope} />
                <Button
                  variant="accent"
                  onClick={() => selectSection("investigar", true)}
                >
                  Investigar recortes →
                </Button>
              </div>
            )
          ) : null}
          {section === "investigar" ? (
            envelope.data.window_decomposition &&
            envelope.data.window_decomposition.status !== "unavailable" ? (
              <RevenueInvestigation
                envelope={envelope}
                groupBy={parsed.groupBy}
                onGroupByChange={applyGroupBy}
                onExplore={exploreWindowItem}
                onViewDiagnosis={viewDiagnosis}
                metric={
                  ["volume", "preco", "receita"].includes(
                    searchParams.get("metrica") ?? "",
                  )
                    ? searchParams.get("metrica")!
                    : "volume"
                }
                onMetricChange={(value) => {
                  const next = new URLSearchParams(searchParams);
                  next.set("metrica", value);
                  setSearchParams(next, { preventScrollReset: true });
                }}
              />
            ) : (
              <div className="grid gap-4">
                {envelope.data.window_decomposition ? (
                  <p role="status" className="text-sm text-muted">
                    Decomposição por janelas indisponível. A investigação abaixo
                    compara somente{" "}
                    {competenceLabel(envelope.metadata.period.start)} e{" "}
                    {competenceLabel(envelope.metadata.period.end)}; não
                    representa os efeitos das janelas publicadas.
                  </p>
                ) : null}
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
            )
          ) : null}
        </section>
      ) : null}
    </div>
  );
}
