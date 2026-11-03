export type MapLayer =
  "revenue" | "consumption" | "revenue_change" | "consumption_change";

export type MapQuery = {
  competencia_inicio: string;
  competencia_fim: string;
  classe: string;
  municipio: string;
  camada: MapLayer;
};

export type MapDefaults = {
  months: readonly string[];
  classes: readonly string[];
  municipalityCodes: readonly string[];
};

export type ParsedMapUrl = { query: MapQuery | null; errors: string[] };

const layers: readonly MapLayer[] = [
  "revenue",
  "consumption",
  "revenue_change",
  "consumption_change",
];
const monthPattern = /^(?!0000)\d{4}-(0[1-9]|1[0-2])$/;
const keys = [
  "competencia_inicio",
  "competencia_fim",
  "classe",
  "municipio",
  "camada",
] as const;

function value(params: URLSearchParams, key: string, errors: string[]) {
  const values = params.getAll(key);
  if (values.length > 1) errors.push(`${key} deve aparecer apenas uma vez.`);
  return values.length === 1 ? values[0].trim() : "";
}

export function parseMapSearchParams(
  params: URLSearchParams,
  defaults: MapDefaults,
): ParsedMapUrl {
  const errors: string[] = [];
  for (const key of params.keys()) {
    if (!(keys as readonly string[]).includes(key)) {
      errors.push(`Parâmetro desconhecido: ${key}.`);
    }
  }

  const start = value(params, "competencia_inicio", errors);
  const end = value(params, "competencia_fim", errors);
  const className = value(params, "classe", errors);
  const municipality = value(params, "municipio", errors);
  const layerValue = value(params, "camada", errors);
  for (const key of [
    "competencia_inicio",
    "competencia_fim",
    "camada",
  ] as const) {
    if (params.has(key) && params.get(key) === "") {
      errors.push(`${key} não pode estar vazio no link.`);
    }
  }
  const months = [...defaults.months].filter((month) =>
    monthPattern.test(month),
  );
  if (!months.length && (!start || !end)) {
    errors.push("Aguarde o catálogo de competências publicado.");
  }
  const initial = start || months[Math.max(0, months.length - 2)] || "";
  const final = end || months.at(-1) || "";

  if (initial && !monthPattern.test(initial))
    errors.push("Mês inicial inválido.");
  if (final && !monthPattern.test(final)) errors.push("Mês final inválido.");
  if (months.length && start && !months.includes(initial))
    errors.push("Mês inicial não está disponível na publicação atual.");
  if (months.length && end && !months.includes(final))
    errors.push("Mês final não está disponível na publicação atual.");
  if (initial && final && initial > final)
    errors.push("Mês final deve ser igual ou posterior ao mês inicial.");
  if (className && !defaults.classes.includes(className))
    errors.push("Classe não encontrada na publicação atual.");
  if (municipality && !defaults.municipalityCodes.includes(municipality))
    errors.push("Município não encontrado na RMR.");
  const layer = layerValue || "revenue";
  if (!layers.includes(layer as MapLayer)) errors.push("Camada desconhecida.");

  return {
    query:
      errors.length === 0 && initial && final
        ? {
            competencia_inicio: initial,
            competencia_fim: final,
            classe: className,
            municipio: municipality,
            camada: layer as MapLayer,
          }
        : null,
    errors,
  };
}

export function updateMapSearchParams(
  current: URLSearchParams,
  changes: Partial<MapQuery>,
) {
  const next = new URLSearchParams();
  for (const key of keys) {
    const nextValue = changes[key] ?? current.get(key) ?? "";
    if (nextValue) next.set(key, nextValue);
  }
  return next;
}

export function buildRevenueDestination(
  query: MapQuery,
  goldMunicipality: string,
) {
  const params = new URLSearchParams({
    competencia_inicio: query.competencia_inicio,
    competencia_fim: query.competencia_fim,
    agrupar_por: "bairro",
  });
  if (query.classe) params.set("classe", query.classe);
  params.set("municipio", goldMunicipality);
  return `/receita?${params.toString()}`;
}
