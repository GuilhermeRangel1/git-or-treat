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
    const { container } = render(
      <PanoramaSeriesChart data={history} selectedPeriod="2026-06" />,
    );

    expect(
      container.querySelectorAll(".panorama-series-chart__point"),
    ).toHaveLength(12);
    await user.click(screen.getByRole("button", { name: "24 meses" }));
    expect(
      container.querySelectorAll(".panorama-series-chart__point"),
    ).toHaveLength(24);
    await user.click(screen.getByRole("button", { name: "Todo o histórico" }));
    expect(
      container.querySelectorAll(".panorama-series-chart__point"),
    ).toHaveLength(48);
    expect(screen.getByText("Jul/2022 – Jun/2026")).toBeVisible();
    expect(
      container.querySelectorAll(".panorama-series-chart__tick--mobile"),
    ).toHaveLength(4);
    expect(
      container.querySelectorAll(".panorama-series-chart__tick--desktop"),
    ).toHaveLength(6);
    for (const tick of container.querySelectorAll(
      ".panorama-series-chart__tick--mobile, .panorama-series-chart__tick--desktop",
    )) {
      expect(tick.textContent).toMatch(/\/20\d{2}/);
    }

    await user.click(screen.getByRole("button", { name: "12 meses" }));
    expect(
      container.querySelectorAll(".panorama-series-chart__point"),
    ).toHaveLength(12);
    expect(screen.getByText("Jul/2025 – Jun/2026")).toBeVisible();
  });

  it("trata série de um ponto e janela anterior aos dados observados", () => {
    const { rerender } = render(
      <PanoramaSeriesChart data={[data[0]]} selectedPeriod="2024-03" />,
    );
    expect(
      screen.getByRole("button", { name: /Mar\/2024: R\$/ }),
    ).toBeVisible();

    rerender(<PanoramaSeriesChart data={data} selectedPeriod="2024-02" />);
    expect(
      screen.getByText("Não há competências observadas até o mês selecionado."),
    ).toBeVisible();
  });

  it("mantém lacunas da fonte Gold como indisponíveis na série e na alternativa textual", () => {
    const { container } = render(
      <PanoramaSeriesChart
        sourceKind="gold"
        data={[{ ...data[0], receitaFaturada: null }, data[1]]}
      />,
    );

    expect(screen.getByText("Valores em R$ mil por mês")).toBeVisible();
    expect(
      container.querySelector(".panorama-series-chart__tick--mobile"),
    ).toHaveTextContent(/Mar\/2024 · —/);
    expect(screen.getByRole("group")).toHaveAccessibleName(
      /Mar\/2024 e Abr\/2024/,
    );
  });

  it("mostra a soma como indisponível quando a série inteira não tem valores", async () => {
    const user = userEvent.setup();
    const { container } = render(
      <PanoramaSeriesChart
        sourceKind="gold"
        data={data.map((point) => ({ ...point, receitaFaturada: null }))}
      />,
    );
    expect(
      container.querySelectorAll(".panorama-series-chart__tick--mobile"),
    ).toHaveLength(2);
    await user.click(
      screen.getByRole("button", { name: /Ver tabela da série/ }),
    );
    expect(screen.getByRole("table")).toHaveTextContent("Indisponível");
    expect(screen.getByRole("table")).toHaveTextContent("Soma indisponível");
    expect(screen.getByRole("table")).not.toHaveTextContent(/R\$\s*0,00/);
  });

  it("mostra uma série mensal com valores visíveis, escala em R$ mil e período parcial", () => {
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
    expect(screen.getByText("Valores em R$ mil por mês")).toBeVisible();
    expect(screen.getByRole("group")).toHaveAccessibleName(
      /Receita por competência.*Receita faturada mensal entre Mar\/2024 e Abr\/2024/,
    );
    expect(screen.getByText(/Competência parcial/)).toBeVisible();

    const selectedPoint = document.querySelector(
      ".panorama-series-chart__point.is-selected",
    );
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
    const { container } = render(
      <PanoramaSeriesChart data={centData} selectedPeriod="2024-04" />,
    );

    const zeroPoint = container.querySelector(
      '.panorama-series-chart__point[aria-label^="Mar/2024"]',
    );
    expect(zeroPoint).toHaveStyle({ top: "192px" });
    expect(zeroPoint).not.toHaveClass("is-selected");

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
