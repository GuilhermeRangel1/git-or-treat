import { OperationContractError } from "./contract";
import {
  decodeGoldMetadata,
  type GoldMetadata,
} from "@/shared/analytics/goldContract";

export type GoldOperationPoint = {
  feeder_id: string;
  municipality: string | null;
  period: { start: string; end: string; granularity: "month" };
  observed_period: { start: string; end: string; granularity: "month" } | null;
  observed_competencies: string[];
  missing_competencies: string[];
  duration_hours_sum: number | null;
  interruption_count: number | null;
  denominator_uc_count: number | null;
  dec_hours_per_uc: number | null;
  fec_interruptions_per_uc: number | null;
  status: OperationStatus;
  dec_status: OperationStatus;
  fec_status: OperationStatus;
  limitations: string[];
};

export type OperationStatus = "available" | "empty" | "partial" | "unavailable";
export type GoldOperationSummary = {
  period: GoldOperationPoint["period"];
  observed_period: GoldOperationPoint["observed_period"];
  duration_hours_sum: number | null;
  interruption_count: number | null;
  denominator_uc_count: number | null;
  dec_hours_per_uc: number | null;
  fec_interruptions_per_uc: number | null;
  dec_denominator_uc_count: number | null;
  fec_denominator_uc_count: number | null;
  dec_included_feeder_ids: string[];
  fec_included_feeder_ids: string[];
  dec_excluded_feeder_ids: string[];
  fec_excluded_feeder_ids: string[];
  included_feeder_ids: string[] | null;
  excluded_feeder_ids: string[] | null;
  dec_status: OperationStatus;
  fec_status: OperationStatus;
  status: OperationStatus;
  limitations: string[];
};
export type GoldOperationDefinition = {
  reference: string;
  dec_formula: string;
  fec_formula: string;
  dec_unit: string;
  fec_unit: string;
  event_grain: string;
  population: string;
  completeness: string;
};
export type GoldOperationSummaryEnvelope = {
  data: { summary: GoldOperationSummary; definition: GoldOperationDefinition };
  metadata: GoldMetadata;
};
export type GoldOperationRankingEnvelope = {
  data: {
    items: Array<GoldOperationPoint & { rank: number }>;
    excluded: GoldOperationPoint[];
    metric: "dec" | "fec";
    order: string;
    definition: GoldOperationDefinition;
  };
  metadata: GoldMetadata;
};
export type GoldOperationDetailEnvelope = {
  data: {
    summary: GoldOperationPoint;
    series: GoldOperationPoint[];
    occurrences: null;
    occurrences_status: "unavailable";
    definition: GoldOperationDefinition;
  };
  metadata: GoldMetadata;
};
type Obj = Record<string, unknown>;
const isObject = (v: unknown): v is Obj =>
  typeof v === "object" && v !== null && !Array.isArray(v);
