import { useQuery } from "@tanstack/react-query";
import { apiClient } from "../api/client";
import { decodePanorama } from "./panoramaContract";
import type { PanoramaFilters } from "./types";
import { useGoldPublicationKey } from "./goldPublication";

export function usePanoramaData(
  filters: PanoramaFilters,
  enabled = true,
  bootstrap = false,
  discoverSource = false,
) {
  const publicationKey = useGoldPublicationKey();
  const requestFilters = discoverSource
    ? { ...filters, municipio: "todos", classe: "todas" }
    : filters;
  return useQuery({
    queryKey: ["panorama", publicationKey, filters, bootstrap, discoverSource],
    enabled,
    queryFn: async ({ signal }) => {
      if (!enabled) throw new Error("Filtros inválidos.");
      const params = new URLSearchParams({
        comparacao: requestFilters.comparacao,
        municipio: requestFilters.municipio,
        classe: requestFilters.classe,
      });
      if (!bootstrap) params.set("competencia", filters.periodo);
      return decodePanorama(
        await apiClient<unknown>(`/api/v1/panorama?${params}`, { signal }),
        requestFilters,
        bootstrap,
      );
    },
    staleTime: 1000 * 60 * 5,
  });
}
