import type { PanoramaFilters } from "../../shared/analytics/types";

export type PanoramaInsightStatus =
  | "answered"
  | "needs_clarification"
  | "refused"
  | "no_evidence"
  | "recoverable_error";

export interface PanoramaInsightObservationValue {
  label: string;
  value: number;
}

export interface PanoramaInsightEvidence {
  source: string;
  description: string;
  is_demo: boolean;
}

export interface PanoramaInsightContribution {
  dimension: "municipio" | "classe";
  segmento: string;
  variacaoAbsoluta: number;
  participacaoPercentual: number | null;
}

export interface PanoramaInsightAnalysis {
  direcao: "alta" | "queda" | "estavel" | "indisponivel";
  variacaoPercentual: number | null;
  principalContribuicao: PanoramaInsightContribution | null;
  compensacao: PanoramaInsightContribution | null;
}

export interface PanoramaInsight {
  correlation_id: string | null;
  audit_reference: string | null;
  error: { code: string; retryable: boolean } | null;
  status: PanoramaInsightStatus;
  context: {
    metric: string;
    unit: string;
    period: { start: string; end: string; granularity: string };
    filters: Record<string, string | number | boolean>;
  };
  observation: { values: PanoramaInsightObservationValue[] };
  hypothesis: string | null;
  message: string | null;
  evidence: PanoramaInsightEvidence[];
  limitations: string[];
}

export interface PanoramaInsightEnvelope {
  insight: PanoramaInsight;
  metric: { id: string; definicao: string; formula: string };
  analysis: PanoramaInsightAnalysis;
  source: {
    kind: string;
    loteVersao: string;
    dataAtualizacao: string;
    isDemo: boolean;
    limitacoes: string[];
  };
}

