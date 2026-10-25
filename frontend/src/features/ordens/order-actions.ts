import type { OrderDetail, OrderStatus } from "@/shared/api/orders";
import { ApiError } from "@/shared/api/client";

const transitions: Record<OrderStatus, readonly OrderStatus[]> = {
  PENDENTE: ["EM_ANDAMENTO"],
  EM_ANDAMENTO: ["CONCLUIDA"],
  CONCLUIDA: [],
  CANCELADA: [],
};

export function allowedOrderStatuses(status: OrderStatus): OrderStatus[] {
  return [status, ...transitions[status]];
}

export function isOrderFinal(status: OrderStatus) {
  return status === "CONCLUIDA" || status === "CANCELADA";
}

export function orderStatusLabel(status: OrderStatus) {
  const labels: Record<OrderStatus, string> = {
    PENDENTE: "Pendente",
    EM_ANDAMENTO: "Em andamento",
    CONCLUIDA: "Concluída",
    CANCELADA: "Cancelada",
  };
  return labels[status];
}

export function orderErrorMessage(error: unknown) {
  if (error instanceof ApiError && error.status === 409) {
    const body = error.data;
    if (body && typeof body === "object" && "error" in body) {
      const conflict = body.error;
      if (
        conflict &&
        typeof conflict === "object" &&
        "message" in conflict &&
        typeof conflict.message === "string"
      ) {
        return conflict.message;
      }
    }
  }
  if (error instanceof Error && error.message.trim()) return error.message;
  return "Não foi possível atualizar a ordem. Tente novamente.";
}

type SnapshotSource = {
  kind: string;
  version: string;
  isDemo?: boolean;
  updatedAt?: string;
};
type SnapshotSignal = { id?: string; label: string; weight?: number };

export type OrderFoundation = {
  available: boolean;
  legacy: boolean;
  supported: boolean;
  source: SnapshotSource | null;
  period: { start: string; end: string } | null;
  estimateKwh: number | null;
  estimateUnavailable: boolean;
  signals: SnapshotSignal[];
  estimateEvidence: string | null;
  limitations: string[];
};

const record = (value: unknown): Record<string, unknown> | null =>
  value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
const text = (value: unknown): string | null =>
  typeof value === "string" && value.trim() ? value.trim() : null;
const finiteNumber = (value: unknown): number | null =>
  typeof value === "number" && Number.isFinite(value) ? value : null;
const dateText = (value: unknown): string | null => {
  const valueText = text(value);
  return valueText && Number.isFinite(Date.parse(valueText)) ? valueText : null;
};
const competenceText = (value: unknown): string | null =>
  typeof value === "string" && /^\d{4}-(0[1-9]|1[0-2])$/.test(value)
    ? value
    : null;

/** Reads only known, validated snapshot fields; historical extensions stay opaque. */
export function readOrderFoundation(order: OrderDetail): OrderFoundation {
  const snapshot = record(order.suspicion_snapshot);
  if (!snapshot) {
    return {
      available: false,
      legacy: false,
      supported: false,
      source: null,
      period: null,
      estimateKwh: null,
      estimateUnavailable: true,
      signals: [],
      estimateEvidence: null,
      limitations: [],
    };
  }

  const schemaVersion = snapshot.snapshot_schema_version;
  const legacy = schemaVersion === undefined;
  const supported = legacy || schemaVersion === "1";
  if (!supported) {
    return {
      available: true,
      legacy,
      supported: false,
      source: null,
      period: null,
      estimateKwh: null,
      estimateUnavailable: true,
      signals: [],
      estimateEvidence: null,
      limitations: [],
    };
  }

  const data = record(snapshot.data);
  const metadata = record(snapshot.metadata);
  const sourceData = record(metadata?.source);
  const periodData = record(metadata?.period);
  const estimateData = record(data?.estimate_evidence);
  const sourceKind = text(sourceData?.kind);
  const sourceVersion = text(sourceData?.version);
  const sourceUpdatedAt = dateText(sourceData?.updated_at);
  const sourceIsDemo = sourceData?.is_demo;
  const source =
    sourceKind && sourceVersion
      ? {
          kind: sourceKind,
          version: sourceVersion,
          ...(typeof sourceIsDemo === "boolean"
            ? { isDemo: sourceIsDemo }
            : {}),
          ...(sourceUpdatedAt ? { updatedAt: sourceUpdatedAt } : {}),
        }
      : null;
  const start = competenceText(periodData?.start);
  const end = competenceText(periodData?.end);
  const period = start && end && start <= end ? { start, end } : null;
  const rawEstimate = data?.potential_recoverable_energy_kwh;
  const candidateEstimate = finiteNumber(rawEstimate);
  const estimateKwh =
    candidateEstimate !== null && candidateEstimate >= 0
      ? candidateEstimate
      : null;
  const estimateUnavailable =
    rawEstimate === null || rawEstimate === undefined || estimateKwh === null;
  const signals: SnapshotSignal[] = Array.isArray(data?.signals)
    ? data.signals.flatMap((candidate) => {
        const item = record(candidate);
        const label = text(item?.label);
        if (!label) return [];
        const id = text(item?.id);
        const weight = finiteNumber(item?.weight);
        return [
          {
            label,
            ...(id ? { id } : {}),
            ...(weight !== null && weight >= 0 && weight <= 1
              ? { weight }
              : {}),
          },
        ];
      })
    : [];
  const limitations = Array.isArray(data?.limitations)
    ? data.limitations.flatMap((item) => (text(item) ? [text(item)!] : []))
    : [];
  const reference = text(estimateData?.reference);

  return {
    available: true,
    legacy,
    supported,
    source,
    period,
    estimateKwh,
    estimateUnavailable,
    signals,
    estimateEvidence: reference,
    limitations,
  };
}
