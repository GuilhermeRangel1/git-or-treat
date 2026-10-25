import { useQuery } from "@tanstack/react-query";
import type {
  PanoramaData,
  PanoramaFilters,
} from "../../shared/analytics/types";
import { requestPanoramaInsight } from "./insightApi";

function matchesFilters(data: PanoramaData, filters: PanoramaFilters) {
  return (Object.keys(filters) as (keyof PanoramaFilters)[]).every(
    (key) => data.filtros[key] === filters[key],
  );
}

export function usePanoramaInsight(
  filters: PanoramaFilters,
  data: PanoramaData | undefined,
  enabled: boolean,
) {
  const hasRows = (data?.totalRegistros ?? 0) > 0;
  const matchesCurrentFilters = data ? matchesFilters(data, filters) : false;

  return useQuery({
    queryKey: ["panorama-insight", filters, data?.loteVersao],
    enabled: enabled && Boolean(data) && hasRows && matchesCurrentFilters,
    queryFn: ({ signal }) => {
      if (!data || !matchesCurrentFilters)
        throw new Error("O recorte atual ainda não está disponível.");
      return requestPanoramaInsight(filters, data, signal);
    },
    staleTime: 1000 * 60 * 5,
    retry: false,
    refetchOnWindowFocus: false,
  });
}
