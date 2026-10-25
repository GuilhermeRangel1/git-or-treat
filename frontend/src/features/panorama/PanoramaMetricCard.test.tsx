import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { KpiMetric } from "../../shared/analytics/types";
import PanoramaMetricCard from "./PanoramaMetricCard";

const metric: KpiMetric = {
  id: "rec_fat",
  nome: "Receita Faturada",
  categoria: "financeiro",
  tipoGrandeza: "faturado",
  valorAtual: 200,
  valorAnterior: 0,
  variacaoAbsoluta: 200,
  variacaoPercentual: null,
  baseZero: true,
  unidade: "R$",
  definicao: "Valor das contas emitidas.",
  formula: "Soma dos valores faturados.",
};

describe("PanoramaMetricCard", () => {
  it("distingue base anterior zero, ausência de dados e comparação desativada", () => {
    const { rerender } = render(
      <PanoramaMetricCard
        metric={metric}
        title="Valor faturado"
        period="2024-04"
        comparison="anterior"
      />,
    );
    expect(screen.getByText("N/D · Base anterior zero")).toBeVisible();
    expect(screen.queryByText("Sem comparação")).not.toBeInTheDocument();
    expect(screen.getByRole("article")).not.toHaveTextContent(/NaN|Infinity/);

    const noPrevious = { ...metric, baseZero: false, valorAnterior: null };
    rerender(
      <PanoramaMetricCard
        metric={noPrevious}
        title="Valor faturado"
        period="2024-04"
        comparison="ano_anterior"
      />,
    );
    expect(
      screen.getByText("Sem dados no período de comparação"),
    ).toBeVisible();

    rerender(
      <PanoramaMetricCard
        metric={noPrevious}
        title="Valor faturado"
        period="2024-04"
        comparison="nenhuma"
      />,
    );
    expect(screen.getByText("Sem comparação")).toBeVisible();
    expect(screen.queryByText("Sem dados no período de comparação")).toBeNull();
  });

  it("identifica comparação incompleta e preserva um valor positivo de centavos", () => {
    render(
      <PanoramaMetricCard
        metric={{
          ...metric,
          valorAtual: 0.25,
          valorAnterior: 200,
          variacaoPercentual: -99.875,
          baseZero: false,
        }}
        title="Valor faturado"
        period="2024-05"
        comparison="anterior"
        comparisonUnavailable
      />,
    );
    expect(screen.getByText(/R\$\s*0,25/)).toBeVisible();
    expect(
      screen.getByText("Comparação indisponível · período incompleto"),
    ).toBeVisible();
    expect(screen.queryByText(/99,88%/)).not.toBeInTheDocument();
  });
});
