import { useCallback, useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import type { ComparisonType, PanoramaFilters } from "../analytics/types";
import type { PanoramaFilterOptions } from "../analytics/types";
import {
  CLASSES_DISPONIVEIS,
  MUNICIPIOS_DISPONIVEIS,
} from "../analytics/syntheticData";

export const DEFAULT_FILTERS: PanoramaFilters = {
  periodo: "2024-04",
  comparacao: "anterior",
  municipio: "todos",
  classe: "todas",
};

export function usePanoramaFilters(
  options?: PanoramaFilterOptions,
  source?: "gold" | "synthetic",
) {
  const [searchParams, setSearchParams] = useSearchParams();

  const filters = useMemo<PanoramaFilters>(() => {
    const periodo = searchParams.get("periodo") ?? DEFAULT_FILTERS.periodo;
    const comparacaoParam = searchParams.get("comparacao");
    const comparacao = (comparacaoParam ??
      DEFAULT_FILTERS.comparacao) as ComparisonType;
    const municipio =
      searchParams.get("municipio") ?? DEFAULT_FILTERS.municipio;
    const classe = searchParams.get("classe") ?? DEFAULT_FILTERS.classe;

    return {
      periodo,
      comparacao,
      municipio,
      classe,
    };
  }, [searchParams]);

  const errors: Partial<Record<keyof PanoramaFilters, string>> = {};
  if (!/^(?!0000)\d{4}-(0[1-9]|1[0-2])$/.test(filters.periodo))
    errors.periodo = "Informe uma competência real no formato YYYY-MM.";
  if (!["anterior", "ano_anterior", "nenhuma"].includes(filters.comparacao))
    errors.comparacao = "Escolha mês anterior, ano anterior ou sem comparação.";
  const municipioCatalog =
    options?.municipios ?? MUNICIPIOS_DISPONIVEIS.map((item) => item.value);
  const classCatalog =
    options?.classes ?? CLASSES_DISPONIVEIS.map((item) => item.value);
  const deferCatalogValidation = source === undefined;
  const sourceLabel =
    source === "gold" ? "fonte consultada" : "fonte demonstrativa";
  const structurallySafeDimension = (value: string) =>
    value.length <= 120 && /^[\p{L}\p{N} .,()/-]+$/u.test(value.trim());
  if (
    filters.municipio !== "todos" &&
    (deferCatalogValidation
      ? !structurallySafeDimension(filters.municipio)
      : !municipioCatalog.includes(filters.municipio))
  )
    errors.municipio = `Escolha um municipio da ${sourceLabel}.`;
  if (
    filters.classe !== "todas" &&
    (deferCatalogValidation
      ? !structurallySafeDimension(filters.classe)
      : !classCatalog.includes(filters.classe))
  )
    errors.classe = `Escolha uma classe da ${sourceLabel}.`;
  for (const key of Object.keys(filters) as (keyof PanoramaFilters)[]) {
    if (searchParams.getAll(key).length > 1)
      errors[key] = "Use apenas um valor para este filtro na URL.";
  }

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

  const setFilters = useCallback(
    (values: PanoramaFilters) => {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          for (const key of Object.keys(values) as (keyof PanoramaFilters)[]) {
            next.set(key, String(values[key]));
          }
          return next;
        },
        { replace: false },
      );
    },
    [setSearchParams],
  );

  const setBootstrapPeriod = useCallback(
    (period: string) => {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          next.set("periodo", period);
          return next;
        },
        { replace: true },
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
    periodoExplicit: searchParams.has("periodo"),
    needsSourceDiscovery:
      source === undefined &&
      (filters.municipio !== "todos" || filters.classe !== "todas"),
    setFilter,
    setFilters,
    setBootstrapPeriod,
    resetFilters,
    hasActiveFilters,
    errors,
    isValid: Object.keys(errors).length === 0,
  };
}
