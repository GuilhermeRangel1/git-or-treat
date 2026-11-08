import {
  decodeChatVisualization,
  sqlAnalysisVisualization,
  type ChatVisualization,
} from "./visualization";
export type AIConversationTurn = {
  role: "user" | "assistant";
  content: string;
};

export type AIQuestionRequest = {
  contract_version: "v1";
  expected_publication?: { lote: string; fingerprint: string };
  question: string;
  context: AIConversationTurn[];
  conversation_id?: string;
  continuation_token?: string;
  history_request_id?: string;
  refresh_context?: boolean;
};

export type AIEvidenceReference = {
  source: string;
  description: string;
  is_demo: boolean;
};

export type AIQuestionError = {
  code: string;
  retryable: boolean;
};

export type SqlAnalysisPresentation = {
  contract_version:
    | "text-to-sql-f1-presentation-v1"
    | "text-to-sql-f1-presentation-v2"
    | "text-to-sql-f1-presentation-v3"
    | "text-to-sql-f1-presentation-v4"
    | "text-to-sql-f1-presentation-v5"
    | "text-to-sql-f1-presentation-v6"
    | "text-to-sql-f1-presentation-v7"
    | "text-to-sql-f1-presentation-v8";
  state: "ready" | "empty" | "all_measures_null";
  operation:
    "total" | "monthly_series" | "grouped_total" | "ranking" | "comparison" | "grain_read" | "accumulated_total" | "average" | "snapshot_total" | "accumulated_average";
  answer: string;
  period: string;
  filters: string[];
  universe: string[];
  limitations: string[];
  columns: {
    key: string;
    label: string;
    role: "dimension" | "measure";
    semantic_id:
      | "competency"
      | "municipality"
      | "neighborhood"
      | "consumption_class"
      | "revenue_total"
      | "energy_total"
      | "attendance_total"
      | "attendance_accumulated_total"
      | "gd_units_total"
      | "satisfaction_accumulated_average"
      | "satisfaction_average"
      | "dec_value"
      | "fec_value"
      | "period_0_total"
      | "period_1_total"
      | "period_0_minus_period_1"
      | "period_0_growth_percent";
  unit: "R$" | "kWh" | "protocolos" | "UCs" | "pontos" | "horas por UC" | "interrupções por UC" | "%" | null;
  }[];
  rows: { observation_id: string; cells: (string | null)[] }[];
  evidence_digest: string;
};

export type AIAnalysisContext = {
  batch_reference?: string | null;
  metric?: string | null;
  metric_label?: string | null;
  metric_definition?: string | null;
  filter_labels?: Record<string, string>;
  unit?: string | null;
  period?: string | null;
  filters: Record<string, string | number | boolean>;
};

export type AIQuestionResponse = {
  contract_version: "v1";
  correlation_id?: string | null;
  audit_reference?: string | null;
  error?: AIQuestionError | null;
  status:
    | "answered"
    | "needs_clarification"
    | "refused"
    | "no_evidence"
    | "recoverable_error";
  model_tier?: "light" | "strong" | null;
  answer?: string | null;
  message?: string | null;
  evidence: AIEvidenceReference[];
  limitations: string[];
  analysis_context?: AIAnalysisContext | null;
  continuation_token?: string | null;
  visualization?: ChatVisualization;
  sql_analysis_mode?: boolean;
  sql_presentation?: SqlAnalysisPresentation;
};

export type AIQuestionErrorResponse = {
  contract_version: "v1";
  status: "error";
  correlation_id: string;
  message: string;
  error: AIQuestionError;
};

const IDENTIFIER = /^[a-z][a-z0-9]*(?:[._:-][a-z0-9]+)*$/;
const CORRELATION_ID = /^[a-f0-9]{32}$/;
const SQL_F1_LIMITATIONS = [
  "Faturamento representa valor faturado e não confirma recebimento ou pagamento.",
];
const SQL_ENERGY_LIMITATIONS = ["Consumo medido não é energia faturada."];
const SQL_GD_LIMITATIONS = [
  "Retrato do cadastro no lote publicado; não informa quando a GD entrou em operação nem confirma geração ou injeção.",
];
const SQL_ACCUMULATED_SATISFACTION_LIMITATIONS = [
  "Média das notas válidas do histórico publicado; o intervalo e a completude histórica não são conhecidos.",
];

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

