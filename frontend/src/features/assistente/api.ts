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
      body: JSON.stringify(request),
    });
  } catch (error) {
    if (timedOut) {
      throw new AIChatApiError(
        "A consulta demorou mais que o esperado. Tente novamente em instantes.",
        true,
      );
    }
    if (!(error instanceof ApiError)) throw error;

    const accessMessages: Record<number, string> = {
      401: "Sua sessão expirou. Entre novamente para continuar.",
      403: "Seu acesso não permite consultar esses dados.",
      409: "Os dados disponíveis mudaram. Envie uma nova pergunta para consultar a versão atual.",
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

  try {
    return decodeAIQuestionResponse(rawResponse);
  } catch {
    throw new AIChatApiError(
      "Não foi possível apresentar a resposta. Tente uma nova pergunta em instantes.",
      false,
    );
  }
}
