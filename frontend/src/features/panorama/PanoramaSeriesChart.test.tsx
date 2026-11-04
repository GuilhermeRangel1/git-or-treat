import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import PanoramaSeriesChart from "./PanoramaSeriesChart";

const data = [
  {
    competencia: "2024-03",
    label: "Mar/24",
    receitaFaturada: 72000,
    receitaPaga: 70000,
    energiaConsumidaKwh: 90000,
    energiaFaturadaKwh: 90000,
    ucsAtivas: 1248,
    decHoras: 1,
    fecVezes: 1,
  },
  {
    competencia: "2024-04",
    label: "Abr/24",
    receitaFaturada: 76500,
    receitaPaga: 74200,
    energiaConsumidaKwh: 91000,
    energiaFaturadaKwh: 91000,
    ucsAtivas: 1250,
    decHoras: 1,
    fecVezes: 1,
  },
];

describe("PanoramaSeriesChart", () => {
  it("explora janelas de 12, 24 e todo o histórico sem alterar a competência limite", async () => {
    const user = userEvent.setup();
    const history = Array.from({ length: 48 }, (_, index) => {
      const date = new Date(Date.UTC(2022, 6 + index, 1));
      const competencia = `${date.getUTCFullYear()}-${String(date.getUTCMonth() + 1).padStart(2, "0")}`;
      return { ...data[0], competencia, receitaFaturada: index * 1000 };
    });
    render(<PanoramaSeriesChart data={history} selectedPeriod="2026-06" />);

    expect(screen.getAllByRole("img", { name: /^Exibir / })).toHaveLength(12);
    await user.click(screen.getByRole("button", { name: "24 meses" }));
    expect(screen.getAllByRole("img", { name: /^Exibir / })).toHaveLength(24);
    await user.click(screen.getByRole("button", { name: "Todo o histórico" }));
    expect(screen.getAllByRole("img", { name: /^Exibir / })).toHaveLength(48);
    expect(screen.getByText("Jul/2022 – Jun/2026")).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Todo o histórico" }),
    ).toHaveAttribute("aria-pressed", "true");
    expect(
      screen.getByRole("img", { name: /^Receita faturada por mês/ }),
    ).toHaveAccessibleName(/Jul\/2022:.*Jun\/2026:/);

    await user.click(screen.getByRole("button", { name: "12 meses" }));
    expect(screen.getAllByRole("img", { name: /^Exibir / })).toHaveLength(12);
    expect(screen.getByText("Jul/2025 – Jun/2026")).toBeVisible();
  });

  it("trata série de um ponto e janela anterior aos dados observados", () => {
    const { rerender } = render(
      <PanoramaSeriesChart data={[data[0]]} selectedPeriod="2024-03" />,
    );
    expect(
      screen.getByRole("img", { name: /Exibir Mar\/2024, faturamento R\$/ }),
    ).toBeVisible();

    rerender(<PanoramaSeriesChart data={data} selectedPeriod="2024-02" />);
    expect(
      screen.getByText("Não há competências observadas até o mês selecionado."),
    ).toBeVisible();
  });

  it("mantém lacunas da fonte Gold como indisponíveis na série e na alternativa textual", async () => {
    const user = userEvent.setup();
    render(
      <PanoramaSeriesChart
        sourceKind="gold"
        data={[{ ...data[0], receitaFaturada: null }, data[1]]}
      />,
    );

    expect(screen.getByText("Receita faturada por mês (BRL).")).toBeVisible();
    expect(
      screen.getByRole("img", { name: /^Receita faturada por mês/ }),
    ).toHaveAccessibleName(/Mar\/2024: sem dado; Abr\/2024: R\$/);
    expect(
      screen.queryByRole("img", { name: /^Exibir Mar\/2024/ }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("img", { name: /^Exibir Abr\/2024/ }),
    ).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: /Ver tabela da série/ }),
    );
    expect(screen.getByRole("row", { name: /Mar\/2024/ })).toHaveTextContent(
      "Indisponível",
    );
  });

  it("mostra a soma como indisponível quando a série inteira não tem valores", async () => {
    const user = userEvent.setup();
    render(
      <PanoramaSeriesChart
        sourceKind="gold"
        data={data.map((point) => ({ ...point, receitaFaturada: null }))}
      />,
    );
    expect(
      screen.getByText("Sem dados de faturamento no período"),
    ).toBeVisible();
    expect(
      screen.queryByRole("img", { name: /^Exibir / }),
    ).not.toBeInTheDocument();
    await user.click(
      screen.getByRole("button", { name: /Ver tabela da série/ }),
    );
    expect(screen.getByRole("table")).toHaveTextContent("Indisponível");
    expect(screen.getByRole("table")).toHaveTextContent("Soma indisponível");
    expect(screen.getByRole("table")).not.toHaveTextContent(/R\$\s*0,00/);
  });

  it("mostra uma série mensal em reais e identifica a competência parcial", () => {
    render(
      <PanoramaSeriesChart
        data={data}
        partialPeriod="2024-04"
        selectedPeriod="2024-04"
      />,
    );

    expect(
      screen.getByRole("heading", { name: "Receita por competência" }),
    ).toBeVisible();
    expect(screen.getByText("Receita faturada por mês (BRL).")).toBeVisible();
    expect(
      screen.getByRole("img", { name: /^Receita faturada por mês/ }),
    ).toHaveAccessibleName(/Mar\/2024:.*Abr\/2024:/);
    expect(screen.getByText(/Competência parcial/)).toBeVisible();

    const selectedPoint = screen.getByRole("img", {
      name: /Exibir Abr\/2024,.*competência selecionada, competência parcial/,
    });
    expect(selectedPoint).toHaveAttribute("data-partial", "true");
    expect(
      screen.queryByRole("button", { name: /Físico|Pago|Ver Tabela/ }),
    ).not.toBeInTheDocument();
  });

  it("abre a tabela detalhada, fecha com Escape e devolve o foco ao acionador", async () => {
    const user = userEvent.setup();
    render(<PanoramaSeriesChart data={data} />);

    const trigger = screen.getByRole("button", {
      name: "Ver tabela da série →",
    });
    await user.click(trigger);

    const dialog = screen.getByRole("dialog", { name: "Tabela da série" });
    expect(dialog).toBeVisible();
    expect(screen.getByRole("table")).toBeVisible();
    expect(screen.getByRole("table")).toHaveTextContent(/R\$\s*76\.500/);
    expect(
      screen.getByText("Soma dos meses exibidos (ilustrativa)"),
    ).toBeVisible();
    expect(screen.getByRole("table")).toHaveTextContent(/R\$\s*148\.500/);

    fireEvent.keyDown(dialog, { key: "Escape" });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });

  it("preserva zero e centavos na série e tabela", async () => {
    const user = userEvent.setup();
    const centData = [
      { ...data[0], receitaFaturada: 0 },
      { ...data[1], receitaFaturada: 12345.67 },
    ];
    render(<PanoramaSeriesChart data={centData} selectedPeriod="2024-04" />);

    const zeroPoint = screen.getByRole("img", {
      name: /Exibir Mar\/2024, faturamento R\$\s*0,00/,
    });
    expect(zeroPoint).toBeVisible();
    expect(zeroPoint).not.toHaveAccessibleName(/competência selecionada/);
    fireEvent.focus(zeroPoint);
    expect(screen.getByRole("tooltip")).toHaveAccessibleName(
      /Mar\/2024: R\$\s*0,00/,
    );
    fireEvent.blur(zeroPoint);
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
    const centPoint = screen.getByRole("img", {
      name: /Exibir Abr\/2024, faturamento R\$\s*12\.345,67, competência selecionada/,
    });
    await user.hover(centPoint);
    expect(screen.getByRole("tooltip")).toHaveAccessibleName(
      /Abr\/2024: R\$\s*12\.345,67/,
    );
    await user.unhover(centPoint);

    await user.click(
      screen.getByRole("button", { name: "Ver tabela da série →" }),
    );
    const table = screen.getByRole("table");
    expect(table).toHaveTextContent(/R\$\s*0,00/);
    const rows = screen.getAllByRole("row");
    expect(rows[2]).toHaveTextContent(/R\$\s*12\.345,67/);
    expect(rows[3]).toHaveTextContent(
      /Soma dos meses exibidos \(ilustrativa\).*R\$\s*12\.345,67/,
    );
  });
});