function decodeError(value: unknown): AIQuestionError | null {
  if (!isRecord(value)) return null;
  if (!isText(value.code, 120) || typeof value.retryable !== "boolean")
    return null;
  return { code: value.code, retryable: value.retryable };
}

export function decodeAIQuestionResponse(value: unknown): AIQuestionResponse {
  if (!isRecord(value) || value.contract_version !== "v1") {
    throw new Error("Resposta inválida do serviço.");
  }

  const statuses = [
    "answered",
    "needs_clarification",
    "refused",
    "no_evidence",
    "recoverable_error",
  ] as const;
  if (!statuses.includes(value.status as (typeof statuses)[number])) {
    throw new Error("Resposta inválida do serviço.");
  }

  const status = value.status as AIQuestionResponse["status"];
  const answer = value.answer;
  const message = value.message;
  if (
    (answer !== undefined && answer !== null && !isText(answer, 4000)) ||
    (message !== undefined && message !== null && !isText(message, 4000))
  ) {
    throw new Error("Resposta inválida do serviço.");
  }

  const rawEvidence = value.evidence ?? [];
  if (!Array.isArray(rawEvidence) || rawEvidence.length > 20) {
    throw new Error("Resposta inválida do serviço.");
  }
  const evidence: AIEvidenceReference[] = rawEvidence.map((item) => {
    if (
      !isRecord(item) ||
      typeof item.source !== "string" ||
      !IDENTIFIER.test(item.source) ||
      !isText(item.description, 500) ||
      typeof item.is_demo !== "boolean"
    ) {
      throw new Error("Resposta inválida do serviço.");
    }
    return {
      source: item.source,
      description: item.description,
      is_demo: item.is_demo,
    };
  });

  const rawLimitations = value.limitations ?? [];
  if (
    !Array.isArray(rawLimitations) ||
    rawLimitations.length > 20 ||
    !rawLimitations.every((item) => isText(item, 500))
  ) {
    throw new Error("Resposta inválida do serviço.");
  }

  const error = value.error == null ? null : decodeError(value.error);
  if (value.error != null && error === null) {
    throw new Error("Resposta inválida do serviço.");
  }
  if (status === "answered") {
    if (
      !isText(answer, 4000) ||
      message != null ||
      evidence.length === 0 ||
      error
    ) {
      throw new Error("Resposta inválida do serviço.");
    }
  } else if (!isText(message, 4000) || answer != null) {
    throw new Error("Resposta inválida do serviço.");
  }
  if (["refused", "recoverable_error"].includes(status) !== Boolean(error)) {
    throw new Error("Resposta inválida do serviço.");
  }

  const correlationId = value.correlation_id;
  if (
    correlationId != null &&
    (typeof correlationId !== "string" || !CORRELATION_ID.test(correlationId))
  ) {
    throw new Error("Resposta inválida do serviço.");
  }

  let analysisContext: AIAnalysisContext | null | undefined;
  if (value.analysis_context == null) {
    analysisContext = value.analysis_context as null | undefined;
  } else {
    const context = value.analysis_context;
    if (
      !isRecord(context) ||
      (context.filters != null && !isRecord(context.filters))
    ) {
      throw new Error("Resposta inválida do serviço.");
    }
    const rawFilters = context.filters ?? {};
    if (Object.keys(rawFilters).length > 20) {
      throw new Error("Resposta inválida do serviço.");
    }
    const filters: Record<string, string | number | boolean> = {};
    for (const [key, filter] of Object.entries(rawFilters)) {
      if (
        !IDENTIFIER.test(key) ||
        !["string", "number", "boolean"].includes(typeof filter) ||
        (typeof filter === "string" && !isText(filter, 2438)) ||
        (typeof filter === "number" && !Number.isFinite(filter))
      ) {
        throw new Error("Resposta inválida do serviço.");
      }
      filters[key] = filter as string | number | boolean;
    }
    for (const field of [
      "metric",
      "metric_label",
      "unit",
      "period",
      "batch_reference",
    ] as const) {
      if (context[field] != null && !isText(context[field], 200)) {
        throw new Error("Resposta inválida do serviço.");
      }
    }
    if (
      context.metric_definition != null &&
      !isText(context.metric_definition, 500)
    ) {
      throw new Error("Resposta inválida do serviço.");
    }
    const filterLabels: Record<string, string> = {};
    if (context.filter_labels != null) {
      if (
        !isRecord(context.filter_labels) ||
        Object.keys(context.filter_labels).length > 20
      ) {
        throw new Error("Resposta inválida do serviço.");
      }
      for (const [key, label] of Object.entries(context.filter_labels)) {
        if (!Object.hasOwn(filters, key) || !isText(label, 200)) {
          throw new Error("Resposta inválida do serviço.");
        }
        filterLabels[key] = label;
      }
    }
    analysisContext = {
      batch_reference: context.batch_reference as string | null | undefined,
      metric: context.metric as string | null | undefined,
      metric_label: context.metric_label as string | null | undefined,
      metric_definition: context.metric_definition as string | null | undefined,
      filter_labels: filterLabels,
      unit: context.unit as string | null | undefined,
      period: context.period as string | null | undefined,
      filters,
    };
    if (
      analysisContext.metric == null &&
      analysisContext.unit == null &&
      analysisContext.period == null &&
      Object.keys(filters).length === 0
    ) {
      throw new Error("Resposta inválida do serviço.");
    }
  }

  const visualization = decodeChatVisualization(
    value.visualization,
    analysisContext,
  );
  if (
    visualization &&
    (status !== "answered" ||
      evidence.some(
        (e) => e.is_demo || !/^gold\.local(?::[a-f0-9]{64})?$/.test(e.source),
      ))
  )
    throw new Error("Visualização sem evidência autorizada.");
  const auditReference = value.audit_reference;
  if (auditReference != null && !isText(auditReference, 200)) {
    throw new Error("Resposta inválida do serviço.");
  }
  const modelTier = value.model_tier;
  const continuationToken = value.continuation_token;
  if (continuationToken != null && !isText(continuationToken, 16000)) {
    throw new Error("Resposta inválida do serviço.");
  }
  if (modelTier != null && modelTier !== "light" && modelTier !== "strong") {
    throw new Error("Resposta inválida do serviço.");
  }

  return {
    contract_version: "v1",
    correlation_id: correlationId as string | null | undefined,
    audit_reference: auditReference as string | null | undefined,
    error,
    status,
    model_tier: modelTier as "light" | "strong" | null | undefined,
    answer: answer as string | null | undefined,
    message: message as string | null | undefined,
    evidence,
    limitations: rawLimitations as string[],
    analysis_context: analysisContext,
    continuation_token: continuationToken as string | null | undefined,
    ...(visualization ? { visualization } : {}),
  };
}

