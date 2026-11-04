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
  it("omite mensagens repetidas quando não há variação para mostrar", () => {
    const { rerender } = render(
      <PanoramaMetricCard
        metric={metric}
        title="Valor faturado"
        comparison="anterior"
      />,
    );
    expect(screen.queryByText(/Base anterior zero/)).not.toBeInTheDocument();
    expect(screen.getByRole("article")).not.toHaveTextContent(/NaN|Infinity/);

    const noPrevious = { ...metric, baseZero: false, valorAnterior: null };
    rerender(
      <PanoramaMetricCard
        metric={noPrevious}
        title="Valor faturado"
        comparison="ano_anterior"
      />,
    );
    expect(screen.queryByText(/período de comparação/)).not.toBeInTheDocument();

    rerender(
      <PanoramaMetricCard
        metric={noPrevious}
        title="Valor faturado"
        comparison="nenhuma"
      />,
    );
    expect(screen.queryByText(/Sem comparação/)).not.toBeInTheDocument();
  });

  it("omite a mensagem de comparação ausente do cartão", () => {
    render(
      <PanoramaMetricCard
        metric={{
          ...metric,
          valorAnterior: null,
          variacaoPercentual: null,
          baseZero: false,
          statusComparacao: "unavailable",
        }}
        title="Valor faturado"
        comparison="anterior"
      />,
    );

    expect(screen.queryByText(/Comparação não calculada/)).toBeNull();
  });

  it("mantém as ressalvas fora do KPI e colore aumento e queda", () => {
    const { rerender } = render(
      <PanoramaMetricCard
        metric={{
          ...metric,
          valorAtual: 0.25,
          valorAnterior: 200,
          variacaoPercentual: -99.875,
          statusComparacao: "partial",
          baseZero: false,
        }}
        title="Valor faturado"
        comparison="anterior"
      />,
    );
    expect(screen.getByText(/R\$\s*0,25/)).toBeVisible();
    const negative = screen.getByText(/99,88%/);
    expect(negative).toHaveClass("text-[var(--status-danger)]");
    expect(screen.queryByText(/fechamento mensal não declarado/)).toBeNull();
    expect(screen.queryByText(/dados parciais/)).toBeNull();

    rerender(
      <PanoramaMetricCard
        metric={{
          ...metric,
          valorAtual: 300,
          valorAnterior: 200,
          variacaoPercentual: 50,
          variacaoAbsoluta: 100,
          baseZero: false,
        }}
        title="Valor faturado"
        comparison="anterior"
      />,
    );
    expect(screen.getByText(/50%/)).toHaveClass("text-success");
  });
});
