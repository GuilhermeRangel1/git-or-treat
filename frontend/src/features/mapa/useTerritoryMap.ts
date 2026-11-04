import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import {
  isGoldPublicationStale,
  useGoldPublicationKey,
  useGoldPublicationRevision,
} from "@/shared/analytics/goldPublication";
import { useSession } from "@/shared/auth/useSession";
import { useSourceOptions } from "@/shared/analytics/sourceOptions";
import { fetchRevenueForContext } from "@/shared/analytics/revenueClient";
import { municipalities, municipalityByCode } from "./municipalities";
import {
  municipalityDetailRequest,
  mapMunicipalityMetrics,
  validateMunicipalityDetail,
} from "./contract";
import { parseMapSearchParams } from "./map-state";
import { currentMapSummary } from "./map-result";

export function useTerritoryMap() {
  const [searchParams] = useSearchParams();
  const searchKey = searchParams.toString();
  const catalog = useSourceOptions();
  const { user } = useSession();
  const publication = useGoldPublicationKey();
  const publicationRevision = useGoldPublicationRevision();
  const publicationStale = isGoldPublicationStale();
  const defaults = useMemo(
    () => ({
      months: catalog.data?.data.competencias ?? [],
      classes: catalog.data?.data.classe ?? [],
      municipalityCodes: municipalities.map(
        (municipality) => municipality.code,
      ),
    }),
    [catalog.data],
  );
  const parsed = useMemo(
    () => parseMapSearchParams(new URLSearchParams(searchKey), defaults),
    [defaults, searchKey],
  );
  const request = parsed.query
    ? {
        competencia_inicio: parsed.query.competencia_inicio,
        competencia_fim: parsed.query.competencia_fim,
        municipio: "",
        bairro: "",
        classe: parsed.query.classe,
        alimentador: "",
        group_by: "municipio" as const,
      }
    : null;
  const summary = useQuery({
    queryKey: [
      "territory-map",
      user?.id ?? "anonymous",
      publication,
      "summary",
      request,
    ],
    enabled: Boolean(request && catalog.data) && !publicationStale,
    queryFn: async ({ signal }) => {
      if (!request) throw new Error("Filtros de mapa inválidos.");
      const envelope = await fetchRevenueForContext(request, signal);
      return { envelope, mapped: mapMunicipalityMetrics(envelope) };
    },
    staleTime: 30_000,
    retry: false,
  });
  const selected = parsed.query?.municipio
    ? municipalityByCode(parsed.query.municipio)
    : undefined;
  const detailRequest =
    request && selected && catalog.data
      ? municipalityDetailRequest(
          request,
          selected,
          catalog.data.data.municipio,
        )
      : null;
  const detail = useQuery({
    queryKey: [
      "territory-map",
      user?.id ?? "anonymous",
      publication,
      "detail",
      detailRequest,
    ],
    enabled: Boolean(detailRequest) && !publicationStale,
    queryFn: async ({ signal }) => {
      if (!detailRequest)
        throw new Error("Município sem correspondência no catálogo atual.");
      return validateMunicipalityDetail(
        await fetchRevenueForContext(detailRequest, signal),
        detailRequest,
      );
    },
    staleTime: 30_000,
    retry: false,
  });
  const currentSummary = useMemo(
    () =>
      currentMapSummary(publicationStale, summary.isError, summary.data) ??
      null,
    [publicationStale, summary.data, summary.isError],
  );

  return {
    catalog,
    parsed,
    request,
    summary,
    detail,
    selected,
    detailRequest,
    mapped: currentSummary?.mapped ?? null,
    summaryEnvelope: currentSummary?.envelope,
    detailEnvelope:
      publicationStale || detail.isError ? undefined : detail.data,
    publicationStale,
    publicationRevision,
  };
}
