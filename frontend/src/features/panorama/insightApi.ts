import { ApiError, apiClient } from "../../shared/api/client";
import type {
  PanoramaData,
  PanoramaFilters,
} from "../../shared/analytics/types";
import {
  decodePanoramaInsight,
  decodePanoramaInsightError,
  type PanoramaInsightEnvelope,
} from "./insightContract";

export class PanoramaInsightApiError extends Error {
  readonly retryable: boolean;
  readonly status?: number;
  readonly code?: string;

  constructor(
    message: string,
    retryable: boolean,
    status?: number,
    code?: string,
  ) {
    super(message);
    this.name = "PanoramaInsightApiError";
    this.retryable = retryable;
    this.status = status;
    this.code = code;
  }
}

export async function requestPanoramaInsight(
  filters: PanoramaFilters,
  data: PanoramaData,
  signal: AbortSignal,
): Promise<PanoramaInsightEnvelope> {
  let response: unknown;
  try {
    response = await apiClient<unknown>("/api/v1/ai/insights", {
      method: "POST",
      signal,
      body: JSON.stringify({
        filters,
        loteVersao: data.loteVersao,
        ...(data.origem?.kind === "gold" && data.origem.fingerprint
          ? { fingerprint: data.origem.fingerprint }
          : {}),
      }),
    });
  } catch (error) {
    if (error instanceof ApiError) {
      const publicError = decodePanoramaInsightError(error.data);
      if (publicError) {
        throw new PanoramaInsightApiError(
          publicError.message,
          publicError.error.retryable,
          error.status,
          publicError.error.code,
        );
      }
      if (error.kind === "network") {
        throw new PanoramaInsightApiError(
          "Não foi possível conectar ao serviço de insight. Verifique a conexão e tente novamente.",
          true,
          error.status,
        );
      }
      throw new PanoramaInsightApiError(
        "Não foi possível concluir a interpretação deste recorte.",
        false,
        error.status,
      );
    }
    throw error;
  }

  try {
    const result = decodePanoramaInsight(
      response,
      filters,
      data.loteVersao,
      data.dataAtualizacao,
      data.origem?.isDemo ?? true,
    );
    if (
      data.origem?.kind === "gold" &&
      data.origem.fingerprint &&
      result.source.fingerprint !== data.origem.fingerprint
    )
      throw new Error("A publicação do insight mudou.");
    const metric =
      data.origem?.kind === "gold"
        ? data.metricas.receitaFaturada
        : data.metricas.energiaFaturada;
    if (
      result.insight.status === "answered" &&
      (result.metric.id !== metric.id ||
        result.insight.context.unit !== metric.unidade ||
        result.insight.observation.values[0]?.value !== metric.valorAtual)
    )
      throw new Error("O insight não corresponde aos números exibidos.");
    return result;
  } catch {
    throw new PanoramaInsightApiError(
      "O serviço retornou um insight incompatível com o recorte atual.",
      false,
    );
  }
}
