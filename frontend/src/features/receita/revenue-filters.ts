export type RevenueGroupBy = "municipio" | "bairro" | "classe";

export type RevenueBaseFilters = {
  competencia_inicio: string;
  competencia_fim: string;
  municipio: string;
  bairro: string;
  classe: string;
  alimentador: string;
};

export type RevenueRefinements = {
  municipio: string;
  bairro: string;
  classe: string;
};

export type RevenueQuery = RevenueBaseFilters & {
  group_by: RevenueGroupBy;
};

export type ParsedRevenueUrl = {
  base: RevenueBaseFilters;
  refinements: RevenueRefinements;
  groupBy: RevenueGroupBy;
  query: RevenueQuery | null;
  errors: string[];
};

export const defaultRevenueFilters: RevenueBaseFilters = {
  competencia_inicio: "2025-01",
  competencia_fim: "2025-02",
  municipio: "",
  bairro: "",
  classe: "",
  alimentador: "",
};

const filterLabels: Record<keyof RevenueBaseFilters, string> = {
  competencia_inicio: "Mês inicial",
  competencia_fim: "Mês final",
  municipio: "Município",
  bairro: "Bairro",
  classe: "Classe",
  alimentador: "Alimentador",
};

function validMonth(value: string) {
  return /^(?!0000)\d{4}-(0[1-9]|1[0-2])$/.test(value);
}

function readScalar(params: URLSearchParams, key: string, errors: string[]) {
  const values = params.getAll(key);
  if (values.length === 1 && !values[0].trim()) {
    errors.push(`${key} não pode estar vazio no link.`);
  }
  return values.length === 1 ? values[0].trim() : "";
}

function mergeFilter(
  base: string,
  refinement: string,
  label: string,
  errors: string[],
) {
  if (base && refinement && base !== refinement) {
    errors.push(`${label} do recorte não pode contradizer o filtro aplicado.`);
    return "";
  }
  return refinement || base;
}

export function parseRevenueSearchParams(
  params: URLSearchParams,
): ParsedRevenueUrl {
  const errors: string[] = [];
  const seen = new Set<string>();
  const reported = new Set<string>();
  for (const key of params.keys()) {
    if (seen.has(key) && !reported.has(key)) {
      errors.push(`${key} deve aparecer apenas uma vez no link.`);
      reported.add(key);
    }
    seen.add(key);
  }
  const values = Object.fromEntries(
    [
      ...Object.keys(defaultRevenueFilters),
      "agrupar_por",
      "recorte_municipio",
      "recorte_bairro",
      "recorte_classe",
    ].map((key) => [key, readScalar(params, key, errors)]),
  ) as Record<string, string>;

  const base: RevenueBaseFilters = {
    competencia_inicio:
      values.competencia_inicio || defaultRevenueFilters.competencia_inicio,
    competencia_fim:
      values.competencia_fim || defaultRevenueFilters.competencia_fim,
    municipio: values.municipio,
    bairro: values.bairro,
    classe: values.classe,
    alimentador: values.alimentador,
  };
  if (!validMonth(base.competencia_inicio)) {
    errors.push("Mês inicial inválido. Escolha um mês e ano válidos.");
  }
  if (!validMonth(base.competencia_fim)) {
    errors.push("Mês final inválido. Escolha um mês e ano válidos.");
  }
  if (
    validMonth(base.competencia_inicio) &&
    validMonth(base.competencia_fim) &&
    base.competencia_inicio > base.competencia_fim
  ) {
    errors.push("Mês final deve ser igual ou posterior ao mês inicial.");
  }
  for (const field of [
    "municipio",
    "bairro",
    "classe",
    "alimentador",
  ] as const) {
    if (Array.from(base[field]).length > 100) {
      errors.push(`${filterLabels[field]} deve ter no máximo 100 caracteres.`);
    }
  }

  const rawGroupBy = values.agrupar_por || "municipio";
  const groupBy: RevenueGroupBy =
    rawGroupBy === "bairro" || rawGroupBy === "classe"
      ? rawGroupBy
      : "municipio";
  if (!(["municipio", "bairro", "classe"] as string[]).includes(rawGroupBy)) {
    errors.push("Agrupamento deve ser município, bairro ou classe.");
  }

  const refinements: RevenueRefinements = {
    municipio: values.recorte_municipio,
    bairro: values.recorte_bairro,
    classe: values.recorte_classe,
  };
  for (const [field, value] of Object.entries(refinements)) {
    if (Array.from(value).length > 100) {
      errors.push(`Recorte de ${field} deve ter no máximo 100 caracteres.`);
    }
  }
  const municipality = mergeFilter(
    base.municipio,
    refinements.municipio,
    "Município",
    errors,
  );
  const neighborhood = mergeFilter(
    base.bairro,
    refinements.bairro,
    "Bairro",
    errors,
  );
  const className = mergeFilter(
    base.classe,
    refinements.classe,
    "Classe",
    errors,
  );
  if (refinements.bairro && refinements.municipio && !municipality) {
    errors.push("O recorte de bairro precisa manter o município.");
  }

  return {
    base,
    refinements,
    groupBy,
    query:
      errors.length === 0
        ? {
            competencia_inicio: base.competencia_inicio,
            competencia_fim: base.competencia_fim,
            municipio: municipality,
            bairro: neighborhood,
            classe: className,
            alimentador: base.alimentador,
            group_by: groupBy,
          }
        : null,
    errors,
  };
}

