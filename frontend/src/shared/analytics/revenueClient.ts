import { apiClient } from "@/shared/api/client";
import { decodeRevenueEnvelope, type RevenueEnvelope } from "./revenueContract";

export type RevenueRequest = {
  competencia_inicio: string;
  competencia_fim: string;
  municipio: string;
  bairro?: string;
  classe: string;
  alimentador?: string;
  group_by: "municipio" | "bairro" | "classe";
};

export class RevenueContextError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "RevenueContextError";
  }
}

export function validateRevenueContext(
  envelope: RevenueEnvelope,
  request: RevenueRequest,
) {
  const { metadata, data } = envelope;
  if (
    metadata.period.start !== request.competencia_inicio ||
    metadata.period.end !== request.competencia_fim ||
    metadata.filters.municipio !== (request.municipio || null) ||
    metadata.filters.classe !== (request.classe || null) ||
    metadata.filters.bairro !== (request.bairro || null) ||
    metadata.filters.alimentador !== (request.alimentador || null) ||
    data.breakdown.dimension !== request.group_by
  ) {
    throw new RevenueContextError(
      "A API retornou Receita para um recorte diferente do solicitado.",
    );
  }
  return envelope;
}

export async function fetchRevenue(
  request: RevenueRequest,
  signal?: AbortSignal,
) {
  const params = new URLSearchParams({
    competencia_inicio: request.competencia_inicio,
    competencia_fim: request.competencia_fim,
    group_by: request.group_by,
  });
  for (const key of ["municipio", "bairro", "classe", "alimentador"] as const) {
    const value = request[key];
    if (value) params.set(key, value);
  }
  const raw = await apiClient<unknown>(`/api/v1/revenue?${params}`, { signal });
  return decodeRevenueEnvelope(raw);
}

export async function fetchRevenueForContext(
  request: RevenueRequest,
  signal?: AbortSignal,
) {
  return validateRevenueContext(await fetchRevenue(request, signal), request);
}
