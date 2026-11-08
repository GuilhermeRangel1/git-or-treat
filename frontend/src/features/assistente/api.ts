import {
  getGoldGeneration,
  getGoldPublication,
  goldPublicationKey,
  isGoldPublicationStale,
  markGoldPublicationStale,
} from "@/shared/analytics/goldPublication";
import { ApiError, apiClient } from "@/shared/api/client";
import {
  decodeAIQuestionErrorResponse,
  decodeAIQuestionResponse,
  decodeSqlAnalysisResponse,
  type AIQuestionRequest,
  type AIQuestionResponse,
} from "./contract";

export class AIChatApiError extends Error {
  readonly retryable: boolean;
  readonly status?: number;
  readonly code?: string;
  readonly correlationId?: string;

  constructor(
    message: string,
    retryable: boolean,
    status?: number,
    code?: string,
    correlationId?: string,
  ) {
    super(message);
    this.name = "AIChatApiError";
    this.retryable = retryable;
    this.status = status;
    this.code = code;
    this.correlationId = correlationId;
  }
}

export async function askAIQuestion(
  request: AIQuestionRequest,
  onData?: (response: AIQuestionResponse) => void,
  signal?: AbortSignal,
  strategy: "legacy" | "sql_f1" = "legacy",
): Promise<AIQuestionResponse> {
  const generation = getGoldGeneration();
  const publicationKey = goldPublicationKey();
  const expected = getGoldPublication();
  if (isGoldPublicationStale())
    throw new AIChatApiError(
      "Os dados mudaram. Atualize os dados Gold antes de perguntar.",
      false,
      409,
    );
  const { history_request_id, refresh_context, ...publicRequest } = request;
  const saved =
    strategy === "legacy" && Boolean(history_request_id && request.conversation_id);
  const path =
    strategy === "sql_f1"
      ? saved
        ? `/api/v1/ai/conversations/${encodeURIComponent(request.conversation_id!)}/questions`
        : "/api/v1/ai/sql-analyses"
      : saved
        ? `/api/v1/ai/conversations/${encodeURIComponent(request.conversation_id!)}/questions`
        : "/api/v1/ai/questions";
  const payload = {
    ...(strategy === "sql_f1"
      ? saved
        ? {
            request_id: history_request_id,
            question: request.question,
            strategy: "sql_f1",
            refresh_context: refresh_context ?? false,
            ...(expected ? { expected_publication: expected } : {}),
          }
        : {
            contract_version: "v1",
            question: request.question,
            conversation_id: request.conversation_id,
            continuation_token: request.continuation_token,
          }
      : {
          ...(saved
            ? {
                request_id: history_request_id,
                question: request.question,
                refresh_context: refresh_context ?? false,
              }
            : publicRequest),
          ...(expected ? { expected_publication: expected } : {}),
        }),
  };
  let rawResponse: unknown;
  const controller = new AbortController();
  const abortFromCaller = () => controller.abort();
  if (signal?.aborted) controller.abort();
  else signal?.addEventListener("abort", abortFromCaller, { once: true });
  let timedOut = false;
  const timeout = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, 70_000);
  try {
    rawResponse = await apiClient<unknown>(
      path,
      {
        method: "POST",
        signal: controller.signal,
        body: JSON.stringify(payload),
        ...(onData && strategy === "legacy"
          ? { headers: { Accept: "application/x-ndjson" } }
          : {}),
      },
      onData && strategy === "legacy"
        ? (value) => {
            if (
              generation !== getGoldGeneration() ||
              publicationKey !== goldPublicationKey() ||
              isGoldPublicationStale()
            )
              throw new ApiError("Os dados mudaram durante a consulta.", 409);
            const preview = decodeAIQuestionResponse(value);
            if (
              preview.status !== "answered" ||
              !preview.visualization ||
              preview.continuation_token
            )
              throw new ApiError("Dados progressivos inválidos.", 502);
            onData(preview);
          }
        : undefined,
    );
  } catch (error) {
    if (
      generation !== getGoldGeneration() ||
      publicationKey !== goldPublicationKey()
    )
      throw new AIChatApiError(
        "A consulta anterior foi descartada após a atualização dos dados.",
        false,
        409,
        "superseded_request",
      );
    if (timedOut) {
      throw new AIChatApiError(
        "A consulta demorou mais que o esperado. Tente novamente em instantes.",
        true,
      );
    }
    if (!(error instanceof ApiError)) throw error;

    const publicError = decodeAIQuestionErrorResponse(error.data);
    if (publicError?.error.code === "conversation_conflict") {
      throw new AIChatApiError(
        publicError.message,
        publicError.error.retryable,
        error.status,
        publicError.error.code,
        publicError.correlation_id,
      );
    }
    if (publicError?.error.code === "invalid_continuation") {
      throw new AIChatApiError(
        "O contexto anterior não é mais válido. Inicie uma nova conversa.",
        false,
        error.status,
        publicError.error.code,
        publicError.correlation_id,
      );
    }
    if (error.status === 409) markGoldPublicationStale();
    const accessMessages: Record<number, string> = {
      401: "Sua sessão expirou. Entre novamente para continuar.",
      403: "Seu acesso não permite consultar esses dados.",
      409: "Os dados disponíveis mudaram. Atualize os dados Gold antes de enviar uma nova pergunta.",
      422: "Não foi possível entender a solicitação. Revise a pergunta e envie novamente.",
      429: "Há muitas consultas no momento. Aguarde um pouco antes de enviar outra pergunta.",
    };
    const accessMessage = accessMessages[error.status ?? 0];
    if (accessMessage) {
      throw new AIChatApiError(accessMessage, false, error.status);
    }

    if (publicError) {
      throw new AIChatApiError(
        publicError.message,
        publicError.error.retryable,
        error.status,
        publicError.error.code,
        publicError.correlation_id,
      );
    }

    if (error.kind === "network") {
      throw new AIChatApiError(
        "Não foi possível conectar ao serviço de resposta. Verifique a conexão e tente novamente.",
        true,
        error.status,
      );
    }
    throw new AIChatApiError(
      "Não foi possível concluir a pergunta. Tente novamente mais tarde.",
      false,
      error.status,
    );
  } finally {
    clearTimeout(timeout);
    signal?.removeEventListener("abort", abortFromCaller);
  }

  if (
    generation !== getGoldGeneration() ||
    publicationKey !== goldPublicationKey() ||
    isGoldPublicationStale()
  )
    throw new AIChatApiError(
      "Os dados mudaram durante a consulta. Envie uma nova pergunta.",
      false,
      409,
    );
  try {
    return strategy === "sql_f1"
      ? decodeSqlAnalysisResponse(rawResponse)
      : decodeAIQuestionResponse(rawResponse);
  } catch {
    throw new AIChatApiError(
      "Não foi possível apresentar a resposta. Tente uma nova pergunta em instantes.",
      false,
    );
  }
}
