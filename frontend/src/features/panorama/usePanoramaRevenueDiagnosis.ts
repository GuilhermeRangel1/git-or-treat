import { useQuery } from "@tanstack/react-query";
import { useGoldPublicationKey } from "@/shared/analytics/goldPublication";
import { fetchRevenueForContext } from "@/shared/analytics/revenueClient";

type PanoramaRevenueDiagnosisScope = {
  municipio: string;
  classe: string;
  latestPeriod: string;
};

/**
 * O diagnóstico usa as janelas da publicação, não a competência da requisição.
 * Por isso a competência fica fora da chave: trocar o mês não refaz a consulta.
 */
export function usePanoramaRevenueDiagnosis({
  municipio,
  classe,
  latestPeriod,
}: PanoramaRevenueDiagnosisScope) {
  const publication = useGoldPublicationKey();
  const municipioFilter = municipio === "todos" ? "" : municipio;
  const classeFilter = classe === "todas" ? "" : classe;
  return useQuery({
    queryKey: [
      "panorama-revenue-diagnosis",
      publication,
      municipioFilter,
      classeFilter,
    ],
    staleTime: 30_000,
    queryFn: async ({ signal }) => {
      const { data } = await fetchRevenueForContext(
        {
          competencia_inicio: latestPeriod,
          competencia_fim: latestPeriod,
          municipio: municipioFilter,
          classe: classeFilter,
          group_by: "municipio",
          include_diagnosis: true,
        },
        signal,
      );
      return {
        diagnosis: data.diagnosis ?? null,
        window: data.window_decomposition,
      };
    },
  });
}
