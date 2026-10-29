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
  try {
    rawResponse = await apiClient<unknown>("/api/v1/ai/questions", {
      method: "POST",
      body: JSON.stringify(request),
    });
  } catch (error) {
    if (!(error instanceof ApiError)) throw error;

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
  }

  try {
    return decodeAIQuestionResponse(rawResponse);
  } catch {
    throw new AIChatApiError(
      "O serviço retornou uma resposta fora do contrato esperado.",
      false,
    );
  }
}
