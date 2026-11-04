import { ApiError, apiClient } from "../../shared/api/client";
import { markGoldPublicationStale } from "../../shared/analytics/goldPublication";
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

/** Revalida a análise já produzida sem voltar ao modelo nem consultar medidas. */
export async function verifyPanoramaInsightContext(
  data: PanoramaData,
  signal: AbortSignal,
  neighborhood = false,
): Promise<void> {
  if (!data.origem?.fingerprint)
    throw new PanoramaInsightApiError(
      "A publicação não pôde ser conferida.",
      false,
    );
  const controller = new AbortController();
  const cancel = () => controller.abort();
  if (signal.aborted) cancel();
  signal.addEventListener("abort", cancel, { once: true });
  const timer = setTimeout(cancel, 8_000);
  try {
    const result = await apiClient<{ authorized?: boolean }>(
      "/api/v1/ai/visualizations/verify",
      {
        method: "POST",
        signal: controller.signal,
        body: JSON.stringify({
          metric: "billing.revenue",
          dimension_ids: [
            "geography.municipality",
            "customer.consumption_class",
            ...(neighborhood ? ["geography.neighborhood"] : []),
          ],
          expected_publication: {
            lote: data.loteVersao,
            fingerprint: data.origem.fingerprint,
          },
        }),
      },
    );
    if (result?.authorized !== true)
      throw new PanoramaInsightApiError(
        "O acesso à análise não foi confirmado.",
        false,
        403,
      );
  } catch (error) {
    if (signal.aborted) throw error;
    if (error instanceof PanoramaInsightApiError) throw error;
    const status = error instanceof ApiError ? error.status : 0;
    if (status === 409) markGoldPublicationStale();
    throw new PanoramaInsightApiError(
      "Não foi possível verificar a atualização da análise agora.",
      !status || status >= 500,
      status,
      status === 409 ? "invalid_context" : undefined,
    );
  } finally {
    clearTimeout(timer);
    signal.removeEventListener("abort", cancel);
  }
}

export async function requestPanoramaInsight(
  filters: PanoramaFilters,
  data: PanoramaData,
  signal: AbortSignal,
): Promise<PanoramaInsightEnvelope> {
  let response: unknown;
  const controller = new AbortController();
  let timedOut = false;
  const cancel = () => controller.abort();
  if (signal.aborted) cancel();
  signal.addEventListener("abort", cancel, { once: true });
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, 70_000);
  try {
    response = await apiClient<unknown>("/api/v1/ai/insights", {
      method: "POST",
      signal: controller.signal,
      body: JSON.stringify({
        filters,
        loteVersao: data.loteVersao,
        ...(data.origem?.kind === "gold" && data.origem.fingerprint
          ? { fingerprint: data.origem.fingerprint }
          : {}),
      }),
    });
  } catch (error) {
    if (timedOut)
      throw new PanoramaInsightApiError(
        "A interpretação demorou mais que o esperado. Os dados do recorte continuam disponíveis; tente novamente.",
        true,
        504,
      );
    if (signal.aborted) throw error;
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
  } finally {
    clearTimeout(timer);
    signal.removeEventListener("abort", cancel);
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
    if (
      result.insight.status === "answered" &&
      filters.comparacao !== "nenhuma" &&
      metric.valorAnterior != null &&
      result.insight.observation.values[1]?.value !== metric.valorAnterior
    )
      throw new Error(
        "O insight não corresponde ao período de comparação exibido.",
      );
    const composition = result.analysis.composicaoAtual;
    if (composition) {
      const expectedDimension =
        filters.municipio === "todos"
          ? "municipio"
          : filters.classe === "todas"
            ? "classe"
            : "bairro";
      if (
        composition.dimension !== expectedDimension ||
        metric.valorAtual == null ||
        metric.valorAtual <= 0 ||
        composition.valor > metric.valorAtual ||
        Math.abs(
          (composition.valor / metric.valorAtual) * 100 -
            composition.participacaoPercentual,
        ) > 0.051 ||
        !result.insight.observation.values.some(
          (value) =>
            value.value === composition.valor &&
            value.label ===
              `Maior receita observada no mês · ${composition.segmento}`,
        )
      )
        throw new Error("A composição não corresponde ao recorte exibido.");
    }
    return result;
  } catch {
    throw new PanoramaInsightApiError(
      "O serviço retornou um insight incompatível com o recorte atual.",
      false,
    );
  }
}
