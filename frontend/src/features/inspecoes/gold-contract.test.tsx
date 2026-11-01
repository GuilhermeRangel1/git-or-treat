import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { decodeDetail, decodeQueue } from "./contract";
import SuspicionDetail from "./SuspicionDetail";

const item = {
  uc_id: "FAKE-GOLD-A",
  municipality: "Cidade fictícia",
  neighborhood: "Centro",
  class_name: "Residencial",
  feeder_id: "FAKE-AL",
  priority: null,
  priority_label: "ALTA - HISTORICO IRREGULAR",
  reason: "ALTA - HISTORICO IRREGULAR",
  potential_recoverable_energy_kwh: null,
  indicators: ["Inspeções anteriores: 2"],
  signals: [],
};
const metadata = {
  contract_version: "1.1.0",
  status: "partial",
  period: { start: "2025-01", end: "2025-02" },
  source: {
    kind: "gold_csv",
    version: "test-v1:hash",
    is_demo: false,
    updated_at: "2026-10-27T10:00:00Z",
  },
  limitations: ["Gold provisória; dicionário pendente."],
};

it("aceita fila Gold com categoria textual e score e estimativa ausentes", () => {
  const result = decodeQueue({
    data: {
      items: [item],
      filter_options: {
        municipio: [],
        bairro: [],
        classe: [],
        alimentador: [],
      },
      summary: {
        total_units: 1,
        highest_priority: null,
        estimated_units: 0,
        unavailable_estimate_units: 1,
      },
    },
    pagination: { page: 1, page_size: 10, total: 1, total_pages: 1 },
    metadata,
  });
  const first = result.data.items[0];
  if (!("priority" in first)) throw new Error("Esperada fila legada");
  expect(first.priority).toBeNull();
  expect(first.priority_label).toBe("ALTA - HISTORICO IRREGULAR");
  expect(result.data.items[0].potential_recoverable_energy_kwh).toBeNull();
});

it("mostra a categoria e o histórico, sem score ou diagnóstico inventados", () => {
  const result = decodeDetail({
    data: {
      ...item,
      rule_version: "gold-csv-v1",
      limitations: [],
      estimate_evidence: {
        baseline_kwh: null,
        observed_kwh: null,
        horizon_months: 1,
        reference: "Sem estimativa Gold",
        unavailable_reason: "Não fornecida",
      },
    },
    metadata,
  });
  render(<SuspicionDetail data={result.data} metadata={result.metadata} />);
  expect(
    screen.getByRole("status", {
      name: "Prioridade categórica: ALTA - HISTORICO IRREGULAR",
    }),
  ).toBeVisible();
  expect(screen.getByText("Inspeções anteriores: 2")).toBeVisible();
  expect(
    screen.getByText(/não confirmam uma nova irregularidade/),
  ).toBeVisible();
  expect(screen.queryByText(/\/ 1/)).not.toBeInTheDocument();
});

it("recusa score nulo sem categoria textual", () => {
  expect(() =>
    decodeDetail({
      data: { ...item, priority_label: null, estimate_evidence: {} },
      metadata,
    }),
  ).toThrow();
});

it("mostra os dois trimestres como comparação proposta, sem alterar a prioridade", () => {
  const result = decodeDetail({
    data: {
      ...item,
      rule_version: "gold-csv-v2",
      limitations: [],
      estimate_evidence: {
        baseline_kwh: null,
        observed_kwh: null,
        horizon_months: null,
        reference: "Sem estimativa",
        unavailable_reason: "Não fornecida",
      },
      consumption_comparison: {
        baseline_start: "2024-08",
        baseline_end: "2024-10",
        recent_start: "2024-11",
        recent_end: "2025-01",
        baseline_kwh: 300,
        recent_kwh: 150,
        change_percent: -50,
        unavailable_reason: null,
      },
    },
    metadata,
  });
  render(<SuspicionDetail data={result.data} metadata={result.metadata} />);
  expect(screen.getByText("Comparação proposta de consumo")).toBeVisible();
  expect(screen.getByText(/-50%/)).toBeVisible();
  expect(
    screen.getByText(/não define a prioridade nem comprova irregularidade/),
  ).toBeVisible();
  expect(
    screen.getByRole("status", {
      name: "Prioridade categórica: ALTA - HISTORICO IRREGULAR",
    }),
  ).toBeVisible();
});