function fail(path: string): never {
  throw new OperationContractError(`${path} inválido no contrato Gold v2.`);
}
function text(v: unknown, path: string, empty = false): string {
  if (typeof v !== "string" || (!empty && !v.trim())) return fail(path);
  return v;
}
function list(v: unknown, path: string): string[] {
  if (!Array.isArray(v)) return fail(path);
  return v.map((item, i) => text(item, `${path}[${i}]`, true));
}
function num(v: unknown, path: string): number {
  if (typeof v !== "number" || !Number.isFinite(v)) return fail(path);
  return v;
}
function nullableNum(v: unknown, path: string): number | null {
  return v === null ? null : num(v, path);
}
function nullableInteger(v: unknown, path: string, minimum = 0): number | null {
  if (v === null) return null;
  const value = num(v, path);
  if (!Number.isSafeInteger(value) || value < minimum) return fail(path);
  return value;
}
function state(v: unknown, path: string): OperationStatus {
  if (
    v === "available" ||
    v === "empty" ||
    v === "partial" ||
    v === "unavailable"
  )
    return v;
  return fail(path);
}
function month(v: unknown, path: string): string {
  const value = text(v, path);
  if (!/^(?!0000)\d{4}-(0[1-9]|1[0-2])$/.test(value)) return fail(path);
  return value;
}
function period(v: unknown, path: string): GoldOperationPoint["period"] {
  if (!isObject(v)) return fail(path);
  const start = month(v.start, `${path}.start`),
    end = month(v.end, `${path}.end`);
  if (start > end) return fail(path);
  return { start, end, granularity: "month" };
}
function metadata(v: unknown): GoldMetadata {
  const parsed = decodeGoldMetadata(v);
  if (parsed.schema_version !== "gold-csv-v2")
    return fail("metadata.schema_version");
  if (parsed.temporal_scope !== "monthly")
    return fail("metadata.temporal_scope");
  return parsed;
}
function point(v: unknown, path: string): GoldOperationPoint {
  if (!isObject(v)) return fail(path);
  const periodValue = period(v.period, `${path}.period`);
  const observed =
    v.observed_period === null
      ? null
      : period(v.observed_period, `${path}.observed_period`);
  const out: GoldOperationPoint = {
    feeder_id: text(v.feeder_id, `${path}.feeder_id`),
    municipality:
      v.municipality === null
        ? null
        : text(v.municipality, `${path}.municipality`, true),
    period: periodValue,
    observed_period: observed,
    observed_competencies: list(
      v.observed_competencies,
      `${path}.observed_competencies`,
    ),
    missing_competencies: list(
      v.missing_competencies,
      `${path}.missing_competencies`,
    ),
    duration_hours_sum: nullableNum(
      v.duration_hours_sum,
      `${path}.duration_hours_sum`,
    ),
    interruption_count: nullableInteger(
      v.interruption_count,
      `${path}.interruption_count`,
    ),
    denominator_uc_count: nullableInteger(
      v.denominator_uc_count,
      `${path}.denominator_uc_count`,
      -Number.MAX_SAFE_INTEGER,
    ),
    dec_hours_per_uc: nullableNum(
      v.dec_hours_per_uc,
      `${path}.dec_hours_per_uc`,
    ),
    fec_interruptions_per_uc: nullableNum(
      v.fec_interruptions_per_uc,
      `${path}.fec_interruptions_per_uc`,
    ),
    status: state(v.status, `${path}.status`),
    dec_status: state(v.dec_status, `${path}.dec_status`),
    fec_status: state(v.fec_status, `${path}.fec_status`),
    limitations: list(v.limitations, `${path}.limitations`),
  };
  if (
    (out.dec_status === "available" || out.dec_status === "partial") !==
      (out.dec_hours_per_uc !== null) ||
    (out.fec_status === "available" || out.fec_status === "partial") !==
      (out.fec_interruptions_per_uc !== null)
  )
    return fail(`${path}.indicator_status`);
  return out;
}
function definition(v: unknown): GoldOperationDefinition {
  if (!isObject(v)) return fail("data.definition");
  return {
    reference: text(v.reference, "definition.reference"),
    dec_formula: text(v.dec_formula, "definition.dec_formula"),
    fec_formula: text(v.fec_formula, "definition.fec_formula"),
    dec_unit: text(v.dec_unit, "definition.dec_unit"),
    fec_unit: text(v.fec_unit, "definition.fec_unit"),
    event_grain: text(v.event_grain, "definition.event_grain"),
    population: text(v.population, "definition.population"),
    completeness: text(v.completeness, "definition.completeness"),
  };
}

function checkContext(
  meta: GoldMetadata,
  expected: {
    start: string;
    end: string;
    feederId?: string | null;
    municipality?: string | null;
  },
) {
  if (
    !meta.period ||
    meta.period.start !== expected.start ||
    meta.period.end !== expected.end
  )
    fail("metadata.period");
  if (
    expected.feederId !== undefined &&
    meta.filters.alimentador !== expected.feederId
  )
    fail("metadata.filters.alimentador");
  if (
    expected.municipality !== undefined &&
    meta.filters.municipio !== expected.municipality
  )
    fail("metadata.filters.municipio");
}

