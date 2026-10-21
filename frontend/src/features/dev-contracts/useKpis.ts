import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import { decodeKpisEnvelope, type KpisEnvelope } from "./contract";
import { kpisSearchParams, type KpisFilters } from "./kpis-filters";

async function fetchKpis(filters: KpisFilters, signal: AbortSignal) {
  const response = await apiClient<unknown>(
    `/api/v1/kpis?${kpisSearchParams(filters)}`,
    { signal },
  );
  return decodeKpisEnvelope(response);
}

export function useKpis(filters: KpisFilters | null) {
  return useQuery<KpisEnvelope>({
    queryKey: ["dev-contracts", "kpis", filters],
    enabled: filters !== null,
    queryFn: ({ signal }) => {
      if (!filters) throw new Error("Filtros não aplicados.");
      return fetchKpis(filters, signal);
    },
    staleTime: 30_000,
  });
}
