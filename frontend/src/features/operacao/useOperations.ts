import { useQuery } from "@tanstack/react-query";
import { apiClient, ApiError } from "@/shared/api/client";
import { useGoldPublicationKey } from "@/shared/analytics/goldPublication";
import { decodeGoldMetadata } from "@/shared/analytics/goldContract";
import {
  decodeOperationDetail,
  decodeOperationRanking,
  decodeOperationSummary,
  type OperationDetailEnvelope,
  type OperationMetric,
  type OperationRankingEnvelope,
  type OperationSummaryEnvelope,
} from "./contract";
import {
  decodeGoldOperationDetail,
  decodeGoldOperationRanking,
  decodeGoldOperationSummary,
  type GoldOperationDetailEnvelope,
  type GoldOperationRankingEnvelope,
  type GoldOperationSummaryEnvelope,
} from "./gold-contract";

export type OperationPeriodQuery = {
  start: string;
  end: string;
  feederId: string | null;
  municipality?: string | null;
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
  municipality?: string | null;
  source?: "gold" | "synthetic";
};

const CONTRACTS = { summary: "1.2.0|2.0.0", queries: "1.1.0|2.0.0" } as const;

function versionOf(value: unknown): unknown {
  return value && typeof value === "object" && "metadata" in value
    ? (value as { metadata?: { contract_version?: unknown } }).metadata
        ?.contract_version
    : undefined;
}

function periodParams(query: OperationPeriodQuery): URLSearchParams {
  const params = new URLSearchParams({
    competencia_inicio: query.start,
    competencia_fim: query.end,
  });
  if (query.feederId) params.set("alimentador", query.feederId);
  if (query.municipality) params.set("municipio", query.municipality);
  return params;
}

async function fetchSummary(
  query: OperationPeriodQuery,
  signal: AbortSignal,
): Promise<OperationSummaryEnvelope | GoldOperationSummaryEnvelope> {
  const params = periodParams(query);
  const response = await apiClient<unknown>(
    `/api/v1/operations/summary?${params}`,
    { signal },
  );
  return versionOf(response) === "2.0.0"
    ? decodeGoldOperationSummary(response, query)
    : decodeOperationSummary(response, query);
}

async function fetchRanking(
  query: OperationRankingQuery,
  signal: AbortSignal,
): Promise<OperationRankingEnvelope | GoldOperationRankingEnvelope> {
  const params = periodParams(query);
  params.set("metric", query.metric);
  const response = await apiClient<unknown>(
    `/api/v1/operations/ranking?${params}`,
    { signal },
  );
  return versionOf(response) === "2.0.0"
    ? decodeGoldOperationRanking(response, query.metric, query)
    : decodeOperationRanking(response, query.metric, query);
}

async function fetchDetail(
  query: OperationDetailQuery,
  signal: AbortSignal,
): Promise<OperationDetailEnvelope | GoldOperationDetailEnvelope> {
  const params = new URLSearchParams({
    competencia_inicio: query.start,
    competencia_fim: query.end,
  });
  if (query.source !== "gold") {
    params.set("page", String(query.page));
    params.set("page_size", String(query.pageSize));
  }
  if (query.municipality) params.set("municipio", query.municipality);
  const feederId = encodeURIComponent(query.feederId);
  const response = await apiClient<unknown>(
    `/api/v1/operations/feeders/${feederId}?${params}`,
    { signal },
  );
  return versionOf(response) === "2.0.0"
    ? decodeGoldOperationDetail(response, query)
    : decodeOperationDetail(response, query);
}

export function useOperationSummary(query: OperationPeriodQuery | null) {
  const publication = useGoldPublicationKey();
  return useQuery<OperationSummaryEnvelope | GoldOperationSummaryEnvelope>({
    queryKey: ["operations", "summary", CONTRACTS.summary, publication, query],
    enabled: query !== null,
    queryFn: ({ signal }) => {
      if (!query) throw new Error("Filtros de Operação inválidos.");
      return fetchSummary(query, signal);
    },
  });
}

export function useOperationRanking(query: OperationRankingQuery | null) {
  const publication = useGoldPublicationKey();
  return useQuery<OperationRankingEnvelope | GoldOperationRankingEnvelope>({
    queryKey: ["operations", "ranking", CONTRACTS.queries, publication, query],
    enabled: query !== null,
    queryFn: ({ signal }) => {
      if (!query) throw new Error("Filtros de ranking de Operação inválidos.");
      return fetchRanking(query, signal);
    },
  });
}

export function useOperationDetail(query: OperationDetailQuery | null) {
  const publication = useGoldPublicationKey();
  return useQuery<OperationDetailEnvelope | GoldOperationDetailEnvelope>({
    queryKey: ["operations", "detail", CONTRACTS.queries, publication, query],
    enabled: query !== null && query.feederId.length > 0,
    queryFn: ({ signal }) => {
      if (!query) throw new Error("Filtros do detalhe de Operação inválidos.");
      return fetchDetail(query, signal);
    },
  });
}

export type OperationOptions = {
  competencias: string[];
  municipios: string[];
  alimentadores: Array<{ id: string; municipio: string | null }>;
};

export function decodeOperationOptions(value: unknown): OperationOptions {
  if (!value || typeof value !== "object")
    throw new Error("Opções de operação inválidas.");
  const root = value as Record<string, unknown>;
  const metadata = decodeGoldMetadata(root.metadata);
  if (metadata.temporal_scope !== "snapshot" || metadata.period !== null)
    throw new Error("Metadados de opções Gold inválidos.");
  const data = root.data as Record<string, unknown> | undefined;
  if (
    !data ||
    !Array.isArray(data.competencias) ||
    !Array.isArray(data.municipios) ||
    !Array.isArray(data.alimentadores)
  )
    throw new Error("Opções de operação inválidas.");
  const month = (item: unknown) =>
    typeof item === "string" && /^(?!0000)\d{4}-(0[1-9]|1[0-2])$/.test(item);
  if (
    !data.competencias.every(month) ||
    !data.municipios.every((item) => typeof item === "string")
  )
    throw new Error("Opções de operação inválidas.");
  const feeders = data.alimentadores.map((item) => {
    if (!item || typeof item !== "object")
      throw new Error("Opções de operação inválidas.");
    const row = item as Record<string, unknown>;
    if (
      typeof row.id !== "string" ||
      !row.id.trim() ||
      (row.municipio !== null && typeof row.municipio !== "string")
    )
      throw new Error("Opções de operação inválidas.");
    return { id: row.id, municipio: row.municipio };
  });
  return {
    competencias: data.competencias,
    municipios: data.municipios,
    alimentadores: feeders,
  } as OperationOptions;
}

export function useOperationOptions(enabled = true) {
  const publication = useGoldPublicationKey();
  return useQuery({
    queryKey: ["operations", "options", "2.0.0", publication],
    enabled,
    queryFn: async ({ signal }) => {
      try {
        const response = await apiClient<unknown>(
          "/api/v1/operations/options",
          { signal },
        );
        return {
          kind: "gold" as const,
          options: decodeOperationOptions(response),
        };
      } catch (error) {
        const body =
          error instanceof ApiError &&
          error.data &&
          typeof error.data === "object"
            ? (error.data as Record<string, unknown>)
            : undefined;
        const errorObject =
          body?.error && typeof body.error === "object"
            ? (body.error as Record<string, unknown>)
            : undefined;
        if (
          error instanceof ApiError &&
          error.status === 422 &&
          errorObject?.code === "unsupported_source"
        )
          return { kind: "synthetic" as const, options: null };
        throw error;
      }
    },
  });
}
