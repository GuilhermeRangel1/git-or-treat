export type QueueItem = {
  uc_id: string;
  municipality: string;
  neighborhood: string;
  class_name: string;
  feeder_id: string;
  priority: number;
  reason: string;
  potential_recoverable_energy_kwh: number | null;
  indicators: string[];
  signals: { id: string; label: string; weight: number }[];
};
export type Metadata = {
  status: string;
  period: { start: string; end: string };
  source: {
    kind: string;
    version: string;
    is_demo: boolean;
    updated_at: string;
  };
  limitations: string[];
};
export type QueueEnvelope = {
  data: {
    items: QueueItem[];
    filter_options: Record<string, string[]>;
    summary: {
      total_units: number;
      highest_priority: number | null;
      estimated_units: number;
      unavailable_estimate_units: number;
    };
  };
  pagination: {
    page: number;
    page_size: number;
    total: number;
    total_pages: number;
  };
  metadata: Metadata;
};
export type DetailEnvelope = {
  data: QueueItem & {
    rule_version: string;
    signals: { id: string; label: string; weight: number }[];
    estimate_evidence: {
      baseline_kwh: number | null;
      observed_kwh: number | null;
      horizon_months: number;
      reference: string;
      unavailable_reason: string | null;
    };
    limitations: string[];
  };
  metadata: Metadata;
};

function record(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) invalid();
  return value as Record<string, unknown>;
}
function invalid(): never {
  throw new Error("Resposta inválida da fila de inspeção.");
}
function string(value: unknown): string {
  return typeof value === "string" ? value : invalid();
}
function number(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) && value >= 0
    ? value
    : invalid();
}
function nullable(value: unknown): number | null {
  return value === null ? null : number(value);
}
function strings(value: unknown): string[] {
  if (!Array.isArray(value)) invalid();
  return value.map(string);
}
function item(value: unknown): QueueItem {
  const row = record(value);
  const priority = number(row.priority);
  if (priority > 1) invalid();
  if (!Array.isArray(row.signals)) invalid();
  return {
    uc_id: string(row.uc_id),
    municipality: string(row.municipality),
    neighborhood: string(row.neighborhood),
    class_name: string(row.class_name),
    feeder_id: string(row.feeder_id),
    priority,
    reason: string(row.reason),
    potential_recoverable_energy_kwh: nullable(
      row.potential_recoverable_energy_kwh,
    ),
    indicators: strings(row.indicators),
    signals: row.signals.map((value) => {
      const signal = record(value),
        weight = number(signal.weight);
      if (weight > 1) invalid();
      return { id: string(signal.id), label: string(signal.label), weight };
    }),
  };
}
function metadata(value: unknown): Metadata {
  const row = record(value),
    period = record(row.period),
    source = record(row.source);
  if (
    row.contract_version !== "1.0.0" ||
    typeof source.is_demo !== "boolean" ||
    !["available", "partial", "empty", "unavailable"].includes(
      string(row.status),
    ) ||
    !Number.isFinite(Date.parse(string(source.updated_at)))
  )
    invalid();
  return {
    status: string(row.status),
    period: { start: string(period.start), end: string(period.end) },
    source: {
      kind: string(source.kind),
      version: string(source.version),
      is_demo: source.is_demo,
      updated_at: string(source.updated_at),
    },
    limitations: strings(row.limitations),
  };
}
export function decodeQueue(value: unknown): QueueEnvelope {
  const root = record(value),
    data = record(root.data),
    pagination = record(root.pagination);
  if (!Array.isArray(data.items)) invalid();
  const options = record(data.filter_options);
  const filter_options: Record<string, string[]> = {};
  for (const key of ["municipio", "bairro", "classe", "alimentador"])
    filter_options[key] = strings(options[key]);
  const page = number(pagination.page),
    page_size = number(pagination.page_size),
    total = number(pagination.total),
    total_pages = number(pagination.total_pages);
  if (
    ![page, page_size, total, total_pages].every(Number.isSafeInteger) ||
    page < 1 ||
    page_size < 1 ||
    total_pages !== Math.ceil(total / page_size)
  )
    invalid();
  const items = data.items.map(item);
  if (items.length > page_size || items.length > total) invalid();
  const rawSummary = record(data.summary);
  const summary = {
    total_units: number(rawSummary.total_units),
    highest_priority: nullable(rawSummary.highest_priority),
    estimated_units: number(rawSummary.estimated_units),
    unavailable_estimate_units: number(rawSummary.unavailable_estimate_units),
  };
  if (
    summary.total_units !== total ||
    ![
      summary.total_units,
      summary.estimated_units,
      summary.unavailable_estimate_units,
    ].every(Number.isSafeInteger) ||
    summary.estimated_units + summary.unavailable_estimate_units !== total ||
    (total === 0) !== (summary.highest_priority === null) ||
    (summary.highest_priority !== null && summary.highest_priority > 1)
  )
    invalid();
  return {
    data: { items, filter_options, summary },
    pagination: { page, page_size, total, total_pages },
    metadata: metadata(root.metadata),
  };
}
export function decodeDetail(value: unknown): DetailEnvelope {
  const root = record(value),
    data = record(root.data),
    evidence = record(data.estimate_evidence);
  const horizon = number(evidence.horizon_months);
  if (!Number.isSafeInteger(horizon) || horizon < 1) invalid();
  return {
    data: {
      ...item(data),
      rule_version: string(data.rule_version),
      estimate_evidence: {
        baseline_kwh: nullable(evidence.baseline_kwh),
        observed_kwh: nullable(evidence.observed_kwh),
        horizon_months: horizon,
        reference: string(evidence.reference),
        unavailable_reason:
          evidence.unavailable_reason === null
            ? null
            : string(evidence.unavailable_reason),
      },
      limitations: strings(data.limitations),
    },
    metadata: metadata(root.metadata),
  };
}
