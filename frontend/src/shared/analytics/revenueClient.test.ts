import { expect, it } from "vitest";
import type { RevenueEnvelope } from "./revenueContract";
import { validateRevenueContext } from "./revenueClient";

const request = {
  competencia_inicio: "2025-01",
  competencia_fim: "2025-03",
  municipio: "Recife",
  bairro: "",
  classe: "Comercial",
  alimentador: "",
  group_by: "bairro" as const,
};

const envelope = {
  metadata: {
    period: { start: "2025-01", end: "2025-03" },
    filters: {
      municipio: "Recife",
      bairro: null,
      classe: "Comercial",
      alimentador: null,
    },
  },
  data: { breakdown: { dimension: "bairro" } },
} as unknown as RevenueEnvelope;

it("accepts Revenue only when the echoed period, filters and grouping match the request", () => {
  expect(validateRevenueContext(envelope, request)).toBe(envelope);
  expect(() =>
    validateRevenueContext(envelope, { ...request, municipio: "Olinda" }),
  ).toThrow("recorte diferente");
  expect(() =>
    validateRevenueContext(envelope, {
      ...request,
      competencia_fim: "2025-02",
    }),
  ).toThrow("recorte diferente");
});