function decodeSqlAnalysisPresentation(
  value: unknown,
): SqlAnalysisPresentation {
  const fail = (): never => {
    throw new Error("Resposta Text-to-SQL inválida.");
  };
  if (!isRecord(value)) return fail();
  const attendancePresentation = Array.isArray(value.columns) && value.columns.some(
    (item) => isRecord(item) && ["attendance_total", "attendance_accumulated_total"].includes(String(item.semantic_id)),
  );
  const accumulatedAttendancePresentation = Array.isArray(value.columns) && value.columns.some(
    (item) => isRecord(item) && item.semantic_id === "attendance_accumulated_total",
  );
  const continuityPresentation = Array.isArray(value.columns) && value.columns.some(
    (item) => isRecord(item) && ["dec_value", "fec_value"].includes(String(item.semantic_id)),
  );
  const acceptedLimitations = [SQL_F1_LIMITATIONS, SQL_ENERGY_LIMITATIONS];
  if (attendancePresentation) acceptedLimitations.push([]);
  if (accumulatedAttendancePresentation) acceptedLimitations.push([
    "Histórico publicado sem intervalo conhecido ou certificação de completude histórica.",
  ]);
  const gdUnitsPresentation = Array.isArray(value.columns) && value.columns.some(
    (item) => isRecord(item) && item.semantic_id === "gd_units_total",
  );
  if (gdUnitsPresentation) acceptedLimitations.push(SQL_GD_LIMITATIONS);
  const accumulatedSatisfactionPresentation = Array.isArray(value.columns) && value.columns.some(
    (item) => isRecord(item) && item.semantic_id === "satisfaction_accumulated_average",
  );
  if (accumulatedSatisfactionPresentation)
    acceptedLimitations.push(SQL_ACCUMULATED_SATISFACTION_LIMITATIONS);
  const satisfactionPresentation = Array.isArray(value.columns) && value.columns.some(
    (item) => isRecord(item) && item.semantic_id === "satisfaction_average",
  );
  if (satisfactionPresentation) acceptedLimitations.push([
    "Média das notas informadas; valores ausentes são excluídos e zero é válido.",
  ]);
  if (continuityPresentation) acceptedLimitations.push(
    [], ["Valores observados; cobertura do alimentador não certificada."],
  );
  const keys = [
    "contract_version",
    "state",
    "operation",
    "answer",
    "period",
    "filters",
    "universe",
    "limitations",
    "columns",
    "rows",
    "evidence_digest",
  ];
  if (
    Object.keys(value).some((key) => !keys.includes(key)) ||
    ![
      "text-to-sql-f1-presentation-v1",
      "text-to-sql-f1-presentation-v2",
      "text-to-sql-f1-presentation-v3",
      "text-to-sql-f1-presentation-v4",
      "text-to-sql-f1-presentation-v5",
      "text-to-sql-f1-presentation-v6",
      "text-to-sql-f1-presentation-v7",
      "text-to-sql-f1-presentation-v8",
    ].includes(String(value.contract_version)) ||
    !["ready", "empty", "all_measures_null"].includes(String(value.state)) ||
    ![
      "total",
      "monthly_series",
      "grouped_total",
      "ranking",
      "comparison",
      "grain_read",
      "accumulated_total",
      "average",
      "snapshot_total",
      "accumulated_average",
    ].includes(String(value.operation)) ||
    !isText(value.answer, 4000) ||
    !isText(value.period, 100) ||
    !Array.isArray(value.filters) ||
    value.filters.length > 20 ||
    !value.filters.every((filter) => isText(filter, 500)) ||
    !Array.isArray(value.universe) ||
    value.universe.length > 3 ||
    !value.universe.every((item) => isText(item, 250)) ||
    !Array.isArray(value.limitations) ||
    !acceptedLimitations.map((item) => JSON.stringify(item)).includes(
      JSON.stringify(value.limitations),
    ) ||
    !/^[a-f0-9]{64}$/.test(String(value.evidence_digest)) ||
    !Array.isArray(value.columns) ||
    value.columns.length < 1 ||
    value.columns.length > 32 ||
    !Array.isArray(value.rows) ||
    value.rows.length > 100
  )
    return fail();
  const columns = value.columns.map((item) => {
    if (
      !isRecord(item) ||
      Object.keys(item).some(
        (key) => !["key", "label", "role", "semantic_id", "unit"].includes(key),
      ) ||
      !isText(item.key, 120) ||
      !isText(item.label, 120) ||
      !["dimension", "measure"].includes(String(item.role)) ||
      ![
        "competency",
        "municipality",
        "neighborhood",
        "consumption_class",
        "revenue_total",
        "energy_total",
        "attendance_total",
        "attendance_accumulated_total",
        "gd_units_total",
        "satisfaction_accumulated_average",
        "satisfaction_average",
        "dec_value",
        "fec_value",
        "period_0_total",
        "period_1_total",
        "period_0_minus_period_1",
        "period_0_growth_percent",
      ].includes(String(item.semantic_id)) ||
      (item.unit !== null && item.unit !== "R$" && item.unit !== "kWh" && item.unit !== "protocolos" && item.unit !== "UCs" && item.unit !== "pontos" && item.unit !== "horas por UC" && item.unit !== "interrupções por UC" && item.unit !== "%") ||
      (item.role === "measure") !== (item.unit !== null) ||
      (item.role === "measure" && (
        (item.semantic_id === "period_0_growth_percent" && item.unit !== "%") ||
        (item.semantic_id === "energy_total" && item.unit !== "kWh") ||
        (item.semantic_id === "attendance_total" && item.unit !== "protocolos") ||
        (item.semantic_id === "attendance_accumulated_total" && item.unit !== "protocolos") ||
        (item.semantic_id === "gd_units_total" && item.unit !== "UCs") ||
        (item.semantic_id === "satisfaction_accumulated_average" && item.unit !== "pontos") ||
        (item.semantic_id === "satisfaction_average" && item.unit !== "pontos") ||
        (item.semantic_id === "dec_value" && item.unit !== "horas por UC") ||
        (item.semantic_id === "fec_value" && item.unit !== "interrupções por UC") ||
        (item.semantic_id === "revenue_total" && item.unit !== "R$")
      ))
    )
      return fail();
    return item as SqlAnalysisPresentation["columns"][number];
  });
  if (
    new Set(columns.map((column) => column.key)).size !== columns.length ||
    columns.some(
      (column) =>
        (column.role === "dimension") !==
        ["competency", "municipality", "neighborhood", "consumption_class", "feeder"].includes(
          column.semantic_id,
        ),
    )
  )
    return fail();
  const hasGrowth = columns.some(
    (column) => column.semantic_id === "period_0_growth_percent",
  );
  if ((value.contract_version === "text-to-sql-f1-presentation-v2") !== hasGrowth ||
      (value.contract_version === "text-to-sql-f1-presentation-v3" &&
       !columns.some((column) => column.semantic_id === "attendance_total")) ||
      (value.contract_version === "text-to-sql-f1-presentation-v4" &&
       !columns.some((column) => ["dec_value", "fec_value"].includes(column.semantic_id))) ||
      (value.contract_version === "text-to-sql-f1-presentation-v5" &&
       !columns.some((column) => column.semantic_id === "attendance_accumulated_total")) ||
      (value.contract_version === "text-to-sql-f1-presentation-v6" &&
       !columns.some((column) => column.semantic_id === "satisfaction_average")) ||
      (value.contract_version === "text-to-sql-f1-presentation-v7" &&
       !columns.some((column) => column.semantic_id === "gd_units_total")) ||
      (value.contract_version === "text-to-sql-f1-presentation-v8" &&
       !columns.some((column) => column.semantic_id === "satisfaction_accumulated_average")))
    return fail();
  const energyResult = columns.some((column) => column.role === "measure" && column.unit === "kWh");
  if (JSON.stringify(value.limitations) !== JSON.stringify(
    continuityPresentation ? value.limitations :
    energyResult ? SQL_ENERGY_LIMITATIONS :
    accumulatedAttendancePresentation
      ? ["Histórico publicado sem intervalo conhecido ou certificação de completude histórica."]
      : satisfactionPresentation
      ? ["Média das notas informadas; valores ausentes são excluídos e zero é válido."]
      : gdUnitsPresentation ? SQL_GD_LIMITATIONS
      : accumulatedSatisfactionPresentation ? SQL_ACCUMULATED_SATISFACTION_LIMITATIONS
      : attendancePresentation ? [] : SQL_F1_LIMITATIONS,
  )) return fail();
  const rows = value.rows.map((item, index) => {
    if (
      !isRecord(item) ||
      Object.keys(item).some(
        (key) => !["observation_id", "cells"].includes(key),
      ) ||
      item.observation_id !== `row_${index + 1}` ||
      !Array.isArray(item.cells) ||
      item.cells.length !== columns.length ||
      !item.cells.every(
        (cell, cellIndex) =>
          cell === null ||
          (typeof cell === "string" &&
            cell.length <= 16384 &&
            (columns[cellIndex].role !== "measure" ||
              /^-?(?:0|[1-9][0-9]{0,100})(?:\.[0-9]{1,100})?$/.test(cell))),
      )
    )
      return fail();
    return item as SqlAnalysisPresentation["rows"][number];
  });
  if (value.state === "empty" && rows.length !== 0) return fail();
  const measureIndexes = columns.flatMap((column, index) =>
    column.role === "measure" ? [index] : [],
  );
  const hasMeasureValue = rows.some((row) =>
    measureIndexes.some((index) => row.cells[index] !== null),
  );
  if (
    (value.state === "ready" && (!rows.length || !hasMeasureValue)) ||
    (value.state === "all_measures_null" && (!rows.length || hasMeasureValue))
  )
    return fail();
  return {
    contract_version: value.contract_version as SqlAnalysisPresentation["contract_version"],
    state: value.state as SqlAnalysisPresentation["state"],
    operation: value.operation as SqlAnalysisPresentation["operation"],
    answer: value.answer,
    period: value.period,
    filters: value.filters as string[],
    universe: value.universe as string[],
    limitations: value.limitations as string[],
    columns,
    rows,
    evidence_digest: value.evidence_digest as string,
  };
}

