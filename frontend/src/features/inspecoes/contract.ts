import {
  decodeGoldMetadata,
  isGoldMetadata,
  type GoldMetadata,
} from "@/shared/analytics/goldContract";

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
export type SyntheticMetadata = {
  contract_version: "1.0.0";
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
export type GoldInspectionVariation = {
  p1_start: string;
  p1_end: string;
  p1_months_observed: number | null;
  p1_average_kwh_per_month: number | null;
  p2_start: string;
  p2_end: string;
  p2_months_observed: number | null;
  p2_average_kwh_per_month: number | null;
  variation_kwh: number | null;
  variation_pct: number | null;
  drop_over_30_pct: boolean | null;
};
export type GoldInspectionItem = {
  queue_position: number;
  uc_id: string;
  municipality: string | null;
  neighborhood: string | null;
  class_name: string | null;
  feeder_id: string | null;
  category: string | null;
  reason: string | null;
  potential_recoverable_energy_kwh: null;
  recovery_unavailable_reason: string;
  evidence: {
    inspections_performed: number | null;
    confirmed_irregular_inspections: number | null;
    historical_average_kwh_per_reading: number | null;
    distributed_generation_present: string | null;
    cadastral_status: string | null;
    call_center_contacts: number | null;
    interruptions: number | null;
    historical_recovery_mean_kwh_per_inspection: number | null;
    historical_recovery_interval_lower_kwh: number | null;
    historical_recovery_interval_upper_kwh: number | null;
    historical_recovery_reference: string | null;
    historical_recovery_status: string | null;
  };
  variation: GoldInspectionVariation | null;
};
export type Metadata = SyntheticMetadata | GoldMetadata;
export type SyntheticQueueEnvelope = {
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
  metadata: SyntheticMetadata;
};
export type GoldQueueEnvelope = {
  data: {
    items: GoldInspectionItem[];
    filter_options: Record<string, string[]>;
    neighborhoods: { municipio: string; bairro: string }[];
    summary: {
      total_units: number;
      categories: Record<string, number>;
      uncategorized_units: number;
      estimated_units: 0;
      unavailable_estimate_units: number;
    };
  };
  pagination: {
    page: number;
    page_size: number;
    total: number;
    total_pages: number;
  };
  metadata: GoldMetadata;
};
export type QueueEnvelope = SyntheticQueueEnvelope | GoldQueueEnvelope;
export type SyntheticDetailEnvelope = {
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
  metadata: SyntheticMetadata;
};
export type GoldDetailEnvelope = {
  data: GoldInspectionItem & {
    rule_version: string;
    limitations: string[];
    consumption_comparison: SyntheticDetailEnvelope["data"]["consumption_comparison"];
  };
  metadata: GoldMetadata;
};
export type DetailEnvelope = SyntheticDetailEnvelope | GoldDetailEnvelope;

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
function nullableSigned(value: unknown): number | null {
  return value === null
    ? null
    : typeof value === "number" && Number.isFinite(value)
      ? value
      : invalid();
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
  if (isGoldMetadata(value)) return decodeGoldMetadata(value);
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
    contract_version: "1.0.0",
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
function nullableText(value: unknown): string | null {
  return value === null ? null : string(value);
}
function nullableCount(value: unknown): number | null {
  if (value === null) return null;
  const result = number(value);
  if (!Number.isSafeInteger(result)) invalid();
  return result;
}
function goldMonth(value: unknown): string {
  const result = string(value);
  if (!/^(?!0000)\d{4}-(0[1-9]|1[0-2])$/.test(result)) invalid();
  return result;
}
function goldVariation(value: unknown): GoldInspectionVariation {
  const row = record(value);
  const months = (candidate: unknown) => {
    const result = nullableCount(candidate);
    if (result !== null && result < 0) invalid();
    return result;
  };
  const average = (candidate: unknown) => {
    const result = nullable(candidate);
    if (result !== null && result < 0) invalid();
    return result;
  };
  if (
    row.drop_over_30_pct !== null &&
    typeof row.drop_over_30_pct !== "boolean"
  )
    invalid();
  const p1_start = goldMonth(row.p1_start);
  const p1_end = goldMonth(row.p1_end);
  const p2_start = goldMonth(row.p2_start);
  const p2_end = goldMonth(row.p2_end);
  if (p1_start > p1_end || p2_start > p2_end) invalid();
  return {
    p1_start,
    p1_end,
    p1_months_observed: months(row.p1_months_observed),
    p1_average_kwh_per_month: average(row.p1_average_kwh_per_month),
    p2_start,
    p2_end,
    p2_months_observed: months(row.p2_months_observed),
    p2_average_kwh_per_month: average(row.p2_average_kwh_per_month),
    variation_kwh: nullableSigned(row.variation_kwh),
    variation_pct: nullableSigned(row.variation_pct),
    drop_over_30_pct: row.drop_over_30_pct as boolean | null,
  };
}
function goldItem(value: unknown): GoldInspectionItem {
  const row = record(value);
  if (row.potential_recoverable_energy_kwh !== null) invalid();
  const queue_position = number(row.queue_position);
  if (!Number.isSafeInteger(queue_position) || queue_position < 1) invalid();
  const evidence = record(row.evidence);
  const nullableNonNegative = (candidate: unknown) => {
    const result = nullable(candidate);
    if (result !== null && result < 0) invalid();
    return result;
  };
  if (
    row.variation !== null &&
    (!row.variation ||
      typeof row.variation !== "object" ||
      Array.isArray(row.variation))
  )
    invalid();
  return {
    queue_position,
    uc_id: string(row.uc_id),
    municipality: nullableText(row.municipality),
    neighborhood: nullableText(row.neighborhood),
    class_name: nullableText(row.class_name),
    feeder_id: nullableText(row.feeder_id),
    category: nullableText(row.category),
    reason: nullableText(row.reason),
    potential_recoverable_energy_kwh: null,
    recovery_unavailable_reason: string(row.recovery_unavailable_reason),
    evidence: {
      inspections_performed: nullableNonNegative(
        evidence.inspections_performed,
      ),
      confirmed_irregular_inspections: nullableNonNegative(
        evidence.confirmed_irregular_inspections,
      ),
      historical_average_kwh_per_reading: nullableNonNegative(
        evidence.historical_average_kwh_per_reading,
      ),
      distributed_generation_present: nullableText(
        evidence.distributed_generation_present,
      ),
      cadastral_status: nullableText(evidence.cadastral_status),
      call_center_contacts: nullableNonNegative(evidence.call_center_contacts),
      interruptions: nullableNonNegative(evidence.interruptions),
      historical_recovery_mean_kwh_per_inspection:
        evidence.historical_recovery_mean_kwh_per_inspection == null
          ? null
          : nullableNonNegative(
              evidence.historical_recovery_mean_kwh_per_inspection,
            ),
      historical_recovery_interval_lower_kwh:
        evidence.historical_recovery_interval_lower_kwh == null
          ? null
          : nullableNonNegative(
              evidence.historical_recovery_interval_lower_kwh,
            ),
      historical_recovery_interval_upper_kwh:
        evidence.historical_recovery_interval_upper_kwh == null
          ? null
          : nullableNonNegative(
              evidence.historical_recovery_interval_upper_kwh,
            ),
      historical_recovery_reference:
        evidence.historical_recovery_reference == null
          ? null
          : string(evidence.historical_recovery_reference),
      historical_recovery_status:
        evidence.historical_recovery_status == null
          ? null
          : string(evidence.historical_recovery_status),
    },
    variation: row.variation === null ? null : goldVariation(row.variation),
  };
}
function goldQueue(value: Record<string, unknown>): GoldQueueEnvelope {
  const data = record(value.data);
  const pagination = record(value.pagination);
  const raw = record(data.summary);
  if (!Array.isArray(data.items)) invalid();
  const options = record(data.filter_options);
  const neighborhoods =
    data.neighborhoods == null
      ? []
      : Array.isArray(data.neighborhoods)
        ? data.neighborhoods.map((value) => {
            const entry = record(value);
            return {
              municipio: string(entry.municipio),
              bairro: string(entry.bairro),
            };
          })
        : invalid();
  const filter_options: Record<string, string[]> = {};
  for (const key of ["municipio", "bairro", "classe", "alimentador"])
    filter_options[key] = strings(options[key]);
  const page = number(pagination.page);
  const page_size = number(pagination.page_size);
  const total = number(pagination.total);
  const total_pages = number(pagination.total_pages);
  const categories = record(raw.categories);
  const categoryCounts: Record<string, number> = {};
  for (const [key, count] of Object.entries(categories)) {
    const parsed = nullableCount(count);
    if (parsed === null || parsed < 0) invalid();
    categoryCounts[key] = parsed;
  }
  const summary = {
    total_units: number(raw.total_units),
    categories: categoryCounts,
    uncategorized_units: number(raw.uncategorized_units),
    estimated_units: number(raw.estimated_units),
    unavailable_estimate_units: number(raw.unavailable_estimate_units),
  };
  if (
    ![page, page_size, total, total_pages].every(Number.isSafeInteger) ||
    page < 1 ||
    page_size < 1 ||
    total !== summary.total_units ||
    total_pages !== Math.ceil(total / page_size) ||
    summary.estimated_units !== 0 ||
    summary.uncategorized_units +
      Object.values(categoryCounts).reduce((sum, count) => sum + count, 0) !==
      total ||
    summary.unavailable_estimate_units !== total ||
    data.items.length > page_size ||
    data.items.length > total
  )
    invalid();
  return {
    data: {
      items: data.items.map(goldItem),
      filter_options,
      neighborhoods,
      summary: { ...summary, estimated_units: 0 },
    },
    pagination: { page, page_size, total, total_pages },
    metadata: decodeGoldMetadata(value.metadata),
  };
}
export function decodeQueue(value: unknown): QueueEnvelope {
  const root = record(value);
  if (isGoldMetadata(root.metadata)) return goldQueue(root);
  return decodeSyntheticQueue(root);
}
function decodeSyntheticQueue(
  root: Record<string, unknown>,
): SyntheticQueueEnvelope {
  const data = record(root.data),
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
    metadata: metadata(root.metadata) as SyntheticMetadata,
  };
}
export function decodeDetail(value: unknown): DetailEnvelope {
  const root = record(value);
  if (isGoldMetadata(root.metadata)) {
    const data = record(root.data);
    return {
      data: {
        ...goldItem(data),
        rule_version: string(data.rule_version),
        limitations: strings(data.limitations),
        consumption_comparison: decodeConsumptionComparison(
          data.consumption_comparison,
        ),
      },
      metadata: decodeGoldMetadata(root.metadata),
    };
  }
  const data = record(root.data),
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
  return {
    data: {
      ...item(data),
      rule_version: string(data.rule_version),
      historical_recovery: recovery,
      consumption_comparison: decodeConsumptionComparison(
        data.consumption_comparison,
      ),
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
    metadata: metadata(root.metadata) as SyntheticMetadata,
  };
}

function decodeConsumptionComparison(
  value: unknown,
): SyntheticDetailEnvelope["data"]["consumption_comparison"] {
  if (value == null) return null;
  const comparison = record(value);
  const percent = comparison.change_percent;
  if (
    percent !== null &&
    (typeof percent !== "number" || !Number.isFinite(percent))
  )
    invalid();
  return {
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
  };
}
