export type AIConversationTurn = {
  role: "user" | "assistant";
  content: string;
};

export type AIQuestionRequest = {
  contract_version: "v1";
  question: string;
  context: AIConversationTurn[];
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

export type AIAnalysisContext = {
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
    for (const field of ["metric", "metric_label", "unit", "period"] as const) {
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

  const auditReference = value.audit_reference;
  if (auditReference != null && !isText(auditReference, 200)) {
    throw new Error("Resposta inválida do serviço.");
  }
  const modelTier = value.model_tier;
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
  };
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
