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
  const payload = {
    ...request,
    ...(expected ? { expected_publication: expected } : {}),
  };
  let rawResponse: unknown;
  const controller = new AbortController();
  let timedOut = false;
  const timeout = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, 40_000);
  try {
    rawResponse = await apiClient<unknown>("/api/v1/ai/questions", {
      method: "POST",
      signal: controller.signal,
      body: JSON.stringify(payload),
    });
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

    const publicError = decodeAIQuestionErrorResponse(error.data);
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
    return decodeAIQuestionResponse(rawResponse);
  } catch {
    throw new AIChatApiError(
      "Não foi possível apresentar a resposta. Tente uma nova pergunta em instantes.",
      false,
    );
  }
}
