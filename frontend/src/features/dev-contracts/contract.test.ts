import { expect, it } from "vitest";
import { ContractError, decodeKpisEnvelope } from "./contract";

const validEnvelope = {
  data: {
    metrics: [
      {
        id: "billed_amount",
        label: "Valor faturado",
        value: 182,
        unit: "BRL",
        status: "available",
        limitations: [],
      },
    ],
  },
  metadata: {
    contract_version: "1.0.0",
    status: "available",
    period: { start: "2025-01", end: "2025-02", granularity: "month" },
    filters: {
      municipio: null,
      bairro: null,
      classe: null,
      alimentador: null,
    },
    source: {
      kind: "synthetic",
      version: "dev01-v1",
      is_demo: true,
      updated_at: "2026-10-20T00:00:00Z",
    },
    limitations: [],
  },
};

it("decodifica o envelope KPIs do desenho sem alterar zero ou metadados", () => {
  const decoded = decodeKpisEnvelope(validEnvelope);
  expect(decoded.data.metrics[0]?.value).toBe(182);
  expect(decoded.metadata.source.is_demo).toBe(true);
});

it("rejeita métricas com valor não finito", () => {
  const malformed = structuredClone(validEnvelope);
  malformed.data.metrics[0]!.value = Number.POSITIVE_INFINITY;
  expect(() => decodeKpisEnvelope(malformed)).toThrow(
    /data\.metrics\[0\]\.value/,
  );
});

const invalidCases: Array<[string, (value: typeof validEnvelope) => void]> = [
  [
    "versão diferente",
    (value) => {
      value.metadata.contract_version = "2.0.0";
    },
  ],
  [
    "granularidade diferente",
    (value) => {
      value.metadata.period.granularity = "day";
    },
  ],
  [
    "fonte não sintética",
    (value) => {
      value.metadata.source.kind = "gold";
    },
  ],
  [
    "fonte marcada como real",
    (value) => {
      value.metadata.source.is_demo = false;
    },
  ],
  [
    "data inválida",
    (value) => {
      value.metadata.source.updated_at = "yesterday";
    },
  ],
  [
    "estado available sem valor",
    (value) => {
      value.data.metrics[0]!.value = null as never;
    },
  ],
  [
    "estado empty com valor",
    (value) => {
      value.data.metrics[0]!.status = "empty";
    },
  ],
];

it.each(invalidCases)(
  "rejeita contrato demo inconsistente: %s",
  (_label, mutate) => {
    const malformed = structuredClone(validEnvelope);
    mutate(malformed);
    expect(() => decodeKpisEnvelope(malformed)).toThrow(ContractError);
  },
);

it("rejeita ids de métrica duplicados", () => {
  const malformed = structuredClone(validEnvelope);
  malformed.data.metrics.push({ ...malformed.data.metrics[0]! });
  expect(() => decodeKpisEnvelope(malformed)).toThrow(/id duplicado/);
});
