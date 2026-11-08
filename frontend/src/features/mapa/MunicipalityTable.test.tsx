import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import type { MunicipalityMetric } from "./contract";
import MunicipalityTable from "./MunicipalityTable";
import { municipalities } from "./municipalities";

const [a, b, c] = municipalities;
if (!a || !b || !c) throw new Error("Faltam municípios de teste.");

function metric(
  municipality: (typeof municipalities)[number],
  final: number | null,
  change = 0,
): MunicipalityMetric {
  return {
    municipality,
    item:
      final === null
        ? null
        : ({
            comparison: {
              initial: {
                billed_amount: final - change,
                measured_energy_kwh: 1,
              },
              final: { billed_amount: final, measured_energy_kwh: 2 },
              billed_amount_change_brl: change,
              measured_energy_change_kwh: 0,
            },
          } as unknown as MunicipalityMetric["item"]),
  };
}

function renderTable(
  items: MunicipalityMetric[],
  options: {
    layer?: "revenue" | "revenue_change";
    partial?: string[];
    onSelect?: (code: string) => void;
  } = {},
) {
  return render(
    <MunicipalityTable
      items={items}
      selectedCode=""
      layer={options.layer ?? "revenue"}
      partialCodes={new Set(options.partial ?? [])}
      dataAvailable
      onSelect={options.onSelect ?? (() => {})}
    />,
  );
}

const order = () =>
  screen
    .getAllByRole("button", { name: /^Selecionar / })
    .map((button) => button.getAttribute("aria-label"));

it("ordena do maior para o menor valor", () => {
  renderTable([metric(a, 100), metric(b, 300), metric(c, 200)]);
  expect(order()).toEqual([
    `Selecionar ${b.name}`,
    `Selecionar ${c.name}`,
    `Selecionar ${a.name}`,
  ]);
  expect(screen.getByText(/maior para o menor valor/i)).toBeVisible();
});

it("nas variações, começa pela maior queda", () => {
  renderTable([metric(a, 100, -50), metric(b, 100, 20), metric(c, 100, -10)], {
    layer: "revenue_change",
  });
  expect(order()).toEqual([
    `Selecionar ${a.name}`,
    `Selecionar ${c.name}`,
    `Selecionar ${b.name}`,
  ]);
  expect(screen.getByText(/maior queda para a maior alta/i)).toBeVisible();
});

it("deixa município sem observação por último e não o trata como zero", () => {
  renderTable([metric(a, null), metric(b, 10)]);
  expect(order()).toEqual([`Selecionar ${b.name}`, `Selecionar ${a.name}`]);
  expect(screen.getByText("Sem observação")).toBeVisible();
  expect(screen.getByText(/não são tratados como zero/i)).toBeVisible();
});

it("avisa uma vez quando a cobertura é parcial em todos, sem repetir por linha", () => {
  renderTable([metric(a, 100), metric(b, 300)], {
    partial: [a.code, b.code],
  });
  expect(
    screen.getByRole("status", {
      name: "",
    }),
  ).toHaveTextContent(/cobertura parcial em todos os municípios/i);
  expect(
    screen.queryByRole("columnheader", { name: "Cobertura" }),
  ).not.toBeInTheDocument();
  // Quem usa leitor de tela continua sabendo o estado de cada linha.
  expect(
    screen.getAllByText(/cobertura parcial/i, { selector: ".sr-only" }),
  ).toHaveLength(2);
});

it("marca só as exceções quando a cobertura parcial não é geral", () => {
  renderTable([metric(a, 100), metric(b, 300)], { partial: [a.code] });
  expect(screen.getByRole("columnheader", { name: "Cobertura" })).toBeVisible();
  expect(screen.getAllByText("Parcial")).toHaveLength(1);
  const row = screen
    .getByRole("button", {
      name: `Selecionar ${a.name}`,
    })
    .closest("tr");
  expect(row).not.toBeNull();
  expect(within(row as HTMLElement).getByText("Parcial")).toBeVisible();
});

it("seleciona o município pela lista", async () => {
  const user = userEvent.setup();
  const onSelect = vi.fn();
  renderTable([metric(a, 100), metric(b, 300)], { onSelect });
  await user.click(
    screen.getByRole("button", { name: `Selecionar ${a.name}` }),
  );
  expect(onSelect).toHaveBeenCalledWith(a.code);
});