export interface PanoramaInsightErrorResponse {
  contract_version: "v1";
  status: "error";
  correlation_id: string;
  message: string;
  error: { code: string; retryable: boolean };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isText(value: unknown, maxLength: number): value is string {
  return (
    typeof value === "string" &&
    value.trim().length > 0 &&
    value.length <= maxLength
  );
}

function isFilters(
  value: unknown,
): value is Record<string, string | number | boolean> {
  if (!isRecord(value) || Object.keys(value).length > 20) return false;
  return Object.entries(value).every(
    ([key, item]) =>
      /^[a-z][a-zA-Z0-9_]{0,79}$/.test(key) &&
      ((typeof item === "string" && isText(item, 120)) ||
        (typeof item === "number" && Number.isFinite(item)) ||
        typeof item === "boolean"),
  );
}

function isDate(value: unknown): value is string {
  return (
    typeof value === "string" &&
    /^\d{4}-\d{2}-\d{2}$/.test(value) &&
    Number.isFinite(Date.parse(`${value}T00:00:00Z`))
  );
}

function matchesExpectedFilters(
  received: Record<string, string | number | boolean>,
  expected: PanoramaFilters,
) {
  const keys = Object.keys(expected) as (keyof PanoramaFilters)[];
  return (
    Object.keys(received).length === keys.length &&
    keys.every((key) => received[key] === expected[key])
  );
}

function decodeTextList(value: unknown, maxCount: number, maxLength: number) {
  if (
    !Array.isArray(value) ||
    value.length > maxCount ||
    !value.every((item) => isText(item, maxLength))
  ) {
    throw new Error("Resposta inválida do serviço de insight.");
  }
  return value as string[];
}

function decodeContribution(
  value: unknown,
): PanoramaInsightContribution | null {
  if (value === null) return null;
  if (
    !isRecord(value) ||
    (value.dimension !== "municipio" && value.dimension !== "classe") ||
    !isText(value.segmento, 120) ||
    typeof value.variacaoAbsoluta !== "number" ||
    !Number.isFinite(value.variacaoAbsoluta) ||
    (value.participacaoPercentual !== null &&
      (typeof value.participacaoPercentual !== "number" ||
        !Number.isFinite(value.participacaoPercentual)))
  ) {
    throw new Error("Resposta inválida do serviço de insight.");
  }
  return {
    dimension: value.dimension,
    segmento: value.segmento,
    variacaoAbsoluta: value.variacaoAbsoluta,
    participacaoPercentual: value.participacaoPercentual,
  };
}

export function decodePanoramaInsight(
  value: unknown,
  expectedFilters: PanoramaFilters,
  expectedBatch: string,
  expectedUpdatedAt: string,
): PanoramaInsightEnvelope {
  if (
    !isRecord(value) ||
    !isRecord(value.insight) ||
    !isRecord(value.metric) ||
    !isRecord(value.analysis) ||
    !isRecord(value.source)
  )
    throw new Error("Resposta inválida do serviço de insight.");
  const analysis = value.analysis;
  const directions: PanoramaInsightAnalysis["direcao"][] = [
    "alta",
    "queda",
    "estavel",
    "indisponivel",
  ];
  if (
    !directions.includes(
      analysis.direcao as PanoramaInsightAnalysis["direcao"],
    ) ||
    (analysis.variacaoPercentual !== null &&
      (typeof analysis.variacaoPercentual !== "number" ||
        !Number.isFinite(analysis.variacaoPercentual)))
  ) {
    throw new Error("Resposta inválida do serviço de insight.");
  }
  const decodedAnalysis: PanoramaInsightAnalysis = {
    direcao: analysis.direcao as PanoramaInsightAnalysis["direcao"],
    variacaoPercentual: analysis.variacaoPercentual,
    principalContribuicao: decodeContribution(analysis.principalContribuicao),
    compensacao: decodeContribution(analysis.compensacao),
  };
  const raw = value.insight;
  const statuses: PanoramaInsightStatus[] = [
    "answered",
    "needs_clarification",
    "refused",
    "no_evidence",
    "recoverable_error",
  ];
  if (
    raw.contract_version !== "v1" ||
    !statuses.includes(raw.status as PanoramaInsightStatus)
  )
    throw new Error("Resposta inválida do serviço de insight.");

  const status = raw.status as PanoramaInsightStatus;
  const context = raw.context;
  const observation = raw.observation;
  if (
    !isRecord(context) ||
    !isText(context.metric, 160) ||
    !isText(context.unit, 60) ||
    !isRecord(context.period) ||
    !isDate(context.period.start) ||
    !isDate(context.period.end) ||
    context.period.start > context.period.end ||
    context.period.granularity !== "month" ||
    !isFilters(context.filters) ||
    !isRecord(observation) ||
    !Array.isArray(observation.values) ||
    observation.values.length > 20
  ) {
    throw new Error("Resposta inválida do serviço de insight.");
  }
  const values = observation.values.map((item) => {
    if (
      !isRecord(item) ||
      !isText(item.label, 120) ||
      typeof item.value !== "number" ||
      !Number.isFinite(item.value)
    ) {
      throw new Error("Resposta inválida do serviço de insight.");
    }
    return { label: item.label, value: item.value };
  });

  const expectedStart = `${expectedFilters.periodo}-01`;
  const [year, month] = expectedFilters.periodo.split("-").map(Number);
  const lastDay = new Date(Date.UTC(year, month, 0)).getUTCDate();
  const expectedEnd = `${expectedFilters.periodo}-${String(lastDay).padStart(2, "0")}`;
  if (
    context.period.start !== expectedStart ||
    context.period.end !== expectedEnd
  )
    throw new Error("O insight veio para outra competência.");
  if (status === "answered") {
    if (
      context.metric === "Indisponível" ||
      context.unit === "Indisponível" ||
      !matchesExpectedFilters(context.filters, expectedFilters) ||
      values.length === 0 ||
      !isText(raw.hypothesis, 4000) ||
      raw.message != null ||
      !Array.isArray(raw.evidence) ||
      raw.evidence.length === 0 ||
      raw.error != null
    ) {
      throw new Error("Resposta inválida do serviço de insight.");
    }
  } else if (!isText(raw.message, 4000) || raw.hypothesis != null) {
    throw new Error("Resposta inválida do serviço de insight.");
  }

  let error: PanoramaInsight["error"] = null;
  if (raw.error != null) {
    if (
      !isRecord(raw.error) ||
      !isText(raw.error.code, 80) ||
      typeof raw.error.retryable !== "boolean"
    ) {
      throw new Error("Resposta inválida do serviço de insight.");
    }
    error = { code: raw.error.code, retryable: raw.error.retryable };
  }
  if (["refused", "recoverable_error"].includes(status) !== Boolean(error))
    throw new Error("Resposta inválida do serviço de insight.");

  const evidence = raw.evidence;
  if (!Array.isArray(evidence) || evidence.length > 20)
    throw new Error("Resposta inválida do serviço de insight.");
  const decodedEvidence = evidence.map((item) => {
    if (
      !isRecord(item) ||
      !/^[a-z][a-z0-9]*(?:[._:-][a-z0-9]+)*$/.test(String(item.source)) ||
      !isText(item.description, 500) ||
      typeof item.is_demo !== "boolean"
    ) {
      throw new Error("Resposta inválida do serviço de insight.");
    }
    return {
      source: item.source as string,
      description: item.description,
      is_demo: item.is_demo,
    };
  });

  const correlationId = raw.correlation_id;
  if (
    correlationId != null &&
    (typeof correlationId !== "string" || !/^[a-f0-9]{32}$/.test(correlationId))
  ) {
    throw new Error("Resposta inválida do serviço de insight.");
  }
  const auditReference = raw.audit_reference;
  if (auditReference != null && !isText(auditReference, 200))
    throw new Error("Resposta inválida do serviço de insight.");

  if (
    !isText(value.metric.id, 120) ||
    !isText(value.metric.definicao, 1000) ||
    !isText(value.metric.formula, 1000) ||
    !isText(value.source.kind, 80) ||
    value.source.loteVersao !== expectedBatch ||
    !isText(value.source.loteVersao, 100) ||
    !isText(value.source.dataAtualizacao, 80) ||
    !Number.isFinite(Date.parse(value.source.dataAtualizacao)) ||
    value.source.dataAtualizacao !== expectedUpdatedAt ||
    value.source.isDemo !== true
  ) {
    throw new Error("O insight não corresponde ao lote exibido no Panorama.");
  }

  const insight: PanoramaInsight = {
    correlation_id: correlationId as string | null,
    audit_reference: auditReference as string | null,
    error,
    status,
    context: {
      metric: context.metric,
      unit: context.unit,
      period: {
        start: context.period.start,
        end: context.period.end,
        granularity: context.period.granularity as string,
      },
      filters: context.filters,
    },
    observation: { values },
    hypothesis: raw.hypothesis as string | null,
    message: raw.message as string | null,
    evidence: decodedEvidence,
    limitations: decodeTextList(raw.limitations, 22, 300),
  };

  if (status === "answered" && insight.evidence.some((item) => !item.is_demo))
    throw new Error(
      "A resposta não está identificada como demonstração sintética.",
    );

  return {
    insight,
    analysis: decodedAnalysis,
    metric: {
      id: value.metric.id,
      definicao: value.metric.definicao,
      formula: value.metric.formula,
    },
    source: {
      kind: value.source.kind,
      loteVersao: value.source.loteVersao,
      dataAtualizacao: value.source.dataAtualizacao,
      isDemo: true,
      limitacoes: decodeTextList(value.source.limitacoes, 20, 300),
    },
  };
}

export function decodePanoramaInsightError(
  value: unknown,
): PanoramaInsightErrorResponse | null {
  if (
    !isRecord(value) ||
    value.contract_version !== "v1" ||
    value.status !== "error" ||
    typeof value.correlation_id !== "string" ||
    !/^[a-f0-9]{32}$/.test(value.correlation_id) ||
    !isText(value.message, 300) ||
    !isRecord(value.error) ||
    !isText(value.error.code, 80) ||
    typeof value.error.retryable !== "boolean"
  ) {
    return null;
  }
  return {
    contract_version: "v1",
    status: "error",
    correlation_id: value.correlation_id,
    message: value.message,
    error: {
      code: value.error.code,
      retryable: value.error.retryable,
    },
  };
}
