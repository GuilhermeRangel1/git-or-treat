import { useMemo } from "react";
import { useLocation, useSearchParams } from "react-router-dom";
import Button from "@/shared/ui/Button";
import OperationDetail from "./OperationDetail";
import OperationFilters from "./OperationFilters";
import OperationFoundations from "./OperationFoundations";
import OperationRanking from "./OperationRanking";
import OperationSummary from "./OperationSummary";
import OperationSource from "./OperationSource";
import {
  applyOperationFilters,
  paginateOperationDetail,
  parseOperationParams,
  returnToOperationRanking,
} from "./operations-state";
import {
  useOperationDetail,
  useOperationRanking,
  useOperationSummary,
} from "./useOperations";

export default function OperacaoPage() {
  const location = useLocation();
  const [, setSearchParams] = useSearchParams();
  const parsed = useMemo(
    () => parseOperationParams(new URLSearchParams(location.search)),
    [location.search],
  );
  const query = parsed.query;
  const summaryQuery = query
    ? { start: query.start, end: query.end, feederId: query.feederId }
    : null;
  const rankingQuery = query
    ? {
        start: query.start,
        end: query.end,
        feederId: query.feederId,
        metric: query.metric,
      }
    : null;
  const detailQuery = query?.detailFeederId
    ? {
        start: query.start,
        end: query.end,
        feederId: query.detailFeederId,
        page: query.page,
        pageSize: query.pageSize,
      }
    : null;

  const summary = useOperationSummary(summaryQuery);
  const ranking = useOperationRanking(rankingQuery);
  const detail = useOperationDetail(detailQuery);
  const pageTitle = query?.detailFeederId
    ? `${query.detailFeederId} / visão do alimentador`
    : "Continuidade, onde importa.";
  const pageSubtitle = query?.detailFeederId
    ? `${detail.data?.data.summary.municipalities.join(", ") || "Território não informado"} · evolução mensal · ocorrências`
    : "Compare alimentadores e investigue os registros que sustentam os indicadores internos.";
  const pageSource = query?.detailFeederId
    ? (detail.data?.metadata.source ?? summary.data?.metadata.source)
    : summary.data?.metadata.source;

  const feederOptions = Array.from(
    new Set([
      ...(summary.data?.data.summary.included_feeder_ids ?? []),
      ...(summary.data?.data.summary.excluded_feeder_ids ?? []),
      ...(ranking.data?.data.items.map((item) => item.feeder_id) ?? []),
      ...(ranking.data?.data.excluded.map((item) => item.feeder_id) ?? []),
      ...(query?.feederId ? [query.feederId] : []),
      ...(query?.detailFeederId ? [query.detailFeederId] : []),
    ]),
  );
  feederOptions.sort();

  function updateSearch(next: URLSearchParams) {
    setSearchParams(next);
  }

  if (!query) {
    return (
      <section className="mt-6 grid gap-4 rounded-xl border border-danger/30 bg-surface p-5">
        <div role="alert" className="grid gap-2">
          <h2 className="font-heading text-lg font-semibold">
            Parâmetros de operação inválidos
          </h2>
          <p className="text-sm text-muted">
            A URL contém filtros que esta consulta não aceita. Nenhuma consulta
            foi feita.
          </p>
          <ul className="list-inside list-disc text-sm text-danger">
            {parsed.errors.map((error) => (
              <li key={error}>{error}</li>
            ))}
          </ul>
        </div>
        <Button
          className="w-fit"
          variant="secondary"
          onClick={() => updateSearch(new URLSearchParams())}
        >
          Restaurar filtros
        </Button>
      </section>
    );
  }

  return (
    <div className="grid min-w-0 gap-6 [overflow-wrap:anywhere]">
      <header className="grid gap-2">
        <h1 className="font-heading text-[26px] leading-[34px] font-semibold lg:text-[32px] lg:leading-10 lg:tracking-[-0.64px]">
          {pageTitle}
        </h1>
        <p className="text-sm leading-[22px] text-muted">{pageSubtitle}</p>
      </header>
      <OperationSource source={pageSource} />
      <OperationFilters
        query={query}
        feederOptions={feederOptions}
        onApply={(filters) =>
          updateSearch(
            applyOperationFilters(
              new URLSearchParams(location.search),
              filters,
            ),
          )
        }
      />
      {query.detailFeederId ? (
        <>
          <OperationDetail
            feederId={query.detailFeederId}
            period={{
              start: query.start,
              end: query.end,
              granularity: "month",
            }}
            data={detail.data}
            isLoading={detail.isLoading}
            isFetching={detail.isFetching}
            isError={detail.isError}
            onRetry={() => void detail.refetch()}
            onBack={() =>
              updateSearch(
                returnToOperationRanking(new URLSearchParams(location.search)),
              )
            }
            onPaginate={(page) =>
              updateSearch(
                paginateOperationDetail(
                  new URLSearchParams(location.search),
                  page,
                ),
              )
            }
          />
          <OperationFoundations detail={detail.data} />
        </>
      ) : (
        <>
          <OperationSummary
            data={summary.data}
            isLoading={summary.isLoading}
            isFetching={summary.isFetching}
            isError={summary.isError}
            onRetry={() => void summary.refetch()}
          />
          <OperationRanking
            data={ranking.data}
            metric={query.metric}
            search={location.search}
            isLoading={ranking.isLoading}
            isFetching={ranking.isFetching}
            isError={ranking.isError}
            onRetry={() => void ranking.refetch()}
            onMetricChange={updateSearch}
          />
          <OperationFoundations summary={summary.data} />
        </>
      )}
    </div>
  );
}