export function revenueRequestParams(query: RevenueQuery): URLSearchParams {
  const params = new URLSearchParams({
    competencia_inicio: query.competencia_inicio,
    competencia_fim: query.competencia_fim,
    group_by: query.group_by,
  });
  for (const key of ["municipio", "bairro", "classe", "alimentador"] as const) {
    if (query[key]) params.set(key, query[key]);
  }
  return params;
}

export function updateRevenueBaseParams(
  current: URLSearchParams,
  filters: RevenueBaseFilters,
): URLSearchParams {
  const next = new URLSearchParams(current);
  const seen = new Set<string>();
  const repeated = new Set<string>();
  for (const key of next.keys()) {
    if (seen.has(key)) repeated.add(key);
    seen.add(key);
  }
  for (const key of repeated) next.delete(key);

  for (const key of ["recorte_municipio", "recorte_bairro", "recorte_classe"]) {
    next.delete(key);
  }
  for (const key of Object.keys(defaultRevenueFilters) as Array<
    keyof RevenueBaseFilters
  >) {
    next.delete(key);
    if (filters[key]) next.set(key, filters[key]);
  }
  return next;
}

export function updateRevenueGroupBy(
  current: URLSearchParams,
  groupBy: RevenueGroupBy,
) {
  const next = new URLSearchParams(current);
  next.set("agrupar_por", groupBy);
  return next;
}

export function revenueRefinementDestination(
  current: URLSearchParams,
  destination: "total" | "municipio" | "bairro",
) {
  const next = new URLSearchParams(current);
  if (destination === "total") {
    next.delete("recorte_municipio");
    next.delete("recorte_bairro");
    next.delete("recorte_classe");
  } else if (destination === "municipio") {
    next.delete("recorte_bairro");
    next.delete("recorte_classe");
  } else {
    next.delete("recorte_classe");
  }
  return next;
}

export function refineRevenueParams(
  current: URLSearchParams,
  dimension: RevenueGroupBy,
  filters: {
    municipio: string | null;
    bairro: string | null;
    classe: string | null;
  },
) {
  const next = new URLSearchParams(current);
  if (dimension === "municipio" && filters.municipio) {
    next.set("recorte_municipio", filters.municipio);
    next.delete("recorte_bairro");
    next.set("agrupar_por", "bairro");
  } else if (dimension === "bairro" && filters.municipio && filters.bairro) {
    next.set("recorte_municipio", filters.municipio);
    next.set("recorte_bairro", filters.bairro);
    next.set("agrupar_por", "classe");
  } else if (dimension === "classe" && filters.classe) {
    next.set("recorte_classe", filters.classe);
  }
  return next;
}
