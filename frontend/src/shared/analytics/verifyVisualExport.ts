import { ApiError, apiClient } from "../api/client";
import {
  isGoldPublicationStale,
  markGoldPublicationStale,
} from "./goldPublication";

export interface VisualExportContext {
  metric: string;
  dimension_ids: string[];
  batch_reference?: string;
  expected_publication?: { lote: string; fingerprint: string };
}
export async function verifyVisualExport(
  context: VisualExportContext,
): Promise<boolean> {
  if (isGoldPublicationStale()) return false;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 8_000);
  try {
    const result = await apiClient<{ authorized?: boolean }>(
      "/api/v1/ai/visualizations/verify",
      {
        method: "POST",
        body: JSON.stringify(context),
        signal: controller.signal,
      },
    );
    return result?.authorized === true && !isGoldPublicationStale();
  } catch (error) {
    if (error instanceof ApiError && error.status === 409)
      markGoldPublicationStale();
    return false;
  } finally {
    clearTimeout(timeout);
  }
}
