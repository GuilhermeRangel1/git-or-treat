import type { OrderDetail, OrderStatus } from "@/shared/api/orders";
import { ApiError } from "@/shared/api/client";

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
  origin: "gold" | "synthetic" | null;
  fingerprint: string | null;
  schemaVersion: string | null;
  temporalScope: string | null;
  category: string | null;
  ruleVersion: string | null;
  recoveryEstimateStatus: string | null;
  recoveryEstimateMethod: string | null;
  historicalRecoveryStatus: string | null;
  goldEvidence: { label: string; value: string }[];
  goldVariation: { label: string; value: string }[];
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

function recoveryStatusLabel(value: unknown): string {
  const labels: Record<string, string> = {
    DISPONIVEL_REFERENCIA_HISTORICA: "Referência histórica disponível",
    SEM_REFERENCIA_VALIDADA: "Sem referência histórica validada",
    ESTIMATIVA_UC_INDISPONIVEL: "Estimativa individual indisponível",
    BASE_INSUFICIENTE: "Base histórica insuficiente",
    CANDIDATO_REPROVADO_NA_VALIDACAO_TEMPORAL:
      "Referência reprovada na validação temporal",
  };
  return typeof value === "string" && labels[value]
    ? labels[value]
    : "Estado não reconhecido no snapshot";
}

function recoveryMethodLabel(value: unknown): string {
  const labels: Record<string, string> = {
    MEDIA_GLOBAL_COM_GRUPOS_OPCIONAIS_V2:
      "Média global histórica com grupos opcionais (v2)",
  };
  return typeof value === "string" && labels[value]
    ? labels[value]
    : "Método não reconhecido no snapshot";
}

