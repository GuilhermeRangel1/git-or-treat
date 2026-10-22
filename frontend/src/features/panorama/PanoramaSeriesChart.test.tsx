import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import PanoramaSeriesChart from "./PanoramaSeriesChart";

const data = [
  {
    competencia: "2024-04",
    label: "Abr/24",
    receitaFaturada: 76500,
    receitaPaga: 74200,
    energiaConsumidaKwh: 90000,
    energiaFaturadaKwh: 90000,
    ucsAtivas: 1248,
    decHoras: 1,
    fecVezes: 1,
  },
];

describe("PanoramaSeriesChart", () => {
  it("mostra escala, valores e detalhes fora da rolagem pelo mouse e teclado", async () => {
    const user = userEvent.setup();
    render(<PanoramaSeriesChart data={data} />);
    expect(screen.getByText(/Escala vertical: R\$ mil/)).toBeVisible();
    expect(screen.getAllByText("76,5")[0]).toBeVisible();
    const bar = screen.getByRole("img", { name: /Abr\/24: faturado/ });
    await user.hover(bar);
    expect(screen.getByRole("status")).toHaveTextContent(
      /Abr\/24.*76.500.*74.200/,
    );
    expect(
      screen.getByRole("region", {
        name: "Série histórica com rolagem horizontal",
      }),
    ).not.toContainElement(screen.getByRole("status"));
    await user.unhover(bar);
    bar.focus();
    expect(await screen.findByText(/Faturado: R\$/)).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Físico (Energia)" }));
    expect(screen.getByText(/Escala vertical: MWh/)).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Ver Tabela" }));
    expect(screen.getByRole("table")).toHaveTextContent("90.000 kWh");
  });
});