export function decodeSqlAnalysisResponse(value: unknown): AIQuestionResponse {
  const fail = (): never => {
    throw new Error("Resposta Text-to-SQL inválida.");
  };
  if (
    !isRecord(value) ||
    Object.keys(value).some(
      (key) =>
        ![
          "correlation_id",
          "audit_reference",
          "status",
          "evidence",
          "presentation",
          "clarification",
          "unsupported_reason",
          "continuation_token",
        ].includes(key),
    ) ||
    !/^[a-f0-9]{32}$/.test(String(value.correlation_id))
  )
    return fail();
  const continuationToken = value.continuation_token;
  if (continuationToken != null && !isText(continuationToken, 16000)) return fail();
  if (value.status === "answered") {
    const evidence = value.evidence;
    if (
      !isRecord(evidence) ||
      typeof value.audit_reference !== "string" ||
      !/^[a-f0-9]{32}$/.test(value.audit_reference) ||
      typeof evidence.batch_ref !== "string" ||
      !evidence.batch_ref.startsWith("gold-csv-v2:") ||
      evidence.batch_ref.length > 200 ||
      typeof evidence.evidence_digest !== "string" ||
      !/^[a-f0-9]{64}$/.test(evidence.evidence_digest) ||
      !Array.isArray(evidence.columns) ||
      !Array.isArray(evidence.rows) ||
      !(
        evidence.source_table === (
          ["network.equivalent_interruption_duration", "network.equivalent_interruption_frequency"].includes(String(evidence.metric_id))
            ? "gold_v2.indicadores_dec_fec"
            : evidence.metric_id === "service.attendance"
              ? "gold_v2.atendimentos_uc"
              : evidence.metric_id === "service.satisfaction"
                ? "gold_v2.atendimentos_uc"
              : evidence.metric_id === "service.accumulated_attendance"
                ? "gold_v2.visao_360_uc"
              : evidence.metric_id === "energy.gd_units"
                ? "gold_v2.variacao_consumo_uc"
              : evidence.metric_id === "service.accumulated_satisfaction"
                ? "gold_v2.atendimentos_uc"
              : "gold_v2.diagnostico_receita"
        ) ||
        (evidence.metric_id === "billing.revenue" &&
          evidence.source_table === "gold_v2.consumo_receita_bairro")
      )
    )
      return fail();
    const evidenceColumns = evidence.columns as unknown[];
    const evidenceRows = evidence.rows as unknown[];
    const continuityMetric = [
      "network.equivalent_interruption_duration",
      "network.equivalent_interruption_frequency",
    ].includes(String(evidence.metric_id));
    const presentation = decodeSqlAnalysisPresentation(value.presentation);
    const hasGrowth = presentation.columns.some(
      (column) => column.semantic_id === "period_0_growth_percent",
    );
    const expectedPresentationVersion =
      evidence.evidence_contract_version === "text-to-sql-f1-evidence-v8"
        ? "text-to-sql-f1-presentation-v7"
        :
      evidence.evidence_contract_version === "text-to-sql-f1-evidence-v9"
        ? "text-to-sql-f1-presentation-v8"
        :
      evidence.evidence_contract_version === "text-to-sql-f1-evidence-v7"
        ? "text-to-sql-f1-presentation-v6"
        :
      evidence.evidence_contract_version === "text-to-sql-f1-evidence-v6"
        ? "text-to-sql-f1-presentation-v5"
        : evidence.evidence_contract_version === "text-to-sql-f1-evidence-v5"
        ? "text-to-sql-f1-presentation-v4"
        : evidence.evidence_contract_version === "text-to-sql-f1-evidence-v4"
        ? "text-to-sql-f1-presentation-v3"
        : evidence.evidence_contract_version === "text-to-sql-f1-evidence-v2" ||
      (evidence.evidence_contract_version === "text-to-sql-f1-evidence-v3" && hasGrowth)
        ? "text-to-sql-f1-presentation-v2"
        : "text-to-sql-f1-presentation-v1";
    if (
      (evidence.evidence_contract_version != null &&
        ![
          "text-to-sql-f1-evidence-v1",
          "text-to-sql-f1-evidence-v2",
          "text-to-sql-f1-evidence-v3",
          "text-to-sql-f1-evidence-v4",
          "text-to-sql-f1-evidence-v5",
          "text-to-sql-f1-evidence-v6",
          "text-to-sql-f1-evidence-v7",
          "text-to-sql-f1-evidence-v8",
          "text-to-sql-f1-evidence-v9",
        ].includes(String(evidence.evidence_contract_version))) ||
      (continuityMetric !== (evidence.evidence_contract_version === "text-to-sql-f1-evidence-v5")) ||
      (continuityMetric
        ? !["certified", "observed_uncertified"].includes(String(evidence.coverage_quality))
        : evidence.coverage_quality !== "certified") ||
      (evidence.coverage_quality === "observed_uncertified" && (() => {
        const interpretation = evidence.interpretation;
        const filterList = isRecord(interpretation) ? interpretation.filters : null;
        const periods = isRecord(interpretation) ? interpretation.periods : null;
        return !Array.isArray(filterList) || filterList.length !== 1 ||
          !isRecord(filterList[0]) || filterList[0].dimension_id !== "network.feeder" ||
          filterList[0].operator !== "eq" || !Array.isArray(filterList[0].values) ||
          filterList[0].values.length !== 1 || !Array.isArray(periods) || periods.length !== 1 ||
          !presentation.limitations.includes("Valores observados; cobertura do alimentador não certificada.");
      })()) ||
      presentation.contract_version !== expectedPresentationVersion ||
      (evidence.metric_id !== "billing.revenue" && evidence.metric_id !== "energy.consumption" && evidence.metric_id !== "service.attendance" && evidence.metric_id !== "service.satisfaction" && evidence.metric_id !== "service.accumulated_attendance" && evidence.metric_id !== "energy.gd_units" && evidence.metric_id !== "service.accumulated_satisfaction" && !continuityMetric) ||
      presentation.evidence_digest !== evidence.evidence_digest ||
      presentation.columns.length !== evidenceColumns.length ||
      presentation.rows.length !== evidenceRows.length ||
      presentation.columns.some((column, index) => {
        const sourceColumn = evidenceColumns[index];
        return (
          !isRecord(sourceColumn) ||
          column.key !== sourceColumn.name ||
          column.role !== sourceColumn.role ||
          column.unit !== sourceColumn.unit
        );
      }) ||
      presentation.rows.some((row, index) => {
        const sourceRow = evidenceRows[index];
        return (
          !Array.isArray(sourceRow) ||
          sourceRow.length !== row.cells.length ||
          row.cells.some((cell, cellIndex) => cell !== sourceRow[cellIndex])
        );
      })
    )
      return fail();
    const rawVisualization = sqlAnalysisVisualization(presentation);
    const analysisContext: AIAnalysisContext = {
      batch_reference: evidence.batch_ref,
      metric: String(evidence.metric_id),
      metric_label:
        evidence.metric_id === "service.accumulated_attendance"
          ? "Chamados no histórico acumulado"
          : evidence.metric_id === "energy.gd_units"
          ? "UCs com GD cadastrada"
          : evidence.metric_id === "service.accumulated_satisfaction"
          ? "Nota média de satisfação no histórico"
          : evidence.metric_id === "service.attendance"
          ? "Protocolos de atendimento"
          : evidence.metric_id === "service.satisfaction"
            ? "Nota média de satisfação"
          : evidence.metric_id === "network.equivalent_interruption_duration"
            ? "DEC"
            : evidence.metric_id === "network.equivalent_interruption_frequency"
              ? "FEC"
          : evidence.metric_id === "energy.consumption"
            ? "Consumo medido"
            : "Faturamento",
      unit:
        evidence.metric_id === "service.satisfaction"
          ? "pontos"
          : evidence.metric_id === "service.attendance" || evidence.metric_id === "service.accumulated_attendance"
          ? "protocolos"
          : evidence.metric_id === "energy.gd_units"
          ? "UCs"
          : evidence.metric_id === "service.accumulated_satisfaction"
          ? "pontos"
          : evidence.metric_id === "network.equivalent_interruption_duration"
            ? "horas por UC"
            : evidence.metric_id === "network.equivalent_interruption_frequency"
              ? "interrupções por UC"
          : evidence.metric_id === "energy.consumption"
            ? "kWh"
            : "R$",
      period: presentation.period,
      filters: {},
    };
    const base = decodeAIQuestionResponse({
      contract_version: "v1",
      correlation_id: value.correlation_id,
      audit_reference: value.audit_reference,
      status: "answered",
      answer: presentation.answer,
      evidence: [
        {
          source: "gold.local",
          description: "Faturamento na publicação Gold v2.",
          is_demo: false,
        },
      ],
      limitations: [
        ...presentation.limitations,
        ...(presentation.state === "ready"
          ? []
          : [
              presentation.state === "empty"
                ? "A consulta não retornou linhas para o recorte."
                : "As linhas retornadas não contêm valores de faturamento disponíveis.",
            ]),
      ],
      analysis_context: analysisContext,
      continuation_token: continuationToken as string | null | undefined,
      ...(rawVisualization ? { visualization: rawVisualization } : {}),
    });
    return { ...base, sql_analysis_mode: true, sql_presentation: presentation };
  }
  if (value.status === "needs_clarification") {
    if (
      !isRecord(value.clarification) ||
      typeof value.audit_reference !== "string" ||
      !/^[a-f0-9]{32}$/.test(value.audit_reference) ||
      !isText(value.clarification.question, 1000) ||
      (value.evidence !== undefined && value.evidence !== null) ||
      (value.presentation !== undefined && value.presentation !== null) ||
      (value.unsupported_reason !== undefined &&
        value.unsupported_reason !== null)
    )
      return fail();
    return {
      ...decodeAIQuestionResponse({
        contract_version: "v1",
        correlation_id: value.correlation_id,
        audit_reference: value.audit_reference,
        status: "needs_clarification",
        message: value.clarification.question,
        evidence: [],
        limitations: [],
        continuation_token: continuationToken,
      }),
      sql_analysis_mode: true,
    };
  }
  if (value.status === "unsupported") {
    if (
      !isRecord(value.unsupported_reason) ||
      typeof value.audit_reference !== "string" ||
      !/^[a-f0-9]{32}$/.test(value.audit_reference) ||
      !isText(value.unsupported_reason.message, 1000) ||
      ![
        "metric_outside_f1",
        "operation_outside_f1",
        "source_outside_f1",
      ].includes(String(value.unsupported_reason.code)) ||
      (value.evidence !== undefined && value.evidence !== null) ||
      (value.presentation !== undefined && value.presentation !== null) ||
      (value.clarification !== undefined && value.clarification !== null)
    )
      return fail();
    return {
      ...decodeAIQuestionResponse({
        contract_version: "v1",
        correlation_id: value.correlation_id,
        audit_reference: value.audit_reference,
        status: "refused",
        message: value.unsupported_reason.message,
        error: { code: "unsupported_operation", retryable: false },
        evidence: [],
        limitations: [],
        continuation_token: continuationToken,
      }),
      sql_analysis_mode: true,
    };
  }
  return fail();
}

export function decodeAIQuestionErrorResponse(
  value: unknown,
): AIQuestionErrorResponse | null {
  if (
    !isRecord(value) ||
    value.contract_version !== "v1" ||
    value.status !== "error" ||
    typeof value.correlation_id !== "string" ||
    !CORRELATION_ID.test(value.correlation_id) ||
    !isText(value.message, 300)
  ) {
    return null;
  }
  const error = decodeError(value.error);
  if (!error) return null;
  return {
    contract_version: "v1",
    status: "error",
    correlation_id: value.correlation_id,
    message: value.message,
    error,
  };
}
