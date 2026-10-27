export type OperationStatus = "available" | "empty" | "partial" | "unavailable";
export type OperationMetric = "dec" | "fec";
export type OperationPeriod = {
  start: string;
  end: string;
  granularity: "month";
};
export type OperationMetadata = {
  contract_version: "1.1.0" | "1.2.0";
  status: OperationStatus;
  period: OperationPeriod;
  filters: {
    municipio: string | null;
    bairro: string | null;
    classe: string | null;
    alimentador: string | null;
  };
  source: {
    kind: string;
    version: string;
    is_demo: boolean;
    updated_at: string;
  };
  limitations: string[];
};
export type OperationDefinition = {
  reference: string;
  label: string;
  dec_formula: string;
  fec_formula: string;
  dec_unit: string;
  fec_unit: string;
  event_grain: string;
  population: string;
  rounding: string;
};
export type OperationSummaryDefinition = OperationDefinition & {
  inclusion_rule: string;
};
export type OperationSummary = {
  period: OperationPeriod;
  observed_period: OperationPeriod | null;
  dec_hours_per_uc: number | null;
  fec_interruptions_per_uc: number | null;
  duration_hours_sum: number | null;
  interruption_count: number | null;
  denominator_uc_count: number | null;
  served_uc_count: number;
  included_uc_count: number;
  included_feeder_ids: string[];
  excluded_feeder_ids: string[];
  status: OperationStatus;
  limitations: string[];
  text_alternative: string;
};
export type OperationSummaryEnvelope = {
  data: { summary: OperationSummary; definition: OperationSummaryDefinition };
  metadata: OperationMetadata & { contract_version: "1.2.0" };
};
export type OperationPoint = {
  feeder_id: string;
  municipalities: string[];
  territory_status: "single_municipality" | "multi_municipal";
  dec_hours_per_uc: number | null;
  fec_interruptions_per_uc: number | null;
  interruption_count: number;
  denominator_uc_count: number | null;
  covered_uc_count: number;
  coverage_ratio: number | null;
  served_uc_count: number;
  coverage_status: OperationStatus;
  status: OperationStatus;
  limitations: string[];
  period: OperationPeriod;
  observed_period: OperationPeriod | null;
  duration_hours_sum: number;
  text_alternative: string;
};
export type RankedOperationPoint = OperationPoint & { rank: number };
export type OperationRankingEnvelope = {
  data: {
    items: RankedOperationPoint[];
    excluded: OperationPoint[];
    metric: OperationMetric;
    order: string;
    definition: OperationDefinition;
  };
  metadata: OperationMetadata & { contract_version: "1.1.0" };
};
export type OperationOccurrence = {
  event_id: string;
  uc_id: string;
  feeder_id: string;
  competencia: string;
  duration_hours: number;
};
export type OperationDetailEnvelope = {
  data: {
    summary: OperationPoint;
    series: OperationPoint[];
    occurrences: OperationOccurrence[];
    definition: OperationDefinition;
  };
  pagination: {
    page: number;
    page_size: number;
    total: number;
    total_pages: number;
  };
  metadata: OperationMetadata & { contract_version: "1.1.0" };
};

export class OperationContractError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "OperationContractError";
  }
}

