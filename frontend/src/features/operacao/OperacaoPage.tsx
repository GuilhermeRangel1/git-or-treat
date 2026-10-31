import { useEffect, useMemo } from "react";
import { useLocation, useSearchParams } from "react-router-dom";
import Button from "@/shared/ui/Button";
import OperationDetail from "./OperationDetail";
import OperationFilters from "./OperationFilters";
import OperationFoundations from "./OperationFoundations";
import OperationRanking from "./OperationRanking";
import OperationSummary from "./OperationSummary";
import OperationSource from "./OperationSource";
import GoldOperationView from "./GoldOperationView";
import type {
  OperationSummaryEnvelope,
  OperationRankingEnvelope,
  OperationDetailEnvelope,
} from "./contract";
import type {
  GoldOperationSummaryEnvelope,
  GoldOperationRankingEnvelope,
  GoldOperationDetailEnvelope,
} from "./gold-contract";

function isGoldSummary(
  value: OperationSummaryEnvelope | GoldOperationSummaryEnvelope | undefined,
): value is GoldOperationSummaryEnvelope {
  return value?.metadata.contract_version === "2.0.0";
}
function isGoldRanking(
  value: OperationRankingEnvelope | GoldOperationRankingEnvelope | undefined,
): value is GoldOperationRankingEnvelope {
  return value?.metadata.contract_version === "2.0.0";
}
function isGoldDetail(
  value: OperationDetailEnvelope | GoldOperationDetailEnvelope | undefined,
): value is GoldOperationDetailEnvelope {
  return value?.metadata.contract_version === "2.0.0";
}
import {
  applyOperationFilters,
  paginateOperationRanking,
  paginateOperationDetail,
  parseOperationParams,
  returnToOperationRanking,
} from "./operations-state";
import {
  useOperationDetail,
  useOperationOptions,
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
  const options = useOperationOptions(query !== null);
  useEffect(() => {
    if (options.data?.kind !== "gold") return;
    const current = new URLSearchParams(location.search);
    if (
      current.has("periodo") ||
      current.has("competencia_inicio") ||
      current.has("competencia_fim")
    )
      return;
    const latest = options.data.options.competencias.at(-1);
    if (!latest) return;
    current.set("competencia_inicio", latest);
    current.set("competencia_fim", latest);
    setSearchParams(current, { replace: true });
  }, [location.search, options.data, setSearchParams]);
  const goldFilterError =
    options.data?.kind === "gold" &&
    ((query?.municipality !== null &&
      query?.municipality !== undefined &&
      !options.data.options.municipios.includes(query.municipality)) ||
      (query?.feederId !== null &&
        query?.feederId !== undefined &&
        !options.data.options.alimentadores.some(
          (item) => item.id === query.feederId,
        )) ||
      (query !== null &&
        (!options.data.options.competencias.includes(query.start) ||
          !options.data.options.competencias.includes(query.end))));
  const unsupportedSyntheticFilter =
    options.data?.kind === "synthetic" &&
    query?.municipality !== null &&
    query?.municipality !== undefined;
  const readyQuery =
    !options.isPending &&
    !options.isError &&
    !goldFilterError &&
    !unsupportedSyntheticFilter
      ? query
      : null;
  const summaryQuery = readyQuery
    ? {
        start: readyQuery.start,
        end: readyQuery.end,
        feederId: readyQuery.feederId,
        municipality: readyQuery.municipality,
      }
    : null;
  const rankingQuery = readyQuery
    ? {
        start: readyQuery.start,
        end: readyQuery.end,
        feederId: readyQuery.feederId,
        municipality: readyQuery.municipality,
        metric: readyQuery.metric,
      }
    : null;
  const detailQuery = readyQuery?.detailFeederId
    ? {
        start: readyQuery.start,
        end: readyQuery.end,
        feederId: readyQuery.detailFeederId,
        page: readyQuery.page,
        pageSize: readyQuery.pageSize,
        municipality: readyQuery.municipality,
        source: options.data?.kind,
      }
    : null;

  const summary = useOperationSummary(summaryQuery);
  const ranking = useOperationRanking(rankingQuery);
  const detail = useOperationDetail(detailQuery);
  const goldSummary = isGoldSummary(summary.data) ? summary.data : undefined;
  const syntheticSummary =
    summary.data && !isGoldSummary(summary.data) ? summary.data : undefined;
  const goldRanking = isGoldRanking(ranking.data) ? ranking.data : undefined;
  const syntheticRanking =
    ranking.data && !isGoldRanking(ranking.data) ? ranking.data : undefined;
  const goldDetail = isGoldDetail(detail.data) ? detail.data : undefined;
  const syntheticDetail =
    detail.data && !isGoldDetail(detail.data) ? detail.data : undefined;
  const pageTitle = query?.detailFeederId
    ? `${query.detailFeederId} / visão do alimentador`
    : "Continuidade, onde importa.";
  const pageSubtitle = query?.detailFeederId
    ? `${goldDetail?.data.summary.municipality ?? syntheticDetail?.data.summary.municipalities.join(", ") ?? "Território não informado"} · ${goldDetail ? "evolução mensal · agregado Gold" : "evolução mensal · ocorrências"}`
    : "Compare alimentadores e investigue os registros que sustentam os indicadores internos.";
  const pageSource = query?.detailFeederId
    ? (detail.data?.metadata.source ?? summary.data?.metadata.source)
    : summary.data?.metadata.source;

  const feederOptions =
    options.data?.kind === "gold"
      ? options.data.options.alimentadores.map((item) => item.id)
      : Array.from(
          new Set([
            ...(isGoldSummary(summary.data)
              ? []
              : (summary.data?.data.summary.included_feeder_ids ?? [])),
            ...(isGoldSummary(summary.data)
              ? []
              : (summary.data?.data.summary.excluded_feeder_ids ?? [])),
            ...(ranking.data?.data.items.map((item) => item.feeder_id) ?? []),
            ...(ranking.data?.data.excluded.map((item) => item.feeder_id) ??
              []),
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
      {options.data?.kind === "synthetic" ? (
        <OperationSource source={pageSource} />
      ) : null}
      <OperationFilters
        query={query}
        feederOptions={feederOptions}
        municipalityOptions={
          options.data?.kind === "gold" ? options.data.options.municipios : []
        }
        competencyOptions={
          options.data?.kind === "gold" ? options.data.options.competencias : []
        }
        onApply={(filters) =>
          updateSearch(
            applyOperationFilters(new URLSearchParams(location.search), {
              ...filters,
              municipality: filters.municipality,
            }),
          )
        }
      />
      {options.data?.kind === "gold" &&
      ((summary.isFetching && summary.data) ||
        (ranking.isFetching && ranking.data) ||
        (detail.isFetching && detail.data)) ? (
        <p role="status" className="text-sm text-muted">
          Atualizando consultas Gold; a última resposta válida permanece
          visível.
        </p>
      ) : null}
      {options.isError ? (
        <p
          role="alert"
          className="rounded-xl border border-danger/30 bg-surface p-4 text-sm"
        >
          Não foi possível descobrir o escopo disponível para Operação. Consulte
          as permissões de leitura Gold e tente novamente.
        </p>
      ) : null}
      {unsupportedSyntheticFilter ? (
        <p
          role="alert"
          className="rounded-xl border border-danger/30 bg-surface p-4 text-sm"
        >
          O filtro de município está disponível somente na fonte Gold. Remova o
          filtro para consultar a fonte sintética.
        </p>
      ) : null}
      {goldFilterError ? (
        <div
          role="alert"
          className="rounded-xl border border-danger/30 bg-surface p-4 text-sm"
        >
          <strong>O recorte da URL não existe na publicação Gold atual.</strong>
          <p>
            Atualize o município, alimentador e competências usando os filtros
            disponíveis; nenhuma consulta analítica foi enviada para esse
            recorte.
          </p>
        </div>
      ) : null}
      {options.data?.kind === "gold" &&
      options.data.options.competencias.length === 0 ? (
        <p
          role="status"
          className="rounded-xl bg-surface p-4 text-sm text-muted"
        >
          A fonte Gold não publicou competências disponíveis para Operação.
        </p>
      ) : null}
      {query.detailFeederId ? (
        options.data?.kind === "gold" ? (
          <GoldOperationView
            summary={goldSummary}
            ranking={goldRanking}
            detail={goldDetail}
            metric={query.metric}
            search={location.search}
            rankingPage={query.rankingPage}
            onMetricChange={updateSearch}
            onRankingPage={(page) =>
              updateSearch(
                paginateOperationRanking(
                  new URLSearchParams(location.search),
                  page,
                ),
              )
            }
            detailLoading={detail.isLoading}
            detailError={detail.isError}
            onRetryDetail={() => void detail.refetch()}
            onBack={() =>
              updateSearch(
                returnToOperationRanking(new URLSearchParams(location.search)),
              )
            }
          />
        ) : (
          <>
            <OperationDetail
              feederId={query.detailFeederId}
              period={{
                start: query.start,
                end: query.end,
                granularity: "month",
              }}
              data={syntheticDetail}
              isLoading={detail.isLoading}
              isFetching={detail.isFetching}
              isError={detail.isError}
              onRetry={() => void detail.refetch()}
              onBack={() =>
                updateSearch(
                  returnToOperationRanking(
                    new URLSearchParams(location.search),
                  ),
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
            <OperationFoundations detail={syntheticDetail} />
          </>
        )
      ) : options.data?.kind === "gold" ? (
        <GoldOperationView
          summary={goldSummary}
          ranking={goldRanking}
          metric={query.metric}
          search={location.search}
          rankingPage={query.rankingPage}
          onMetricChange={updateSearch}
          onRankingPage={(page) =>
            updateSearch(
              paginateOperationRanking(
                new URLSearchParams(location.search),
                page,
              ),
            )
          }
          summaryError={summary.isError}
          rankingLoading={ranking.isLoading}
          rankingError={ranking.isError}
          onRetrySummary={() => void summary.refetch()}
          onRetryRanking={() => void ranking.refetch()}
          onBack={() =>
            updateSearch(
              returnToOperationRanking(new URLSearchParams(location.search)),
            )
          }
        />
      ) : (
        <>
          <OperationSummary
            data={syntheticSummary}
            isLoading={summary.isLoading}
            isFetching={summary.isFetching}
            isError={summary.isError}
            onRetry={() => void summary.refetch()}
          />
          <OperationRanking
            data={syntheticRanking}
            metric={query.metric}
            search={location.search}
            isLoading={ranking.isLoading}
            isFetching={ranking.isFetching}
            isError={ranking.isError}
            onRetry={() => void ranking.refetch()}
            onMetricChange={updateSearch}
          />
          <OperationFoundations summary={syntheticSummary} />
        </>
      )}
    </div>
  );
}
