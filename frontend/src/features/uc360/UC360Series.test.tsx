import { render, screen } from "@testing-library/react";
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
    screen.getByRole("img", { name: /Gráfico de consumo medido/ }),
  ).toBeInTheDocument();
  expect(container.querySelectorAll("polyline")).toHaveLength(2);
  expect(container.querySelectorAll("circle")).toHaveLength(5);
  expect(container.querySelector("title")?.textContent).toContain("0 kWh");
});