type Obj = Record<string, unknown>;
function object(value: unknown, path: string): Obj {
  if (typeof value !== "object" || value === null || Array.isArray(value))
    throw new OperationContractError(`${path} deve ser um objeto.`);
  return value as Obj;
}
function string(value: unknown, path: string): string {
  if (typeof value !== "string")
    throw new OperationContractError(`${path} deve ser texto.`);
  return value;
}
function nonEmptyString(value: unknown, path: string): string {
  const parsed = string(value, path);
  if (!parsed.trim())
    throw new OperationContractError(`${path} não pode ser vazio.`);
  return parsed;
}
function month(value: unknown, path: string): string {
  const parsed = string(value, path);
  if (!/^(?!0000)\d{4}-(0[1-9]|1[0-2])$/.test(parsed))
    throw new OperationContractError(`${path} deve conter mês e ano válidos.`);
  return parsed;
}
function number(value: unknown, path: string): number {
  if (typeof value !== "number" || !Number.isFinite(value))
    throw new OperationContractError(`${path} deve ser um número finito.`);
  return value;
}
function integer(value: unknown, path: string, minimum = 0): number {
  const parsed = number(value, path);
  if (!Number.isInteger(parsed) || parsed < minimum)
    throw new OperationContractError(`${path} deve ser inteiro >= ${minimum}.`);
  return parsed;
}
function nullableNumber(value: unknown, path: string): number | null {
  return value === null ? null : number(value, path);
}
function nullableInteger(
  value: unknown,
  path: string,
  minimum = 0,
): number | null {
  return value === null ? null : integer(value, path, minimum);
}
function strings(value: unknown, path: string): string[] {
  if (!Array.isArray(value))
    throw new OperationContractError(`${path} deve ser uma lista.`);
  return value.map((entry, index) => string(entry, `${path}[${index}]`));
}
function status(value: unknown, path: string): OperationStatus {
  if (
    value !== "available" &&
    value !== "empty" &&
    value !== "partial" &&
    value !== "unavailable"
  )
    throw new OperationContractError(`${path} contém estado inválido.`);
  return value;
}
function period(value: unknown, path: string): OperationPeriod {
  const input = object(value, path);
  const start = month(input.start, `${path}.start`);
  const end = month(input.end, `${path}.end`);
  if (start > end || input.granularity !== "month")
    throw new OperationContractError(`${path} inválido.`);
  return { start, end, granularity: "month" };
}
function definition(value: unknown, path: string): OperationDefinition {
  const input = object(value, path);
  return {
    reference: string(input.reference, `${path}.reference`),
    label: string(input.label, `${path}.label`),
    dec_formula: string(input.dec_formula, `${path}.dec_formula`),
    fec_formula: string(input.fec_formula, `${path}.fec_formula`),
    dec_unit: string(input.dec_unit, `${path}.dec_unit`),
    fec_unit: string(input.fec_unit, `${path}.fec_unit`),
    event_grain: string(input.event_grain, `${path}.event_grain`),
    population: string(input.population, `${path}.population`),
    rounding: string(input.rounding, `${path}.rounding`),
  };
}
function metadata(
  value: unknown,
  version: "1.1.0" | "1.2.0",
): OperationMetadata {
  const input = object(value, "metadata");
  if (input.contract_version !== version)
    throw new OperationContractError(
      `metadata.contract_version deve ser ${version}.`,
    );
  const filters = object(input.filters, "metadata.filters");
  const nullableFilter = (
    key: "municipio" | "bairro" | "classe" | "alimentador",
  ) => {
    const entry = filters[key];
    if (entry === null) return null;
    return nonEmptyString(entry, `metadata.filters.${key}`);
  };
  const source = object(input.source, "metadata.source");
  if (typeof source.is_demo !== "boolean")
    throw new OperationContractError(
      "metadata.source.is_demo deve ser booleano.",
    );
  const updatedAt = string(source.updated_at, "metadata.source.updated_at");
  if (
    !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(
      updatedAt,
    ) ||
    !Number.isFinite(Date.parse(updatedAt))
  )
    throw new OperationContractError(
      "metadata.source.updated_at deve ser data ISO válida.",
    );
  return {
    contract_version: version,
    status: status(input.status, "metadata.status"),
    period: period(input.period, "metadata.period"),
    filters: {
      municipio: nullableFilter("municipio"),
      bairro: nullableFilter("bairro"),
      classe: nullableFilter("classe"),
      alimentador: nullableFilter("alimentador"),
    },
    source: {
      kind: string(source.kind, "metadata.source.kind"),
      version: string(source.version, "metadata.source.version"),
      is_demo: source.is_demo,
      updated_at: updatedAt,
    },
    limitations: strings(input.limitations, "metadata.limitations"),
  };
}
function summary(value: unknown): OperationSummary {
  const input = object(value, "data.summary");
  const parsedStatus = status(input.status, "data.summary.status");
  const result: OperationSummary = {
    period: period(input.period, "data.summary.period"),
    observed_period:
      input.observed_period === null
        ? null
        : period(input.observed_period, "data.summary.observed_period"),
    dec_hours_per_uc: nullableNumber(
      input.dec_hours_per_uc,
      "data.summary.dec_hours_per_uc",
    ),
    fec_interruptions_per_uc: nullableNumber(
      input.fec_interruptions_per_uc,
      "data.summary.fec_interruptions_per_uc",
    ),
    duration_hours_sum: nullableNumber(
      input.duration_hours_sum,
      "data.summary.duration_hours_sum",
    ),
    interruption_count: nullableInteger(
      input.interruption_count,
      "data.summary.interruption_count",
    ),
    denominator_uc_count: nullableInteger(
      input.denominator_uc_count,
      "data.summary.denominator_uc_count",
    ),
    served_uc_count: integer(
      input.served_uc_count,
      "data.summary.served_uc_count",
    ),
    included_uc_count: integer(
      input.included_uc_count,
      "data.summary.included_uc_count",
    ),
    included_feeder_ids: strings(
      input.included_feeder_ids,
      "data.summary.included_feeder_ids",
    ),
    excluded_feeder_ids: strings(
      input.excluded_feeder_ids,
      "data.summary.excluded_feeder_ids",
    ),
    status: parsedStatus,
    limitations: strings(input.limitations, "data.summary.limitations"),
    text_alternative: string(
      input.text_alternative,
      "data.summary.text_alternative",
    ),
  };
  const hasTotals =
    result.dec_hours_per_uc !== null &&
    result.fec_interruptions_per_uc !== null &&
    result.duration_hours_sum !== null &&
    result.interruption_count !== null &&
    result.denominator_uc_count !== null &&
    result.denominator_uc_count > 0;
  const totalFields = [
    result.dec_hours_per_uc,
    result.fec_interruptions_per_uc,
    result.duration_hours_sum,
    result.interruption_count,
    result.denominator_uc_count,
  ];
  const hasAnyTotal = totalFields.some((entry) => entry !== null);
  if (hasAnyTotal && totalFields.some((entry) => entry === null))
    throw new OperationContractError(
      "data.summary must provide all totals together or all as null.",
    );
  if (
    (parsedStatus === "available" || parsedStatus === "partial") !== hasTotals
  )
    throw new OperationContractError(
      "data.summary possui numeradores/indicadores/denominador incompatíveis com o estado ou denominador inválido.",
    );
  if (parsedStatus === "available" && result.excluded_feeder_ids.length > 0)
    throw new OperationContractError(
      "data.summary available não pode conter alimentadores excluídos.",
    );
  if (parsedStatus === "partial" && result.excluded_feeder_ids.length === 0)
    throw new OperationContractError(
      "data.summary partial deve identificar exclusões.",
    );
  if (
    (parsedStatus === "available" || parsedStatus === "partial") &&
    result.included_feeder_ids.length === 0
  )
    throw new OperationContractError(
      "data.summary with values must identify included feeders.",
    );
  if (
    new Set(result.included_feeder_ids).size !==
      result.included_feeder_ids.length ||
    new Set(result.excluded_feeder_ids).size !==
      result.excluded_feeder_ids.length ||
    result.included_feeder_ids.some((id) =>
      result.excluded_feeder_ids.includes(id),
    )
  )
    throw new OperationContractError(
      "data.summary feeder ID lists must be unique and disjoint.",
    );
  if (
    (parsedStatus === "empty" || parsedStatus === "unavailable") &&
    result.included_feeder_ids.length > 0
  )
    throw new OperationContractError(
      "data.summary sem consolidação não pode indicar alimentadores incluídos.",
    );
  return result;
}
function point(value: unknown, path: string): OperationPoint {
  const input = object(value, path);
  const parsedStatus = status(input.status, `${path}.status`);
  const coverageStatus = status(
    input.coverage_status,
    `${path}.coverage_status`,
  );
  const result: OperationPoint = {
    feeder_id: nonEmptyString(input.feeder_id, `${path}.feeder_id`),
    municipalities: strings(input.municipalities, `${path}.municipalities`),
    territory_status:
      input.territory_status === "single_municipality" ||
      input.territory_status === "multi_municipal"
        ? input.territory_status
        : (() => {
            throw new OperationContractError(
              `${path}.territory_status inválido.`,
            );
          })(),
    dec_hours_per_uc: nullableNumber(
      input.dec_hours_per_uc,
      `${path}.dec_hours_per_uc`,
    ),
    fec_interruptions_per_uc: nullableNumber(
      input.fec_interruptions_per_uc,
      `${path}.fec_interruptions_per_uc`,
    ),
    interruption_count: integer(
      input.interruption_count,
      `${path}.interruption_count`,
    ),
    denominator_uc_count: nullableInteger(
      input.denominator_uc_count,
      `${path}.denominator_uc_count`,
      -Number.MAX_SAFE_INTEGER,
    ),
    covered_uc_count: integer(
      input.covered_uc_count,
      `${path}.covered_uc_count`,
    ),
    coverage_ratio: nullableNumber(
      input.coverage_ratio,
      `${path}.coverage_ratio`,
    ),
    served_uc_count: integer(input.served_uc_count, `${path}.served_uc_count`),
    coverage_status: coverageStatus,
    status: parsedStatus,
    limitations: strings(input.limitations, `${path}.limitations`),
    period: period(input.period, `${path}.period`),
    observed_period:
      input.observed_period === null
        ? null
        : period(input.observed_period, `${path}.observed_period`),
    duration_hours_sum: number(
      input.duration_hours_sum,
      `${path}.duration_hours_sum`,
    ),
    text_alternative: string(
      input.text_alternative,
      `${path}.text_alternative`,
    ),
  };
  if (
    parsedStatus === "available" &&
    (result.dec_hours_per_uc === null ||
      result.fec_interruptions_per_uc === null ||
      result.denominator_uc_count === null ||
      result.denominator_uc_count <= 0 ||
      coverageStatus !== "available")
  )
    throw new OperationContractError(
      `${path} available exige indicadores, denominador positivo e cobertura available.`,
    );
  if (
    parsedStatus === "unavailable" &&
    (result.dec_hours_per_uc !== null ||
      result.fec_interruptions_per_uc !== null)
  )
    throw new OperationContractError(
      `${path} indisponível não pode publicar indicadores.`,
    );
  return result;
}
function checkContext(
  meta: OperationMetadata,
  expected?: { start?: string; end?: string; feederId?: string | null },
): void {
  if (!expected) return;
  if (
    (expected.start && meta.period.start !== expected.start) ||
    (expected.end && meta.period.end !== expected.end)
  )
    throw new OperationContractError(
      "metadata.period não corresponde ao recorte solicitado.",
    );
  if (
    expected.feederId !== undefined &&
    meta.filters.alimentador !== expected.feederId
  )
    throw new OperationContractError(
      "metadata.filters.alimentador não corresponde ao filtro solicitado.",
    );
}

