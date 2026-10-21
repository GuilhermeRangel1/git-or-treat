import { useQuery } from "@tanstack/react-query";
import { apiClient } from "../api/client";
import { decodePanorama } from "./panoramaContract";
import type { PanoramaFilters } from "./types";

export function usePanoramaData(filters: PanoramaFilters) {
  return useQuery({
    queryKey: ["panorama", filters],
    queryFn: async ({ signal }) => {
      const params = new URLSearchParams({
        competencia: filters.periodo,
        comparacao: filters.comparacao,
        municipio: filters.municipio,
        classe: filters.classe,
      });
      return decodePanorama(
        await apiClient<unknown>(`/api/v1/panorama?${params}`, { signal }),
        filters,
      );
    },
    staleTime: 1000 * 60 * 5,
  });
}
