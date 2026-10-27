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
  it("mostra uma série mensal com valores visíveis, escala em R$ mil e período parcial", () => {
    render(
      <PanoramaSeriesChart
        data={data}
        partialPeriod="2024-04"
        selectedPeriod="2024-04"
      />,
    );

    expect(
      screen.getByRole("heading", { name: "Receita ao longo do período" }),
    ).toBeVisible();
    expect(screen.getByText("Cenário sintético · R$ mil / mês")).toBeVisible();
    expect(screen.getByRole("img")).toHaveAccessibleName(
      /Receita ao longo do período.*Receita faturada mensal entre Mar\/2024 e Abr\/2024/,
    );
    expect(screen.getByText("76,5")).toBeVisible();
    expect(screen.getByText("72")).toBeVisible();
    expect(screen.getByText(/Abr\/2024\*/)).toBeVisible();

    const selectedBar = document.querySelector(
      ".panorama-series-chart__bar.is-selected",
    );
    expect(selectedBar).toHaveAttribute("data-partial", "true");
    expect(
      screen.queryByRole("button", { name: /Físico|Pago|Ver Tabela/ }),
    ).not.toBeInTheDocument();
  });

  it("abre a tabela detalhada, fecha com Escape e devolve o foco ao acionador", async () => {
    const user = userEvent.setup();
    render(<PanoramaSeriesChart data={data} />);

    const trigger = screen.getByRole("button", {
      name: "Ver dados da receita →",
    });
    await user.click(trigger);

    const dialog = screen.getByRole("dialog", { name: "Dados da receita" });
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

  it("preserva zero e centavos na tabela sem desenhar uma barra falsa", async () => {
    const user = userEvent.setup();
    const centData = [
      { ...data[0], receitaFaturada: 0 },
      { ...data[1], receitaFaturada: 12345.67 },
    ];
    const { container } = render(
      <PanoramaSeriesChart data={centData} selectedPeriod="2024-03" />,
    );

    const zeroBar = container.querySelector(
      ".panorama-series-chart__item .panorama-series-chart__bar",
    );
    expect(zeroBar).toHaveStyle({ height: "0px" });
    expect(zeroBar).not.toHaveClass("is-selected");
    expect(zeroBar?.previousElementSibling).toHaveTextContent("0");

    await user.click(
      screen.getByRole("button", { name: "Ver dados da receita →" }),
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
