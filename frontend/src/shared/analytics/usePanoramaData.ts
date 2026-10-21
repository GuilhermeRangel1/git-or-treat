import { useQuery } from "@tanstack/react-query";
import { apiClient } from "../api/client";
import { calculateSyntheticPanorama } from "./syntheticData";
import type { PanoramaData, PanoramaFilters } from "./types";

interface ApiEnvelope<T> {
  data: T;
  metadata?: {
    unidade?: string;
    periodo?: string;
    filtros_aplicados?: Record<string, unknown>;
    lote_gold_versao?: string;
    qualidade_cobertura?: string;
  };
}

export function usePanoramaData(filters: PanoramaFilters) {
  return useQuery<PanoramaData, Error>({
    queryKey: [
      "panorama",
      filters.periodo,
      filters.comparacao,
      filters.municipio,
      filters.classe,
    ],
    networkMode: "always",
    queryFn: async () => {
      // Tenta buscar da API FastAPI se configurada/disponível
      try {
        const params = new URLSearchParams({
          competencia: filters.periodo,
          comparacao: filters.comparacao,
          municipio: filters.municipio,
          classe: filters.classe,
        });

        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 5000);

        try {
          const res = await apiClient<ApiEnvelope<PanoramaData> | PanoramaData>(
            `/api/v1/kpis?${params.toString()}`,
            { signal: controller.signal },
          );

          if (
            res &&
            "data" in res &&
            (res as ApiEnvelope<PanoramaData>).data?.metricas
          ) {
            return (res as ApiEnvelope<PanoramaData>).data;
          }
          if (res && "metricas" in res) {
            return res as PanoramaData;
          }
        } finally {
          clearTimeout(timeoutId);
        }
      } catch {
        // Fallback resiliente para base sintética canônica
        // Garante fidelidade aos controles do protótipo mesmo sem backend ativo
      }

      return calculateSyntheticPanorama(filters);
    },
    staleTime: 1000 * 60 * 5, // 5 minutos
  });
}
