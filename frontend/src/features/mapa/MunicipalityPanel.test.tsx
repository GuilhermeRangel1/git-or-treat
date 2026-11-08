import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it } from "vitest";
import type { RevenueEnvelope } from "@/shared/analytics/revenueContract";
import MunicipalityPanel from "./MunicipalityPanel";
import { municipalities } from "./municipalities";

it("shows available amounts without a percentage-variation field", () => {
  const item = {
    comparison: {
      initial: { billed_amount: 100, measured_energy_kwh: 50 },
      final: { billed_amount: 120, measured_energy_kwh: 60 },
      billed_amount_change_brl: 20,
      measured_energy_change_kwh: 10,
      billed_amount_change_percent: 20,
    },
  } as unknown as RevenueEnvelope["data"]["breakdown"]["items"][number];

  render(
    <MemoryRouter>
      <MunicipalityPanel
        municipality={municipalities[0]}
        item={item}
        detail={undefined}
        detailError={false}
        query={null}
        layer="revenue"
        revenueHref={null}
        onRetryDetail={() => undefined}
      />
    </MemoryRouter>,
  );

  expect(screen.getByText("Faturamento · R$", { exact: true })).toBeVisible();
  expect(screen.queryByText(/percentual/i)).not.toBeInTheDocument();
});

// ---------------------------------------------------------------------------
// Painel organizado em abas: bairros (maior queda primeiro) e série mensal.
// ---------------------------------------------------------------------------

import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

type Cell = number | null;

function neighborhood(key: string, initial: Cell, final: Cell) {
  return {
    key,
    label: key,
    comparison: {
      initial: { billed_amount: initial, measured_energy_kwh: 1 },
      final: { billed_amount: final, measured_energy_kwh: 1 },
      billed_amount_change_brl:
        initial === null || final === null ? null : final - initial,
      measured_energy_change_kwh: 0,
    },
  };
}

function monthlySeries(count: number) {
  return Array.from({ length: count }, (_, index) => {
    const month = (index % 12) + 1;
    const year = 2025 + Math.floor(index / 12);
    return {
      competencia: `${year}-${String(month).padStart(2, "0")}`,
      billed_amount: 1000 + index,
      measured_energy_kwh: 500 + index,
    };
  });
}

// Mudança de faturamento por bairro: B02 é a maior queda e B10 a maior alta.
const changes: Record<string, number> = {
  B01: -5,
  B02: -100,
  B03: -50,
  B04: 20,
  B05: -10,
  B06: 0,
  B07: 5,
  B08: -1,
  B09: -70,
  B10: 30,
};

const detail = {
  data: {
    comparison: undefined,
    series: monthlySeries(14),
    coverage: { measured_energy_kwh: { status: "complete" } },
    breakdown: {
      items: [
        ...Object.entries(changes).map(([key, change]) =>
          neighborhood(key, 1000, 1000 + change),
        ),
        neighborhood("B11", null, 500),
      ],
      reconciliation: { limitations: ["Limite de reconciliação."] },
    },
  },
} as unknown as RevenueEnvelope;

const summaryItem = {
  comparison: {
    initial: { billed_amount: 100, measured_energy_kwh: 50 },
    final: { billed_amount: 80, measured_energy_kwh: 60 },
    billed_amount_change_brl: -20,
    measured_energy_change_kwh: 10,
  },
} as unknown as RevenueEnvelope["data"]["breakdown"]["items"][number];

function renderPanel(
  props: Partial<Parameters<typeof MunicipalityPanel>[0]> = {},
) {
  return render(
    <MemoryRouter>
      <MunicipalityPanel
        municipality={municipalities[0]}
        item={summaryItem}
        detail={detail}
        detailError={false}
        query={null}
        layer="revenue"
        revenueHref={null}
        onRetryDetail={() => undefined}
        {...props}
      />
    </MemoryRouter>,
  );
}

const neighborhoodNames = () =>
  screen.getAllByRole("rowheader").map((cell) => cell.textContent);

it("não renderiza nada sem município selecionado", () => {
  const { container } = renderPanel({ municipality: null });
  expect(container).toBeEmptyDOMElement();
});

