import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import RevenueOverview from "./RevenueOverview";
import { decodeRevenueWindow, type RevenueEnvelope } from "./contract";

const window = {
  status: "available",
  windows: ["2022-07", "2023-06", "2025-07", "2026-06"],
  method: "V3",
  components: {
    preco: 50,
    volume: -80,
    interacao: -5,
    entradas: 10,
    saidas: -2,
    sem_leitura: 3,
    outros: 4,
  },
  initial_amount_brl: 100,
  final_amount_brl: 80,
  total_change_brl: -20,
  change_percent: -20,
  component_percentage_points: { preco: 50, volume: -80 },
  residual_brl: 0,
  group_count: 1,
  incomplete_groups: 0,
  limitations: [],
};
const envelope = {
  data: { window_decomposition: window },
  metadata: { source: { updated_at: "2026-11-05T00:00:00Z", is_demo: false } },
} as unknown as RevenueEnvelope;

it("mostra a ponte reconciliada e preserva as sete parcelas no modal", async () => {
  const investigate = vi.fn();
  render(<RevenueOverview envelope={envelope} onInvestigate={investigate} />);
  expect(
    screen.getByRole("img", { name: "Cascata da variação de receita" }),
  ).toBeVisible();
  expect(screen.getByText("Demais componentes")).toBeVisible();
  expect(
    screen.queryByText("Interação preço × volume"),
  ).not.toBeInTheDocument();
  await userEvent.click(
    screen.getByRole("button", { name: "Como calculamos e valores" }),
  );
  const dialog = screen.getByRole("dialog");
  expect(within(dialog).getByText("Interação preço × volume")).toBeVisible();
  expect(within(dialog).getByText("Faturas sem leitura")).toBeVisible();
  await userEvent.click(
    within(dialog).getByRole("button", { name: "Fechar fundamentos" }),
  );
  await userEvent.click(
    screen.getByRole("button", { name: /Investigar recortes/ }),
  );
  expect(investigate).toHaveBeenCalledOnce();
});

it("não repete os efeitos em cartões nem exibe a apresentação genérica do case", () => {
  render(<RevenueOverview envelope={envelope} onInvestigate={() => {}} />);
  expect(screen.getAllByText(/\+R\$\s*50,00/)).toHaveLength(1);
  expect(screen.queryByText("A pergunta de Henrique")).not.toBeInTheDocument();
  expect(screen.queryByText(/premissas do case/)).not.toBeInTheDocument();
});

it("sinaliza dados parciais e deixa os limites no modal", async () => {
  const partial = structuredClone(envelope);
  Object.assign(partial.data.window_decomposition!, {
    status: "partial",
    initial_amount_brl: null,
    final_amount_brl: null,
    change_percent: null,
    component_percentage_points: {},
    incomplete_groups: 1,
  });
  render(<RevenueOverview envelope={partial} onInvestigate={() => {}} />);
  expect(
    screen.queryByRole("img", { name: "Cascata da variação de receita" }),
  ).not.toBeInTheDocument();
  expect(screen.queryByText("Percentual indisponível")).not.toBeInTheDocument();
  expect(screen.getByText("Dados parciais · R$")).toBeVisible();
  expect(screen.queryByText(/tarifa homologada/)).not.toBeInTheDocument();
  await userEvent.click(
    screen.getByRole("button", { name: "Como calculamos e valores" }),
  );
  expect(
    within(screen.getByRole("dialog")).getByText(
      /Grupos com base incompleta: 1/,
    ),
  ).toBeVisible();
});

it("valida números externos e conserva compatibilidade com respostas sem a extensão", () => {
  expect(decodeRevenueWindow(window)?.change_percent).toBe(-20);
  expect(() =>
    decodeRevenueWindow({ ...window, change_percent: "20" }),
  ).toThrow();
  expect(() =>
    decodeRevenueWindow({
      ...window,
      component_percentage_points: { preco: Infinity },
    }),
  ).toThrow();
  expect(decodeRevenueWindow(undefined)).toBeNull();
});

it("expõe o motivo que impede a decomposição sem exigir abertura de modal", () => {
  const unavailable = structuredClone(envelope);
  Object.assign(unavailable.data.window_decomposition!, {
    status: "unavailable",
    limitations: ["Decomposição indisponível por alimentador."],
  });
  render(<RevenueOverview envelope={unavailable} onInvestigate={() => {}} />);
  expect(
    screen.getByText("Decomposição indisponível por alimentador."),
  ).toBeVisible();
});