export function decodeGoldOperationSummary(
  v: unknown,
  expected?: {
    start: string;
    end: string;
    feederId?: string | null;
    municipality?: string | null;
  },
): GoldOperationSummaryEnvelope {
  if (!isObject(v) || !isObject(v.data)) return fail("resposta");
  const s = v.data,
    parsedPeriod = period(s.period, "data.summary.period");
  const ids = (key: string) => list(s[key], `data.summary.${key}`);
  const nullableIds = (key: string) => (s[key] === null ? null : ids(key));
  const parsed: GoldOperationSummary = {
    period: parsedPeriod,
    observed_period:
      s.observed_period === null
        ? null
        : period(s.observed_period, "data.summary.observed_period"),
    duration_hours_sum: nullableNum(
      s.duration_hours_sum,
      "data.summary.duration_hours_sum",
    ),
    interruption_count: nullableInteger(
      s.interruption_count,
      "data.summary.interruption_count",
    ),
    denominator_uc_count: nullableInteger(
      s.denominator_uc_count,
      "data.summary.denominator_uc_count",
      -Number.MAX_SAFE_INTEGER,
    ),
    dec_hours_per_uc: nullableNum(
      s.dec_hours_per_uc,
      "data.summary.dec_hours_per_uc",
    ),
    fec_interruptions_per_uc: nullableNum(
      s.fec_interruptions_per_uc,
      "data.summary.fec_interruptions_per_uc",
    ),
    dec_denominator_uc_count: nullableInteger(
      s.dec_denominator_uc_count,
      "data.summary.dec_denominator_uc_count",
      -Number.MAX_SAFE_INTEGER,
    ),
    fec_denominator_uc_count: nullableInteger(
      s.fec_denominator_uc_count,
      "data.summary.fec_denominator_uc_count",
      -Number.MAX_SAFE_INTEGER,
    ),
    dec_included_feeder_ids: ids("dec_included_feeder_ids"),
    fec_included_feeder_ids: ids("fec_included_feeder_ids"),
    dec_excluded_feeder_ids: ids("dec_excluded_feeder_ids"),
    fec_excluded_feeder_ids: ids("fec_excluded_feeder_ids"),
    included_feeder_ids: nullableIds("included_feeder_ids"),
    excluded_feeder_ids: nullableIds("excluded_feeder_ids"),
    dec_status: state(s.dec_status, "data.summary.dec_status"),
    fec_status: state(s.fec_status, "data.summary.fec_status"),
    status: state(s.status, "data.summary.status"),
    limitations: list(s.limitations, "data.summary.limitations"),
  };
  const meta = metadata(v.metadata);
  if (
    parsed.period.start !== meta.period?.start ||
    parsed.period.end !== meta.period?.end
  )
    fail("data.summary.period");
  if (meta.status !== parsed.status) fail("metadata.status");
  if (expected) checkContext(meta, expected);
  return {
    data: { summary: parsed, definition: definition(v.definition) },
    metadata: meta,
  };
}
export function decodeGoldOperationRanking(
  v: unknown,
  expectedMetric: "dec" | "fec",
  expected?: {
    start: string;
    end: string;
    feederId?: string | null;
    municipality?: string | null;
  },
): GoldOperationRankingEnvelope {
  if (
    !isObject(v) ||
    !isObject(v.data) ||
    !Array.isArray(v.data.items) ||
    !Array.isArray(v.data.excluded) ||
    v.data.metric !== expectedMetric
  )
    return fail("data.ranking");
  const rank = (item: unknown, i: number) => {
    if (
      !isObject(item) ||
      typeof item.rank !== "number" ||
      !Number.isInteger(item.rank) ||
      item.rank < 1
    )
      return fail(`data.items[${i}].rank`);
    return { ...point(item, `data.items[${i}]`), rank: item.rank };
  };
  const items = v.data.items.map(rank);
  const excluded = v.data.excluded.map((item, i) =>
    point(item, `data.excluded[${i}]`),
  );
  const selectedValue = (item: GoldOperationPoint) =>
    expectedMetric === "dec"
      ? item.dec_hours_per_uc
      : item.fec_interruptions_per_uc;
  if (items.some((item) => selectedValue(item) === null))
    fail("data.items.metric");
  if (excluded.some((item) => selectedValue(item) !== null))
    fail("data.excluded.metric");
  if (
    new Set(items.map((item) => item.feeder_id)).size !== items.length ||
    new Set(excluded.map((item) => item.feeder_id)).size !== excluded.length ||
    items.some((item) =>
      excluded.some((other) => other.feeder_id === item.feeder_id),
    )
  )
    fail("data.ranking.feeders");
  const meta = metadata(v.metadata);
  if (expected) checkContext(meta, expected);
  return {
    data: {
      items,
      excluded,
      metric: expectedMetric,
      order: text(v.data.order, "data.order"),
      definition: definition(v.data.definition),
    },
    metadata: meta,
  };
}
export function decodeGoldOperationDetail(
  v: unknown,
  expected: {
    feederId: string;
    start: string;
    end: string;
    municipality?: string | null;
  },
): GoldOperationDetailEnvelope {
  if (
    !isObject(v) ||
    !isObject(v.data) ||
    !Array.isArray(v.data.series) ||
    v.data.occurrences !== null ||
    v.data.occurrences_status !== "unavailable"
  )
    return fail("data.detail");
  const summary = point(v.data.summary, "data.summary");
  if (summary.feeder_id !== expected.feederId)
    return fail("data.summary.feeder_id");
  const series = v.data.series.map((item, i) =>
    point(item, `data.series[${i}]`),
  );
  if (
    series.some(
      (item) =>
        item.feeder_id !== expected.feederId ||
        item.period.start !== item.period.end ||
        item.period.start < expected.start ||
        item.period.end > expected.end,
    )
  )
    return fail("data.series");
  const meta = metadata(v.metadata);
  checkContext(meta, expected);
  if (
    summary.period.start !== expected.start ||
    summary.period.end !== expected.end
  )
    fail("data.summary.period");
  return {
    data: {
      summary,
      series,
      occurrences: null,
      occurrences_status: "unavailable",
      definition: definition(v.data.definition),
    },
    metadata: meta,
  };
}
