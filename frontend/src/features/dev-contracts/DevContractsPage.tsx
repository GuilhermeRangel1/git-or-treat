import { useEffect } from "react";
import { useLocation, useSearchParams } from "react-router-dom";
import { ApiError } from "@/shared/api/client";
import ThemeToggle from "@/shared/ui/ThemeToggle";
import { ContractError, type DataStatus } from "./contract";
import { useKpis } from "./useKpis";
import { KpisFiltersForm } from "./KpisFiltersForm";
import {
  defaultKpisFilters,
  kpisSearchParams,
  readKpisFilters,
} from "./kpis-filters";

const statusLabels: Record<DataStatus, string> = {
  available: "Disponível",
  empty: "Sem registros",
  partial: "Parcial",
  unavailable: "Indisponível",
};

function formatValue(value: number | null, unit: string) {
  if (value === null) return "Sem valor informado";
  if (unit === "BRL") {
    return new Intl.NumberFormat("pt-BR", {
      style: "currency",
      currency: "BRL",
    }).format(value);
  }
  return `${new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 4 }).format(value)} ${unit}`;
}

function errorMessage(error: Error) {
  if (error instanceof ContractError) {
    return "A resposta recebida não segue o contrato de indicadores esperado.";
  }
  if (error instanceof ApiError) {
    if (error.status === 503)
      return "A fonte de indicadores está indisponível.";
    if (error.kind === "network") return "Não foi possível conectar à API.";
    if (error.kind === "configuration")
      return "Configure VITE_API_URL para consultar a API.";
    return error.message;
  }
  return "Não foi possível carregar os indicadores.";
}

export function DevContractsPage() {
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();
  const selection = readKpisFilters(searchParams);
  const invalid = selection && Object.keys(selection.errors).length > 0;
  const applied = selection && !invalid ? selection.filters : null;
  const search = searchParams.toString();
  const normalizedSearch = invalid
    ? search
    : applied
      ? kpisSearchParams(applied).toString()
      : "";
  useEffect(() => {
    if (search !== normalizedSearch) {
      setSearchParams(normalizedSearch, { replace: true });
    }
  }, [search, normalizedSearch, setSearchParams]);
  const query = useKpis(applied);

  const result = query.data;
  const hasMetrics = Boolean(result && result.data.metrics.length > 0);

  return (
    <main className="min-h-dvh bg-canvas px-4 py-8 text-content sm:px-8">
      <div className="mx-auto w-full max-w-5xl space-y-6">
        <header className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="space-y-3">
            <p className="font-mono text-xs tracking-wide text-muted">
              DADOS SINTÉTICOS DE DEMONSTRAÇÃO
            </p>
            <h1 className="font-heading text-3xl font-semibold tracking-tight sm:text-4xl">
              Diagnóstico de contratos
            </h1>
            <p className="max-w-3xl text-sm leading-6 text-muted">
              Consulta de desenvolvimento para conferir o contrato HTTP de
              indicadores. Estes dados não representam diagnóstico operacional.
            </p>
          </div>
          <ThemeToggle />
        </header>

        <KpisFiltersForm
          navigationKey={location.key}
          initialFilters={selection?.filters ?? defaultKpisFilters}
          initialErrors={selection?.errors}
          onApply={(filters) => setSearchParams(kpisSearchParams(filters))}
        />

        {query.isPending && applied ? (
          <p
            className="rounded-xl border border-border bg-surface p-5 text-sm text-muted"
            role="status"
          >
            Carregando indicadores…
          </p>
        ) : null}

        {query.isFetching && result ? (
          <p
            className="rounded-xl border border-border bg-surface p-5 text-sm text-muted"
            role="status"
          >
            Atualizando indicadores… Os últimos dados válidos deste recorte
            continuam visíveis.
          </p>
        ) : null}

        {query.isError ? (
          <section
            aria-live="polite"
            className="rounded-xl border border-danger bg-surface p-5 text-sm text-content"
            role="alert"
          >
            <h2 className="font-semibold">Falha na consulta</h2>
            <p className="mt-1">{errorMessage(query.error)}</p>
            {applied ? (
              <button
                className="mt-3 min-h-11 rounded-lg border border-control px-4 font-medium text-content hover:bg-surface-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand disabled:opacity-60"
                type="button"
                onClick={() => void query.refetch()}
                disabled={query.isFetching}
              >
                {query.isFetching ? "Tentando novamente…" : "Tentar novamente"}
              </button>
            ) : null}
          </section>
        ) : null}

        {result && result.metadata.status === "unavailable" ? (
          <p
            className="rounded-xl border border-border bg-surface p-5 text-sm"
            role="status"
          >
            Fonte indisponível para este recorte.
          </p>
        ) : null}
        {result && result.metadata.status === "empty" ? (
          <p
            className="rounded-xl border border-border bg-surface p-5 text-sm"
            role="status"
          >
            Nenhum registro encontrado para os filtros aplicados.
          </p>
        ) : null}
        {result && result.metadata.status === "partial" ? (
          <p
            className="rounded-xl border border-border bg-surface p-5 text-sm"
            role="status"
          >
            Resultado parcial. Consulte as limitações e a cobertura informadas.
          </p>
        ) : null}
        {result && result.metadata.status === "available" && !hasMetrics ? (
          <p
            className="rounded-xl border border-border bg-surface p-5 text-sm"
            role="status"
          >
            Nenhuma métrica foi devolvida para este recorte.
          </p>
        ) : null}

        {result ? (
          <section aria-label="Resultado dos indicadores" className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {result.data.metrics.map((metric) => (
                <article
                  key={metric.id}
                  className="space-y-2 rounded-xl border border-border bg-surface p-5 shadow-sm"
                >
                  <div className="flex items-start justify-between gap-3">
                    <h2 className="text-sm font-medium text-muted">
                      {metric.label}
                    </h2>
                    <span className="rounded-full bg-selected px-2.5 py-1 text-xs text-content">
                      {statusLabels[metric.status]}
                    </span>
                  </div>
                  <p
                    className="font-heading text-2xl font-semibold"
                    aria-label={`${metric.label}: ${formatValue(metric.value, metric.unit)}`}
                  >
                    {formatValue(metric.value, metric.unit)}
                  </p>
                  <p className="font-mono text-xs text-muted">
                    Unidade: {metric.unit}
                  </p>
                  {metric.limitations.map((limitation) => (
                    <p
                      key={limitation}
                      className="text-xs leading-5 text-muted"
                    >
                      {limitation}
                    </p>
                  ))}
                </article>
              ))}
            </div>
            <section className="space-y-2 rounded-xl border border-border bg-surface p-5 text-sm">
              <h2 className="font-semibold">Proveniência e recorte</h2>
              <p>
                Período: {result.metadata.period.start} a{" "}
                {result.metadata.period.end} · Granularidade:{" "}
                {result.metadata.period.granularity}
              </p>
              <p>
                Fonte: {result.metadata.source.kind} · versão{" "}
                {result.metadata.source.version} · contrato{" "}
                {result.metadata.contract_version}
              </p>
              <p>Atualizado em: {result.metadata.source.updated_at}</p>
              <p>
                Filtros aplicados: município{" "}
                {result.metadata.filters.municipio ?? "todos"}; classe{" "}
                {result.metadata.filters.classe ?? "todas"}
              </p>
              {result.metadata.limitations.map((limitation) => (
                <p key={limitation} className="leading-5 text-muted">
                  {limitation}
                </p>
              ))}
            </section>
          </section>
        ) : null}
      </div>
    </main>
  );
}
