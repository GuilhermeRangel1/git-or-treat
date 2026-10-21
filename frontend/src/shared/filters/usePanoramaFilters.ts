import { useCallback, useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import type { ComparisonType, PanoramaFilters } from "../analytics/types";

export const DEFAULT_FILTERS: PanoramaFilters = {
  periodo: "2024-04",
  comparacao: "anterior",
  municipio: "todos",
  classe: "todas",
};

export function usePanoramaFilters() {
  const [searchParams, setSearchParams] = useSearchParams();

  const filters = useMemo<PanoramaFilters>(() => {
    const periodo = searchParams.get("periodo") || DEFAULT_FILTERS.periodo;
    const comparacaoParam = searchParams.get("comparacao");
    const comparacao: ComparisonType =
      comparacaoParam === "anterior" ||
      comparacaoParam === "ano_anterior" ||
      comparacaoParam === "nenhuma"
        ? comparacaoParam
        : DEFAULT_FILTERS.comparacao;
    const municipio =
      searchParams.get("municipio") || DEFAULT_FILTERS.municipio;
    const classe = searchParams.get("classe") || DEFAULT_FILTERS.classe;

    return {
      periodo,
      comparacao,
      municipio,
      classe,
    };
  }, [searchParams]);

  const setFilter = useCallback(
    <K extends keyof PanoramaFilters>(key: K, value: PanoramaFilters[K]) => {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          if (value === DEFAULT_FILTERS[key]) {
            // Pode remover se for o default para URL limpa ou manter explícito
            next.set(key, String(value));
          } else {
            next.set(key, String(value));
          }
          return next;
        },
        { replace: false }, // push para histórico de voltar/avançar funcionar
      );
    },
    [setSearchParams],
  );

  const resetFilters = useCallback(() => {
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.set("periodo", DEFAULT_FILTERS.periodo);
        next.set("comparacao", DEFAULT_FILTERS.comparacao);
        next.set("municipio", DEFAULT_FILTERS.municipio);
        next.set("classe", DEFAULT_FILTERS.classe);
        return next;
      },
      { replace: false },
    );
  }, [setSearchParams]);

  const hasActiveFilters = useMemo(() => {
    return (
      filters.periodo !== DEFAULT_FILTERS.periodo ||
      filters.comparacao !== DEFAULT_FILTERS.comparacao ||
      filters.municipio !== DEFAULT_FILTERS.municipio ||
      filters.classe !== DEFAULT_FILTERS.classe
    );
  }, [filters]);

  return {
    filters,
    setFilter,
    resetFilters,
    hasActiveFilters,
  };
}
