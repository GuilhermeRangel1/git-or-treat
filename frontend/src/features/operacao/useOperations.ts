import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import {
  decodeOperationDetail,
  decodeOperationRanking,
  decodeOperationSummary,
  type OperationDetailEnvelope,
  type OperationMetric,
  type OperationRankingEnvelope,
  type OperationSummaryEnvelope,
} from "./contract";

export type OperationPeriodQuery = {
  start: string;
  end: string;
  feederId: string | null;
};
export type OperationRankingQuery = OperationPeriodQuery & {
  metric: OperationMetric;
};
export type OperationDetailQuery = {
  start: string;
  end: string;
  feederId: string;
  page: number;
  pageSize: number;
};

const CONTRACTS = { summary: "1.2.0", queries: "1.1.0" } as const;

function periodParams(query: OperationPeriodQuery): URLSearchParams {
  const params = new URLSearchParams({
    competencia_inicio: query.start,
    competencia_fim: query.end,
  });
  if (query.feederId) params.set("alimentador", query.feederId);
  return params;
}

async function fetchSummary(
  query: OperationPeriodQuery,
  signal: AbortSignal,
): Promise<OperationSummaryEnvelope> {
  const params = periodParams(query);
  const response = await apiClient<unknown>(
    `/api/v1/operations/summary?${params}`,
    { signal },
  );
  return decodeOperationSummary(response, query);
}

async function fetchRanking(
  query: OperationRankingQuery,
  signal: AbortSignal,
): Promise<OperationRankingEnvelope> {
  const params = periodParams(query);
  params.set("metric", query.metric);
  const response = await apiClient<unknown>(
    `/api/v1/operations/ranking?${params}`,
    { signal },
  );
  return decodeOperationRanking(response, query.metric, query);
}

async function fetchDetail(
  query: OperationDetailQuery,
  signal: AbortSignal,
): Promise<OperationDetailEnvelope> {
  const params = new URLSearchParams({
    competencia_inicio: query.start,
    competencia_fim: query.end,
    page: String(query.page),
    page_size: String(query.pageSize),
  });
  const feederId = encodeURIComponent(query.feederId);
  const response = await apiClient<unknown>(
    `/api/v1/operations/feeders/${feederId}?${params}`,
    { signal },
  );
  return decodeOperationDetail(response, query);
}

export function useOperationSummary(query: OperationPeriodQuery | null) {
  return useQuery<OperationSummaryEnvelope>({
    queryKey: ["operations", "summary", CONTRACTS.summary, query],
    enabled: query !== null,
    queryFn: ({ signal }) => {
      if (!query) throw new Error("Filtros de Operação inválidos.");
      return fetchSummary(query, signal);
    },
  });
}

export function useOperationRanking(query: OperationRankingQuery | null) {
  return useQuery<OperationRankingEnvelope>({
    queryKey: ["operations", "ranking", CONTRACTS.queries, query],
    enabled: query !== null,
    queryFn: ({ signal }) => {
      if (!query) throw new Error("Filtros de ranking de Operação inválidos.");
      return fetchRanking(query, signal);
    },
  });
}

export function useOperationDetail(query: OperationDetailQuery | null) {
  return useQuery<OperationDetailEnvelope>({
    queryKey: ["operations", "detail", CONTRACTS.queries, query],
    enabled: query !== null && query.feederId.length > 0,
    queryFn: ({ signal }) => {
      if (!query) throw new Error("Filtros do detalhe de Operação inválidos.");
      return fetchDetail(query, signal);
    },
  });
}