export function decodeOperationSummary(
  input: unknown,
  expected?: { start?: string; end?: string; feederId?: string | null },
): OperationSummaryEnvelope {
  const root = object(input, "resposta");
  const data = object(root.data, "data");
  const meta = metadata(root.metadata, "1.2.0");
  const parsedSummary = summary(data.summary);
  if (meta.status !== parsedSummary.status)
    throw new OperationContractError(
      "metadata.status deve corresponder a data.summary.status.",
    );
  if (
    meta.period.start !== parsedSummary.period.start ||
    meta.period.end !== parsedSummary.period.end
  )
    throw new OperationContractError(
      "metadata.period deve corresponder a data.summary.period.",
    );
  const def = object(data.definition, "data.definition");
  checkContext(meta, expected);
  return {
    data: {
      summary: parsedSummary,
      definition: {
        ...definition(def, "data.definition"),
        inclusion_rule: string(
          def.inclusion_rule,
          "data.definition.inclusion_rule",
        ),
      },
    },
    metadata: meta as OperationSummaryEnvelope["metadata"],
  };
}
export function decodeOperationRanking(
  input: unknown,
  expectedMetric?: OperationMetric,
  expected?: { start?: string; end?: string; feederId?: string | null },
): OperationRankingEnvelope {
  const root = object(input, "resposta");
  const data = object(root.data, "data");
  const meta = metadata(root.metadata, "1.1.0");
  if (!Array.isArray(data.items) || !Array.isArray(data.excluded))
    throw new OperationContractError(
      "data.items e data.excluded devem ser listas.",
    );
  if (data.metric !== "dec" && data.metric !== "fec")
    throw new OperationContractError("data.metric inválida.");
  if (expectedMetric && expectedMetric !== data.metric)
    throw new OperationContractError(
      "métrica da resposta não corresponde à solicitada.",
    );
  const items = data.items.map((entry, index) => {
    const item = object(entry, `data.items[${index}]`);
    return {
      ...point(item, `data.items[${index}]`),
      rank: integer(item.rank, `data.items[${index}].rank`, 1),
    };
  });
  const excluded = data.excluded.map((entry, index) =>
    point(entry, `data.excluded[${index}]`),
  );
  if (items.some((item) => item.status !== "available"))
    throw new OperationContractError(
      "data.items may only contain available feeders.",
    );
  if (excluded.some((item) => item.status === "available"))
    throw new OperationContractError(
      "data.excluded cannot contain available feeders.",
    );
  const ranks = items.map((item) => item.rank);
  if (new Set(ranks).size !== ranks.length)
    throw new OperationContractError("data.items.rank não pode se repetir.");
  checkContext(meta, expected);
  return {
    data: {
      items,
      excluded,
      metric: data.metric,
      order: string(data.order, "data.order"),
      definition: definition(data.definition, "data.definition"),
    },
    metadata: meta as OperationRankingEnvelope["metadata"],
  };
}
export function decodeOperationDetail(
  input: unknown,
  expected?: {
    start?: string;
    end?: string;
    feederId?: string;
    page?: number;
    pageSize?: number;
  },
): OperationDetailEnvelope {
  const root = object(input, "resposta");
  const data = object(root.data, "data");
  const meta = metadata(root.metadata, "1.1.0");
  const parsedSummary = point(data.summary, "data.summary");
  if (!Array.isArray(data.series) || !Array.isArray(data.occurrences))
    throw new OperationContractError(
      "data.series e data.occurrences devem ser listas.",
    );
  const series = data.series.map((entry, index) =>
    point(entry, `data.series[${index}]`),
  );
  const occurrences = data.occurrences.map((entry, index) => {
    const path = `data.occurrences[${index}]`;
    const row = object(entry, path);
    const duration = number(row.duration_hours, `${path}.duration_hours`);
    if (duration < 0)
      throw new OperationContractError(
        `${path}.duration_hours não pode ser negativo.`,
      );
    return {
      event_id: nonEmptyString(row.event_id, `${path}.event_id`),
      uc_id: nonEmptyString(row.uc_id, `${path}.uc_id`),
      feeder_id: nonEmptyString(row.feeder_id, `${path}.feeder_id`),
      competencia: month(row.competencia, `${path}.competencia`),
      duration_hours: duration,
    };
  });
  if (occurrences.some((row) => row.feeder_id !== parsedSummary.feeder_id))
    throw new OperationContractError(
      "ocorrência pertence a outro alimentador.",
    );
  const pagination = object(root.pagination, "pagination");
  const page = integer(pagination.page, "pagination.page", 1);
  const pageSize = integer(pagination.page_size, "pagination.page_size", 1);
  const total = integer(pagination.total, "pagination.total");
  const totalPages = integer(pagination.total_pages, "pagination.total_pages");
  if (
    page > 1_000_000 ||
    pageSize > 100 ||
    (total === 0
      ? totalPages !== 0
      : totalPages !== Math.ceil(total / pageSize))
  )
    throw new OperationContractError(
      "pagination contém valores incompatíveis.",
    );
  if (
    expected &&
    ((expected.feederId && parsedSummary.feeder_id !== expected.feederId) ||
      (expected.page !== undefined && page !== expected.page) ||
      (expected.pageSize !== undefined && pageSize !== expected.pageSize))
  )
    throw new OperationContractError(
      "detalhe ou paginação não correspondem ao pedido.",
    );
  checkContext(meta, expected);
  if (
    parsedSummary.period.start !== meta.period.start ||
    parsedSummary.period.end !== meta.period.end
  )
    throw new OperationContractError(
      "detail summary period must match metadata.period.",
    );
  for (const [index, item] of series.entries()) {
    if (item.feeder_id !== parsedSummary.feeder_id)
      throw new OperationContractError(
        `data.series[${index}] belongs to another feeder.`,
      );
    if (
      item.period.start !== item.period.end ||
      item.period.start < meta.period.start ||
      item.period.end > meta.period.end
    )
      throw new OperationContractError(
        `data.series[${index}].period is outside the requested monthly range.`,
      );
  }
  return {
    data: {
      summary: parsedSummary,
      series,
      occurrences,
      definition: definition(data.definition, "data.definition"),
    },
    pagination: { page, page_size: pageSize, total, total_pages: totalPages },
    metadata: meta as OperationDetailEnvelope["metadata"],
  };
}
