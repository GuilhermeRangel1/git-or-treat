import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { UC360Comparison } from "./UC360Metrics";
import type { UCOverview } from "./contract";

it("usa cores pelo sinal em deltas e preserva zero neutro", () => {
  const measure = { value: 10, status: "available", limitations: [] };
  const snapshot = {
    competencia: "2025-01",
    measured_energy_kwh: measure,
    billed_energy_kwh: measure,
    billed_amount: measure,
    paid_amount: measure,
  };
  const delta = (value: number) => ({
    delta: value,
    percent_change: value,
    status: "available",
    limitations: [],
  });
  const comparison = {
    initial: snapshot,
    final: { ...snapshot, competencia: "2025-02" },
    measured_energy_kwh: delta(5),
    billed_energy_kwh: delta(-3),
    billed_amount: delta(0),
    paid_amount: delta(0),
  } as UCOverview["data"]["comparison"];
  render(<UC360Comparison comparison={comparison} />);
  expect(screen.getByText("+5 kWh")).toHaveClass("text-success");
  expect(screen.getByText("-3 kWh")).toHaveClass("text-danger");
  expect(screen.getAllByText("R$ 0,00")[0]).toHaveClass("text-content");
});