it("abre em Bairros, com a maior queda primeiro e no máximo 8 linhas", async () => {
  const user = userEvent.setup();
  renderPanel();

  expect(screen.getByRole("tab", { name: "Bairros" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  expect(neighborhoodNames()).toEqual([
    "B02",
    "B09",
    "B03",
    "B05",
    "B01",
    "B08",
    "B06",
    "B07",
  ]);
  expect(screen.queryByText("B10")).not.toBeInTheDocument();
  // B11 não tem comparação nos dois extremos e fica de fora da tabela.
  expect(screen.queryByText("B11")).not.toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "Mostrar todos (10)" }));
  expect(neighborhoodNames()).toHaveLength(10);
  expect(screen.getByText("B10")).toBeVisible();
  await user.click(screen.getByRole("button", { name: "Mostrar menos" }));
  expect(neighborhoodNames()).toHaveLength(8);
});

it("troca para a série mensal, mostrando os 12 meses mais recentes", async () => {
  const user = userEvent.setup();
  renderPanel();

  await user.click(screen.getByRole("tab", { name: "Série mensal" }));
  expect(screen.getByRole("tab", { name: "Série mensal" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  expect(screen.queryByText("Jan/2025")).not.toBeInTheDocument();
  expect(screen.queryByText("Fev/2025")).not.toBeInTheDocument();
  expect(screen.getByText("Mar/2025")).toBeVisible();
  expect(screen.getByText("Fev/2026")).toBeVisible();

  await user.click(
    screen.getByRole("button", { name: "Mostrar série completa (14)" }),
  );
  expect(screen.getByText("Jan/2025")).toBeVisible();
});

it("navega entre as abas pelo teclado", async () => {
  const user = userEvent.setup();
  renderPanel();
  screen.getByRole("tab", { name: "Bairros" }).focus();

  await user.keyboard("{ArrowRight}");
  expect(screen.getByRole("tab", { name: "Série mensal" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  expect(screen.getByRole("tab", { name: "Série mensal" })).toHaveFocus();
  expect(screen.getByRole("tabpanel")).toHaveAccessibleName("Série mensal");

  await user.keyboard("{Home}");
  expect(screen.getByRole("tab", { name: "Bairros" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
});

it("recolhe as ressalvas, mas deixa a contagem visível e o texto acessível", async () => {
  const user = userEvent.setup();
  renderPanel();

  // 1 grupo de bairros sem comparação + 1 limitação da reconciliação.
  const summary = screen.getByText("Ressalvas (2)");
  expect(summary).toBeVisible();
  expect(screen.getByText("Limite de reconciliação.")).not.toBeVisible();

  await user.click(summary);
  expect(screen.getByText("Limite de reconciliação.")).toBeVisible();
  expect(screen.getByText(/B11 · faturamento indisponível/)).toBeVisible();
});

it("mostra a variação com sinal e o caminho de volta ao mapa", async () => {
  const user = userEvent.setup();
  const onBackToMap = vi.fn();
  renderPanel({ onBackToMap });

  const revenueCard = screen
    .getByRole("heading", { name: "Faturamento · R$" })
    .closest("div") as HTMLElement;
  expect(revenueCard).toHaveTextContent("−R$ 20,00");
  expect(revenueCard).toHaveTextContent("▼");
  expect(revenueCard).toHaveTextContent("Inicial: R$ 100,00");
  await user.click(screen.getByRole("button", { name: "Voltar ao mapa" }));
  expect(onBackToMap).toHaveBeenCalledTimes(1);
});

it("mostra o nome do bairro sem repetir o município do painel", () => {
  const first = municipalities[0];
  if (!first) throw new Error("Faltam municípios de teste.");
  const prefix = first.name.toUpperCase();
  const labelled = {
    data: {
      ...detail.data,
      breakdown: {
        ...detail.data.breakdown,
        items: [
          { ...neighborhood("x", 1000, 900), label: `${prefix} / SUCUPIRA` },
          { ...neighborhood("y", 1000, 950), label: "OUTRA CIDADE / CENTRO" },
          { ...neighborhood("z", null, 100), label: `${prefix} / SEM BASE` },
        ],
      },
    },
  } as unknown as RevenueEnvelope;
  renderPanel({ detail: labelled });

  expect(neighborhoodNames()).toEqual(["SUCUPIRA", "OUTRA CIDADE / CENTRO"]);
  expect(screen.queryByText(new RegExp(`${prefix} / SUCUPIRA`))).toBeNull();
});

it("oferece 'Limpar seleção' no painel só quando há o que limpar", async () => {
  const user = userEvent.setup();
  const onClearSelection = vi.fn();
  const { unmount } = renderPanel({ onClearSelection });

  await user.click(screen.getByRole("button", { name: "Limpar seleção" }));
  expect(onClearSelection).toHaveBeenCalledTimes(1);
  unmount();

  renderPanel();
  expect(
    screen.queryByRole("button", { name: "Limpar seleção" }),
  ).not.toBeInTheDocument();
});
