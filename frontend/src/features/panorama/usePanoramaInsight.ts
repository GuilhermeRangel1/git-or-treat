import {
  useGoldPublicationRevision,
  isGoldPublicationStale,
} from "../../shared/analytics/goldPublication";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import type {
  PanoramaData,
  PanoramaFilters,
} from "../../shared/analytics/types";
import {
  requestPanoramaInsight,
  verifyPanoramaInsightContext,
} from "./insightApi";
import type { PanoramaInsightEnvelope } from "./insightContract";

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
  const publicationRevision = useGoldPublicationRevision();
  const client = useQueryClient();
  const hasRows = (data?.totalRegistros ?? 0) > 0;
  const matchesCurrentFilters = data ? matchesFilters(data, filters) : false;

  const metric =
    data?.origem?.kind === "gold"
      ? data.metricas.receitaFaturada
      : data?.metricas.energiaFaturada;
  const queryKey = [
    "panorama-insight",
    publicationRevision,
    filters,
    data?.loteVersao,
    data?.origem?.fingerprint,
    data?.dataAtualizacao,
    data?.origem?.kind,
    metric?.valorAtual,
    metric?.valorAnterior,
    metric?.unidade,
  ];
  return useQuery({
    queryKey,
    enabled:
      enabled &&
      !isGoldPublicationStale() &&
      Boolean(data) &&
      hasRows &&
      matchesCurrentFilters,
    queryFn: async ({ signal }) => {
      if (!data || !matchesCurrentFilters)
        throw new Error("O recorte atual ainda não está disponível.");
      const cached = client.getQueryData<PanoramaInsightEnvelope>(queryKey);
      if (
        cached?.insight?.status === "answered" &&
        data.origem?.kind === "gold"
      ) {
        await verifyPanoramaInsightContext(
          data,
          signal,
          cached.analysis?.composicaoAtual?.dimension === "bairro",
        );
        return cached;
      }
      return requestPanoramaInsight(filters, data, signal);
    },
    staleTime: data?.origem?.kind === "gold" ? 0 : 1000 * 60 * 5,
    retry: false,
    refetchOnWindowFocus: data?.origem?.kind === "gold",
  });
}
