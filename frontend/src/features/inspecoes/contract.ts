export type QueueItem = {
  uc_id: string;
  municipality: string;
  neighborhood: string;
  class_name: string;
  feeder_id: string;
  priority: number | null;
  priority_label?: string | null;
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
    neighborhoods: { municipio: string; bairro: string }[];
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
      horizon_months: number | null;
      reference: string;
      unavailable_reason: string | null;
    };
    historical_recovery: {
      mean_kwh_per_inspection: number;
      lower_kwh_per_inspection: number;
      upper_kwh_per_inspection: number;
      reference: string;
    } | null;
    consumption_comparison: {
      baseline_start: string;
      baseline_end: string;
      recent_start: string;
      recent_end: string;
      baseline_kwh: number | null;
      recent_kwh: number | null;
      change_percent: number | null;
      unavailable_reason: string | null;
    } | null;
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
  const priority = nullable(row.priority);
  const priority_label =
    row.priority_label == null ? null : string(row.priority_label);
  if (
    (priority !== null && priority > 1) ||
    (priority === null && !priority_label?.trim())
  )
    invalid();
  if (!Array.isArray(row.signals)) invalid();
  return {
    uc_id: string(row.uc_id),
    municipality: string(row.municipality),
    neighborhood: string(row.neighborhood),
    class_name: string(row.class_name),
    feeder_id: string(row.feeder_id),
    priority,
    priority_label,
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
    !["1.0.0", "1.1.0"].includes(String(row.contract_version)) ||
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
  const neighborhoods =
    data.neighborhoods === undefined
      ? []
      : Array.isArray(data.neighborhoods)
        ? data.neighborhoods.map((value) => {
            const item = record(value);
            return {
              municipio: string(item.municipio),
              bairro: string(item.bairro),
            };
          })
        : invalid();
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
    (metadata(root.metadata).source.kind !== "gold_csv" &&
      (total === 0) !== (summary.highest_priority === null)) ||
    (summary.highest_priority !== null && summary.highest_priority > 1)
  )
    invalid();
  return {
    data: { items, filter_options, neighborhoods, summary },
    pagination: { page, page_size, total, total_pages },
    metadata: metadata(root.metadata),
  };
}
export function decodeDetail(value: unknown): DetailEnvelope {
  const root = record(value),
    data = record(root.data),
    evidence = record(data.estimate_evidence);
  const horizon = nullable(evidence.horizon_months);
  if (horizon !== null && (!Number.isSafeInteger(horizon) || horizon < 1))
    invalid();
  const historical =
    data.historical_recovery == null ? null : record(data.historical_recovery);
  const recovery = historical
    ? {
        mean_kwh_per_inspection: number(historical.mean_kwh_per_inspection),
        lower_kwh_per_inspection: number(historical.lower_kwh_per_inspection),
        upper_kwh_per_inspection: number(historical.upper_kwh_per_inspection),
        reference: string(historical.reference),
      }
    : null;
  if (
    recovery &&
    (recovery.lower_kwh_per_inspection > recovery.upper_kwh_per_inspection ||
      !["global", "0", "1"].includes(recovery.reference))
  )
    invalid();
  const comparison =
    data.consumption_comparison == null
      ? null
      : record(data.consumption_comparison);
  const percent = comparison?.change_percent;
  if (
    percent != null &&
    (typeof percent !== "number" || !Number.isFinite(percent))
  )
    invalid();
  return {
    data: {
      ...item(data),
      rule_version: string(data.rule_version),
      historical_recovery: recovery,
      consumption_comparison: comparison
        ? {
            baseline_start: string(comparison.baseline_start),
            baseline_end: string(comparison.baseline_end),
            recent_start: string(comparison.recent_start),
            recent_end: string(comparison.recent_end),
            baseline_kwh: nullable(comparison.baseline_kwh),
            recent_kwh: nullable(comparison.recent_kwh),
            change_percent: percent as number | null,
            unavailable_reason:
              comparison.unavailable_reason === null
                ? null
                : string(comparison.unavailable_reason),
          }
        : null,
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
