import { useQuery } from "@tanstack/react-query";
import type { RevenueEnvelope } from "@/shared/analytics/revenueContract";
import { fetchRevenue } from "@/shared/analytics/revenueClient";
import type { RevenueQuery } from "./revenue-filters";
import { useGoldPublicationKey } from "@/shared/analytics/goldPublication";

export function useRevenue(query: RevenueQuery | null) {
  const publication = useGoldPublicationKey();
  return useQuery<RevenueEnvelope>({
    queryKey: ["revenue", publication, query],
    enabled: query !== null,
    queryFn: ({ signal }) => {
      if (!query) throw new Error("Filtros de receita inválidos.");
      return fetchRevenue(query, signal);
    },
    staleTime: 30_000,
  });
}