function recoveryReferenceLabel(value: unknown): string {
  if (value === "global") return "Global";
  if (value === "0") return "Sem irregularidade confirmada anterior";
  if (value === "1") return "Com irregularidade confirmada anterior";
  return typeof value === "string" && value.trim()
    ? "Referência sem rótulo reconhecido"
    : "Indisponível";
}

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
      origin: null,
      fingerprint: null,
      schemaVersion: null,
      temporalScope: null,
      category: null,
      ruleVersion: null,
      recoveryEstimateStatus: null,
      recoveryEstimateMethod: null,
      historicalRecoveryStatus: null,
      goldEvidence: [],
      goldVariation: [],
    };
  }

  const schemaVersion = snapshot.snapshot_schema_version;
  const legacy = schemaVersion === undefined;
  const supported = legacy || schemaVersion === "1" || schemaVersion === "2";
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
      origin: null,
      fingerprint: null,
      schemaVersion: typeof schemaVersion === "string" ? schemaVersion : null,
      temporalScope: null,
      category: null,
      ruleVersion: null,
      recoveryEstimateStatus: null,
      recoveryEstimateMethod: null,
      historicalRecoveryStatus: null,
      goldEvidence: [],
      goldVariation: [],
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
  const isGold = schemaVersion === "2";
  if (isGold) {
    const evidence = record(data?.evidence);
    const variation = record(data?.variation);
    const display = (label: string, value: unknown, unit = "") => ({
      label,
      value:
        value === null || value === undefined
          ? "Indisponível"
          : typeof value === "number" && Number.isFinite(value)
            ? `${value.toLocaleString("pt-BR", { maximumFractionDigits: 2 })}${unit}`
            : typeof value === "boolean"
              ? value
                ? "Sim"
                : "Não"
              : typeof value === "string"
                ? value
                : "Indisponível",
    });
    const month = (value: unknown) =>
      typeof value === "string" && /^\d{4}-(0[1-9]|1[0-2])$/.test(value)
        ? value
        : "período não informado";
    const variationRows = variation
      ? [
          display(
            `Média P1 (${month(variation.p1_start)} a ${month(variation.p1_end)})`,
            variation.p1_average_kwh_per_month,
            " kWh/mês",
          ),
          display(`Meses observados em P1`, variation.p1_months_observed),
          display(
            `Média P2 (${month(variation.p2_start)} a ${month(variation.p2_end)})`,
            variation.p2_average_kwh_per_month,
            " kWh/mês",
          ),
          display(`Meses observados em P2`, variation.p2_months_observed),
          display("Diferença observada", variation.variation_kwh, " kWh/mês"),
          display(
            "Variação percentual observada",
            variation.variation_pct,
            "%",
          ),
          display("Queda acima de 30%", variation.drop_over_30_pct),
        ]
      : [];
    const historicalLower = finiteNumber(
      evidence?.historical_recovery_interval_lower_kwh,
    );
    const historicalUpper = finiteNumber(
      evidence?.historical_recovery_interval_upper_kwh,
    );
    const historicalInterval =
      historicalLower === null && historicalUpper === null
        ? null
        : `${historicalLower === null ? "indisponível" : historicalLower.toLocaleString("pt-BR", { maximumFractionDigits: 2 })} a ${historicalUpper === null ? "indisponível" : historicalUpper.toLocaleString("pt-BR", { maximumFractionDigits: 2 })} kWh/inspeção`;
    const goldEvidence = evidence
      ? [
          display("Inspeções realizadas", evidence.inspections_performed),
          display(
            "Irregularidades confirmadas",
            evidence.confirmed_irregular_inspections,
          ),
          display(
            "Média histórica por leitura",
            evidence.historical_average_kwh_per_reading,
            " kWh/leitura",
          ),
          display(
            "Geração distribuída",
            evidence.distributed_generation_present,
          ),
          display("Situação cadastral", evidence.cadastral_status),
          display("Contatos ao atendimento", evidence.call_center_contacts),
          display("Interrupções", evidence.interruptions),
          display(
            "Média histórica de recuperação por inspeção",
            evidence.historical_recovery_mean_kwh_per_inspection,
            " kWh/inspeção",
          ),
          display("Intervalo da referência histórica", historicalInterval),
          display(
            "Referência da média histórica",
            recoveryReferenceLabel(evidence.historical_recovery_reference),
          ),
          display(
            "Estado da média histórica",
            recoveryStatusLabel(evidence.historical_recovery_status),
          ),
          display(
            "Estado da estimativa individual",
            recoveryStatusLabel(evidence.recovery_estimate_status),
          ),
          display(
            "Método da estimativa individual",
            recoveryMethodLabel(evidence.recovery_estimate_method),
          ),
        ]
      : [];
    return {
      available: true,
      legacy: false,
      supported: true,
      source,
      period: null,
      estimateKwh: null,
      estimateUnavailable: true,
      signals: [],
      estimateEvidence: null,
      limitations: Array.isArray(data?.limitations)
        ? data.limitations.flatMap((item) => (text(item) ? [text(item)!] : []))
        : [],
      origin: "gold",
      fingerprint: text(metadata?.fingerprint),
      schemaVersion: text(metadata?.schema_version),
      temporalScope: text(metadata?.temporal_scope),
      category: text(data?.category),
      ruleVersion: text(data?.rule_version),
      recoveryEstimateStatus: text(evidence?.recovery_estimate_status),
      recoveryEstimateMethod: text(evidence?.recovery_estimate_method),
      historicalRecoveryStatus: text(evidence?.historical_recovery_status),
      goldEvidence,
      goldVariation: variationRows,
    };
  }
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
    origin:
      source?.kind === "gold" ? "gold" : source?.kind ? "synthetic" : null,
    fingerprint: text(metadata?.fingerprint),
    schemaVersion: text(metadata?.schema_version),
    temporalScope: text(metadata?.temporal_scope),
    category: null,
    ruleVersion: text(data?.rule_version),
    recoveryEstimateStatus: null,
    recoveryEstimateMethod: null,
    historicalRecoveryStatus: null,
    goldEvidence: [],
    goldVariation: [],
  };
}
