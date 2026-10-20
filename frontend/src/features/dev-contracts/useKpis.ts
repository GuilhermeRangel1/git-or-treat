import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import { decodeKpisEnvelope, type KpisEnvelope } from "./contract";

export type KpisFilters = {
  competencia_inicio: string;
  competencia_fim: string;
  municipio: string;
  classe: string;
};

function queryString(filters: KpisFilters) {
  const params = new URLSearchParams();
  params.set("competencia_inicio", filters.competencia_inicio);
  params.set("competencia_fim", filters.competencia_fim);
  if (filters.municipio) params.set("municipio", filters.municipio);
  if (filters.classe) params.set("classe", filters.classe);
  return params.toString();
}

async function fetchKpis(filters: KpisFilters, signal: AbortSignal) {
  const response = await apiClient<unknown>(
    `/api/v1/kpis?${queryString(filters)}`,
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
