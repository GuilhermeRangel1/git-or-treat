export type KpisFilters = {
  competencia_inicio: string;
  competencia_fim: string;
  municipio: string;
  classe: string;
};

export type KpisFilterErrors = Partial<Record<keyof KpisFilters, string>>;

export function validateKpisFilters(filters: KpisFilters): KpisFilterErrors {
  const errors: KpisFilterErrors = {};
  const month = /^(?!0000)\d{4}-(0[1-9]|1[0-2])$/;
  if (!month.test(filters.competencia_inicio)) {
    errors.competencia_inicio =
      "Competência inicial deve usar YYYY-MM com mês válido.";
  }
  if (!month.test(filters.competencia_fim)) {
    errors.competencia_fim =
      "Competência final deve usar YYYY-MM com mês válido.";
  }
  if (
    !errors.competencia_inicio &&
    !errors.competencia_fim &&
    filters.competencia_inicio > filters.competencia_fim
  ) {
    errors.competencia_fim =
      "Competência final deve ser igual ou posterior à inicial.";
  }
  if (Array.from(filters.municipio).length > 100) {
    errors.municipio = "Município deve ter no máximo 100 caracteres.";
  }
  if (Array.from(filters.classe).length > 100) {
    errors.classe = "Classe deve ter no máximo 100 caracteres.";
  }
  return errors;
}

export const defaultKpisFilters: KpisFilters = {
  competencia_inicio: "2025-01",
  competencia_fim: "2025-02",
  municipio: "",
  classe: "",
};

export function readKpisFilters(params: URLSearchParams) {
  if (!Object.keys(defaultKpisFilters).some((key) => params.has(key))) {
    return null;
  }
  const filters = {
    competencia_inicio: params.get("competencia_inicio") ?? "2025-01",
    competencia_fim: params.get("competencia_fim") ?? "2025-02",
    municipio: (params.get("municipio") ?? "").trim(),
    classe: (params.get("classe") ?? "").trim(),
  };
  const errors = validateKpisFilters(filters);
  const labels: Record<keyof KpisFilters, string> = {
    competencia_inicio: "Competência inicial",
    competencia_fim: "Competência final",
    municipio: "Município",
    classe: "Classe",
  };
  for (const field of Object.keys(labels) as Array<keyof KpisFilters>) {
    if (params.getAll(field).length > 1) {
      errors[field] = `${labels[field]} deve aparecer apenas uma vez no link.`;
    }
  }
  return { filters, errors };
}

export function kpisSearchParams(filters: KpisFilters): URLSearchParams {
  const params = new URLSearchParams();
  params.set("competencia_inicio", filters.competencia_inicio);
  params.set("competencia_fim", filters.competencia_fim);
  if (filters.municipio) params.set("municipio", filters.municipio);
  if (filters.classe) params.set("classe", filters.classe);
  return params;
}
