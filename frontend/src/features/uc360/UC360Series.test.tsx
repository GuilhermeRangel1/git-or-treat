import { fireEvent, render, screen, within } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import UC360Series from "./UC360Series";

it("interrompe a linha em meses ausentes ou nulos e preserva o zero", () => {
  const data = {
    items: [
      { competencia: "2025-01", measured_energy_kwh: 0 },
      { competencia: "2025-02", measured_energy_kwh: 10 },
      { competencia: "2025-03", measured_energy_kwh: null },
      { competencia: "2025-04", measured_energy_kwh: 20 },
      { competencia: "2025-06", measured_energy_kwh: 30 },
      { competencia: "2025-07", measured_energy_kwh: 40 },
    ],
  };
  const { container } = render(
    <UC360Series data={data} pending={false} error={null} onRetry={vi.fn()} />,
  );
  expect(
    screen.getByRole("img", { name: /Consumo medido mensal em kWh/ }),
  ).toBeInTheDocument();
  expect(container.querySelectorAll("path")).toHaveLength(2);
  expect(container.querySelectorAll("circle")).toHaveLength(5);
  expect(container.querySelector("title")?.textContent).toContain("0 kWh");
});

it("compara cada competência com o mesmo mês do ano anterior, distinguindo zero e ausência", () => {
  render(
    <UC360Series
      data={{
        items: [
          { competencia: "2025-01", measured_energy_kwh: 50 },
          { competencia: "2025-02", measured_energy_kwh: null },
          { competencia: "2025-03", measured_energy_kwh: 30 },
        ],
      }}
      previous={{
        data: {
          items: [
            { competencia: "2024-01", measured_energy_kwh: 0 },
            { competencia: "2024-02", measured_energy_kwh: 12 },
          ],
        },
        pending: false,
        error: null,
      }}
      pending={false}
      error={null}
      onRetry={vi.fn()}
    />,
  );
  fireEvent.click(screen.getByRole("button", { name: /Ver tabela da série/ }));
  const rows = within(screen.getByRole("table")).getAllByRole("row");
  expect(rows[1]).toHaveTextContent("50 kWh");
  expect(rows[1]).toHaveTextContent("0 kWh");
  expect(rows[2]).toHaveTextContent("Sem dado");
  expect(rows[2]).toHaveTextContent("12 kWh");
  expect(rows[3]).toHaveTextContent("30 kWh");
  expect(rows[3]).toHaveTextContent("Sem dado");
});
