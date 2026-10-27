import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import MetricCard from "./MetricCard";
import { calculateSyntheticPanorama } from "../analytics/syntheticData";

const metric = calculateSyntheticPanorama({
  periodo: "2024-04",
  comparacao: "anterior",
  municipio: "todos",
  classe: "todas",
}).metricas.energiaConsumida;

describe("MetricCard", () => {
  it.each([
    [1000000, "1 GWh"],
    [1000000000, "1.000 GWh"],
    [90000, "90.000 kWh"],
  ])("converte %s kWh corretamente", (value, label) => {
    render(<MetricCard metric={{ ...metric, valorAtual: value as number }} />);
    expect(screen.getByText(label as string)).toBeVisible();
  });
  it("não transforma percentual indisponível em zero", () => {
    render(
      <MetricCard
        metric={{ ...metric, variacaoPercentual: null, variacaoAbsoluta: null }}
      />,
    );
    expect(screen.getByText("Comparação indisponível")).toBeVisible();
    expect(screen.queryByText("0,00%")).not.toBeInTheDocument();
  });
  it("mantém zero como uma comparação válida", () => {
    render(
      <MetricCard
        metric={{ ...metric, variacaoPercentual: 0, variacaoAbsoluta: 0 }}
      />,
    );
    expect(screen.getByText("0,00%")).toBeVisible();
  });
});
