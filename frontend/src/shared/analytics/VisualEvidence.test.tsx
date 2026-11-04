import { describe, expect, it, vi } from "vitest";
import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import VisualEvidence from "./VisualEvidence";
import { chartCsv } from "./visual-export";
import * as downloads from "./visual-export";
import { advanceAuthorizationGeneration } from "../auth/authorization";

const data = {
  title: "Receita faturada",
  unit: "R$",
  scope: "Olinda · Residencial",
  points: [
    { label: "Mai/2026", value: 200 },
    { label: "Jun/2026", value: 100 },
  ],
};
describe("evidência visual", () => {
  it("mantém tabela e exportação consistentes com os valores de origem", async () => {
    render(<VisualEvidence data={data} />);
    expect(screen.getByRole("img")).toHaveAccessibleDescription(
      /Mai\/2026: R\$.*200,00; Jun\/2026: R\$.*100,00/,
    );
    await userEvent.click(screen.getByRole("button", { name: "Ver tabela" }));
    const rows = within(screen.getByRole("table")).getAllByRole("row");
    expect(rows).toHaveLength(3);
    expect(rows[1]).toHaveTextContent(/Mai\/2026.*200,00/);
    expect(rows[2]).toHaveTextContent(/Jun\/2026.*100,00/);
    expect(chartCsv(data)).toContain('"Mai/2026";200\r\n"Jun/2026";100');
  });
  it("mostra total único como indicador e preserva zero", () => {
    render(
      <VisualEvidence
        data={{ ...data, points: [{ label: "Jun/2026", value: 0 }] }}
      />,
    );
    expect(screen.queryByRole("img")).toBeNull();
    expect(screen.getByText(/R\$.*0,00/)).toBeVisible();
    expect(screen.queryByRole("button", { name: /PNG/ })).toBeNull();
  });
  it("não exporta contexto invalidado durante a visualização", async () => {
    render(<VisualEvidence data={data} canExport={() => false} />);
    await userEvent.click(screen.getByRole("button", { name: /CSV/ }));
    expect(screen.getByRole("alert")).toHaveTextContent(/dados mudaram/);
  });
  it("não transforma ausência em zero quando só há uma observação medida", () => {
    render(
      <VisualEvidence
        data={{
          ...data,
          points: [
            { label: "Mai/2026", value: null },
            { label: "Jun/2026", value: 0 },
          ],
        }}
      />,
    );
    expect(screen.getByText("Sem valor disponível")).toBeVisible();
    expect(screen.getByText(/R\$.*0,00/)).toBeVisible();
    expect(screen.queryByRole("img")).toBeNull();
  });
  it("CSV distingue nulo de zero e neutraliza fórmula em rótulo", () => {
    const csv = chartCsv({
      ...data,
      points: [
        { label: '=HYPERLINK("example")', value: null },
        { label: "Zero", value: 0 },
      ],
    });
    expect(csv).toContain('"\'=HYPERLINK(""example"")";\r\n"Zero";0');
    expect(csv.charCodeAt(0)).toBe(0xfeff);
    expect(
      chartCsv({ ...data, note: "Ranking limitado a 10 grupos." }),
    ).toContain('"Alcance e observações";"Ranking limitado a 10 grupos."');
  });
  it("bloqueia o arquivo quando a conta muda enquanto o servidor confere o acesso", async () => {
    let finish!: (allowed: boolean) => void;
    const verify = vi.fn(
      () =>
        new Promise<boolean>((resolve) => {
          finish = resolve;
        }),
    );
    const save = vi
      .spyOn(downloads, "exportChartCsv")
      .mockImplementation(() => {});
    try {
      render(<VisualEvidence data={data} canExport={verify} />);
      await userEvent.click(screen.getByRole("button", { name: /CSV/ }));
      expect(screen.getByRole("button", { name: /CSV/ })).toBeDisabled();
      advanceAuthorizationGeneration();
      await act(async () => finish(true));
      expect(save).not.toHaveBeenCalled();
      expect(verify).toHaveBeenCalledOnce();
      expect(screen.getByRole("alert")).toHaveTextContent(
        /acesso não pôde ser confirmado/,
      );
    } finally {
      save.mockRestore();
    }
  });
  it("preserva a precisão aprovada de DEC na tabela e no CSV", async () => {
    const dec = {
      ...data,
      unit: "h/UC",
      precision: 6,
      points: [{ label: "Jun/2026", value: 0.123456 }],
    };
    render(<VisualEvidence data={dec} />);
    await userEvent.click(screen.getByRole("button", { name: "Ver tabela" }));
    expect(
      within(screen.getByRole("table")).getByText("0,123456 h/UC"),
    ).toBeVisible();
    expect(chartCsv(dec)).toContain('"Jun/2026";0,123456');
  });
});

it("rosca mantém total, legenda e percentuais exportáveis", async () => {
  const value = {
    ...data,
    kind: "donut" as const,
    total: 300,
    categoryLabel: "Município",
    points: [
      { label: "Olinda", value: 200, percentage: 66.67 },
      { label: "Recife", value: 100, percentage: 33.33 },
    ],
  };
  render(<VisualEvidence data={value} />);
  expect(screen.getByRole("img")).toHaveAccessibleDescription(
    /Olinda.*200,00.*66.67/,
  );
  expect(screen.getByText("Total do recorte")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Ver tabela" }));
  const table = screen.getByRole("table");
  expect(within(table).getByText("66,67%")).toBeVisible();
  expect(chartCsv(value)).toContain('"Município";"Valor";"Participação (%)"');
  expect(chartCsv(value)).toContain('"Olinda";200;66,67');
});

it("barras preservam valor negativo e ausência sem apresentar participação", async () => {
  render(
    <VisualEvidence
      data={{
        ...data,
        kind: "horizontal",
        categoryLabel: "Município",
        points: [
          { label: "A", value: -5 },
          { label: "B", value: 5 },
          { label: "C", value: null },
        ],
      }}
    />,
  );
  expect(screen.getByRole("img")).toHaveAccessibleDescription(
    /A: -R\$.*5,00; B: R\$.*5,00; C: Sem valor disponível/,
  );
  await userEvent.click(screen.getByRole("button", { name: "Ver tabela" }));
  expect(
    within(screen.getByRole("table")).queryByText("Participação"),
  ).toBeNull();
});

it("lista extensa pagina no DOM e mantém todos os municípios no CSV", async () => {
  const full = Array.from({ length: 200 }, (_, i) => ({
    label: `Município ${i + 1}`,
    value: i + 1,
  }));
  const value = {
    ...data,
    kind: "horizontal" as const,
    categoryLabel: "Município",
    points: full.slice(0, 10),
    tablePoints: full,
  };
  render(<VisualEvidence data={value} />);
  await userEvent.click(
    screen.getByRole("button", { name: "Ver lista completa (200)" }),
  );
  expect(within(screen.getByRole("table")).getAllByRole("row")).toHaveLength(
    21,
  );
  expect(screen.getByRole("status")).toHaveTextContent(
    "Página 1 de 10 · 200 grupos",
  );
  await userEvent.click(screen.getByRole("button", { name: "Próxima" }));
  expect(
    within(screen.getByRole("table")).getByText("Município 21"),
  ).toBeVisible();
  expect(
    within(screen.getByRole("table")).queryByText("Município 1"),
  ).toBeNull();
  expect(chartCsv(value)).toContain('"Município 200";200');
  expect(chartCsv(value).trim().split("\r\n")).toHaveLength(205);
});
