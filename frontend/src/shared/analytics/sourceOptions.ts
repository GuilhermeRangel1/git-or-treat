import { useQuery } from "@tanstack/react-query";
import { apiClient } from "../api/client";

export type SourceOptions = {
  competencias: string[];
  municipio: string[];
  bairro: string[];
  classe: string[];
  alimentador: string[];
  bairros: Array<{ municipio: string | null; bairro: string | null }>;
};
type OptionsEnvelope = {
  data: SourceOptions;
  source: {
    kind: string;
    version: string;
    is_demo: boolean;
    updated_at: string;
  };
  limitations: string[];
};

export function decodeSourceOptions(value: unknown): OptionsEnvelope {
  function object(input: unknown): Record<string, unknown> {
    if (!input || typeof input !== "object" || Array.isArray(input))
      throw new Error("Catálogo analítico inválido.");
    return input as Record<string, unknown>;
  }
  function strings(input: unknown): string[] {
    if (!Array.isArray(input) || input.some((v) => typeof v !== "string"))
      throw new Error("Opções analíticas inválidas.");
    return input as string[];
  }
  const root = object(value),
    data = object(root.data),
    source = object(root.source);
  const competencias = strings(data.competencias);
  if (
    competencias.some((v) => !/^(?!0000)\d{4}-(0[1-9]|1[0-2])$/.test(v)) ||
    competencias.some((v, i) => i > 0 && competencias[i - 1] >= v) ||
    typeof source.kind !== "string" ||
    typeof source.version !== "string" ||
    typeof source.is_demo !== "boolean" ||
    typeof source.updated_at !== "string" ||
    !Number.isFinite(Date.parse(source.updated_at)) ||
    !Array.isArray(data.bairros)
  )
    throw new Error("Catálogo analítico inválido.");
  const bairros = data.bairros.map((v) => {
    const row = object(v);
    if (
      (row.municipio !== null && typeof row.municipio !== "string") ||
      (row.bairro !== null && typeof row.bairro !== "string")
    )
      throw new Error("Bairro inválido no catálogo.");
    return row as { municipio: string | null; bairro: string | null };
  });
  return {
    data: {
      competencias,
      municipio: strings(data.municipio),
      bairro: strings(data.bairro),
      classe: strings(data.classe),
      alimentador: strings(data.alimentador),
      bairros,
    },
    source: source as OptionsEnvelope["source"],
    limitations: strings(root.limitations),
  };
}

export function useSourceOptions() {
  return useQuery({
    queryKey: ["analytics", "options"],
    queryFn: async ({ signal }) =>
      decodeSourceOptions(
        await apiClient<unknown>("/api/v1/analytics/options", { signal }),
      ),
    staleTime: 30_000,
    retry: false,
  });
}
