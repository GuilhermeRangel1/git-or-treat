import { ApiError } from "@/shared/api/client";

export type GoldMetadata = {
  contract_version: "2.0.0";
  status: "available" | "empty" | "partial" | "unavailable";
  period: { start: string; end: string; granularity: "month" } | null;
  filters: {
    municipio: string | null;
    bairro: string | null;
    classe: string | null;
    alimentador: string | null;
  };
  source: { kind: "gold"; version: string; is_demo: false; updated_at: string };
  limitations: string[];
  temporal_scope: "monthly" | "snapshot";
  schema_version: "gold-csv-v2";
  fingerprint: string;
};

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function isGoldMetadata(value: unknown): boolean {
  return record(value) && record(value.source) && value.source.kind === "gold";
}

export function decodeGoldMetadata(value: unknown): GoldMetadata {
  const invalid = () => {
    throw new ApiError(
      "Metadados Gold inválidos.",
      200,
      undefined,
      "invalid-response",
    );
  };
  if (!record(value) || !record(value.source) || !record(value.filters))
    return invalid();
  const source = value.source;
  const filters = value.filters;
  if (
    value.contract_version !== "2.0.0" ||
    source.kind !== "gold" ||
    source.is_demo !== false ||
    typeof source.version !== "string" ||
    !source.version.trim() ||
    typeof source.updated_at !== "string" ||
    !Number.isFinite(Date.parse(source.updated_at)) ||
    value.schema_version !== "gold-csv-v2" ||
    typeof value.fingerprint !== "string" ||
    !/^[a-f0-9]{64}$/.test(value.fingerprint) ||
    !["available", "empty", "partial", "unavailable"].includes(
      String(value.status),
    ) ||
    !["monthly", "snapshot"].includes(String(value.temporal_scope)) ||
    !Array.isArray(value.limitations) ||
    !value.limitations.every((item) => typeof item === "string") ||
    !["municipio", "bairro", "classe", "alimentador"].every(
      (key) => filters[key] === null || typeof filters[key] === "string",
    )
  )
    return invalid();
  if (value.period !== null) {
    const period = value.period;
    if (
      !record(period) ||
      period.granularity !== "month" ||
      typeof period.start !== "string" ||
      typeof period.end !== "string" ||
      !/^\d{4}-(0[1-9]|1[0-2])$/.test(period.start) ||
      !/^\d{4}-(0[1-9]|1[0-2])$/.test(period.end) ||
      period.start > period.end
    )
      return invalid();
  }
  if (value.temporal_scope === "snapshot" && value.period !== null)
    return invalid();
  return value as GoldMetadata;
}
