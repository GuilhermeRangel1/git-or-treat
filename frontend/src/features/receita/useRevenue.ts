import { useQuery } from "@tanstack/react-query";
import type { RevenueEnvelope } from "@/shared/analytics/revenueContract";
import {
  fetchRevenue,
  fetchRevenueForContext,
} from "@/shared/analytics/revenueClient";
import type { RevenueQuery } from "./revenue-filters";
import { useGoldPublicationKey } from "@/shared/analytics/goldPublication";

export function useRevenue(
  query: RevenueQuery | null,
  includeDiagnosis = false,
) {
  const publication = useGoldPublicationKey();
  return useQuery<RevenueEnvelope>({
    queryKey: ["revenue", publication, query, includeDiagnosis],
    enabled: query !== null,
    queryFn: ({ signal }) => {
      if (!query) throw new Error("Filtros de receita inválidos.");
      return fetchRevenue(
        { ...query, include_diagnosis: includeDiagnosis },
        signal,
      );
    },
    staleTime: 30_000,
  });
}

export function useRevenueDiagnosis(
  query: RevenueQuery | null,
  enabled: boolean,
) {
  const publication = useGoldPublicationKey();
  return useQuery({
    queryKey: ["revenue-diagnosis", publication, query],
    enabled: enabled && query !== null,
    staleTime: 30_000,
    queryFn: async ({ signal }) => {
      if (!query) throw new Error("Recorte inválido.");
      const response = await fetchRevenueForContext(
        { ...query, include_diagnosis: true },
        signal,
      );
      return response.data.diagnosis ?? null;
    },
  });
}
