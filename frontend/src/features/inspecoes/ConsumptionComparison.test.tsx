import { expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import ConsumptionComparison from "./ConsumptionComparison";

it("distingue referência ausente de observação zero", () => {
  render(
    <ConsumptionComparison
      evidence={{
        baseline_kwh: null,
        observed_kwh: 0,
        horizon_months: 1,
        reference: "Fevereiro/2025: referência comparável ausente.",
        unavailable_reason: "Sem referência.",
      }}
    />,
  );
  expect(screen.getByText("Dado indisponível")).toBeVisible();
  expect(screen.getByText("0 kWh/mês")).toBeVisible();
  expect(screen.getByText(/Comparação incompleta/)).toBeVisible();
});

it("preserva observação ausente e mostra a referência disponível", () => {
  render(
    <ConsumptionComparison
      evidence={{
        baseline_kwh: 90,
        observed_kwh: null,
        horizon_months: 1,
        reference: "Leitura ausente em fevereiro/2025.",
        unavailable_reason: "Sem observação.",
      }}
    />,
  );
  expect(screen.getByText("90 kWh/mês")).toBeVisible();
  expect(screen.getByText("Dado indisponível")).toBeVisible();
  expect(screen.queryByText("0 kWh/mês")).not.toBeInTheDocument();
});
