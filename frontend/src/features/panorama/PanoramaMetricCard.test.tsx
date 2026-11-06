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
  it("mostra selo de alta com seta, texto e a variação recebida", () => {
    render(
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

    const badge = screen.getByText(/Em alta/);
    expect(badge).toHaveTextContent("▲ Em alta · +R$ 100 · +50%");
    expect(badge).toHaveClass("text-success");
    expect(screen.getByText("▲")).toHaveAttribute("aria-hidden", "true");
    expect(
      screen.getByRole("article", {
        name: /^Valor faturado: R\$\s300,00\. Em alta · \+R\$ 100 · \+50%$/,
      }),
    ).toBeVisible();
  });

  it("mostra selo de queda e mantém as ressalvas fora do KPI", () => {
    render(
      <PanoramaMetricCard
        metric={{
          ...metric,
          valorAtual: 0.25,
          valorAnterior: 200,
          variacaoAbsoluta: -199.75,
          variacaoPercentual: -99.875,
          statusComparacao: "partial",
          baseZero: false,
        }}
        title="Valor faturado"
        comparison="anterior"
      />,
    );

    expect(screen.getByText(/R\$\s*0,25/)).toBeVisible();
    const badge = screen.getByText(/Em queda/);
    expect(badge).toHaveTextContent("▼ Em queda · −R$ 200 · −99,88%");
    expect(badge).toHaveClass("text-[var(--status-danger)]");
    expect(screen.getByRole("article")).toHaveAccessibleName(/Em queda/);
    expect(screen.queryByText(/fechamento mensal não declarado/)).toBeNull();
    expect(screen.queryByText(/dados parciais/)).toBeNull();
  });

  it.each([0.49, -0.49, 0])(
    "mostra selo estável sem verde nem vermelho para variação de %s%%",
    (variacaoPercentual) => {
      render(
        <PanoramaMetricCard
          metric={{
            ...metric,
            valorAnterior: 200,
            variacaoPercentual,
            baseZero: false,
          }}
          title="Valor faturado"
          comparison="anterior"
        />,
      );

      const badge = screen.getByText(/Estável/);
      expect(badge).toHaveTextContent(/^● Estável$/);
      expect(badge).toHaveClass("text-muted");
      expect(badge).not.toHaveClass("text-success");
      expect(badge).not.toHaveClass("text-[var(--status-danger)]");
      expect(screen.getByRole("article")).toHaveAccessibleName(/Estável/);
    },
  );

  it.each([0.5, -0.5])(
    "deixa de ser estável a partir do limite, com variação de %s%%",
    (variacaoPercentual) => {
      render(
        <PanoramaMetricCard
          metric={{
            ...metric,
            valorAnterior: 200,
            variacaoPercentual,
            baseZero: false,
          }}
          title="Valor faturado"
          comparison="anterior"
        />,
      );

      expect(screen.queryByText(/Estável/)).toBeNull();
      expect(screen.getByRole("article")).toHaveTextContent(
        variacaoPercentual > 0 ? "▲ Em alta" : "▼ Em queda",
      );
    },
  );

  it.each([
    {
      caso: "sem valor anterior",
      override: { valorAnterior: null, variacaoPercentual: 10 },
      comparison: "anterior" as const,
    },
    {
      caso: "sem variação percentual",
      override: { valorAnterior: 200, variacaoPercentual: null },
      comparison: "ano_anterior" as const,
    },
    {
      caso: "com comparação desligada",
      override: { valorAnterior: 200, variacaoPercentual: 10 },
      comparison: "nenhuma" as const,
    },
    {
      caso: "em UCs cadastradas, que não têm histórico",
      override: { id: "ucs_atv", valorAnterior: 200, variacaoPercentual: 10 },
      comparison: "anterior" as const,
    },
  ])("avisa que a comparação está indisponível $caso", (scenario) => {
    render(
      <PanoramaMetricCard
        metric={{ ...metric, baseZero: false, ...scenario.override }}
        title="Valor faturado"
        comparison={scenario.comparison}
      />,
    );

    const notice = screen.getByText("Comparação indisponível neste recorte");
    expect(notice).toHaveClass("text-muted");
    expect(screen.getByRole("article")).toHaveAccessibleName(
      /Comparação indisponível neste recorte/,
    );
    expect(screen.getByRole("article")).not.toHaveTextContent(/[▲▼●]/);
    expect(screen.getByRole("article")).not.toHaveTextContent(/NaN|Infinity/);
  });

  it("mantém só a limitação quando o próprio valor está indisponível", () => {
    render(
      <PanoramaMetricCard
        metric={{
          ...metric,
          valorAtual: null,
          valorAnterior: null,
          limitacoes: ["Este contrato não disponibiliza a contagem."],
        }}
        title="UCs faturadas no mês"
        comparison="anterior"
      />,
    );

    expect(
      screen.getByText("Este contrato não disponibiliza a contagem."),
    ).toBeVisible();
    expect(screen.queryByText(/Comparação indisponível/)).toBeNull();
  });
});
