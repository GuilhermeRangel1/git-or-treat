import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import { decodeRevenueEnvelope, type RevenueEnvelope } from "./contract";
import { revenueRequestParams, type RevenueQuery } from "./revenue-filters";

async function fetchRevenue(query: RevenueQuery, signal: AbortSignal) {
  const params = revenueRequestParams(query);
  const response = await apiClient<unknown>(`/api/v1/revenue?${params}`, {
    signal,
  });
  return decodeRevenueEnvelope(response);
}

export function useRevenue(query: RevenueQuery | null) {
  return useQuery<RevenueEnvelope>({
    queryKey: ["revenue", query],
    enabled: query !== null,
    queryFn: ({ signal }) => {
      if (!query) throw new Error("Filtros de receita inválidos.");
      return fetchRevenue(query, signal);
    },
    staleTime: 30_000,
  });
}
