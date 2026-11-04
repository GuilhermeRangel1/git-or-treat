import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import OrderHistory from "./OrderHistory";

const getOrderHistory = vi.hoisted(() => vi.fn());

vi.mock("@/shared/api/orders", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/shared/api/orders")>();
  return { ...actual, getOrderHistory };
});

function renderHistory() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <OrderHistory orderId={31} />
    </QueryClientProvider>,
  );
}

beforeEach(() => vi.clearAllMocks());

it("distingue histórico vazio de carregamento", async () => {
  getOrderHistory.mockResolvedValue([]);
  renderHistory();

  expect(
    await screen.findByText("Nenhum evento registrado para esta ordem."),
  ).toBeInTheDocument();
  expect(getOrderHistory).toHaveBeenCalledWith(31, expect.anything());
});

it("expõe falha e permite repetir a consulta", async () => {
  const user = userEvent.setup();
  getOrderHistory
    .mockRejectedValueOnce(new Error("Histórico indisponível"))
    .mockResolvedValue([]);
  renderHistory();

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Histórico indisponível",
  );
  await user.click(
    screen.getByRole("button", { name: "Tentar novamente o histórico" }),
  );
  expect(
    await screen.findByText("Nenhum evento registrado para esta ordem."),
  ).toBeInTheDocument();
  expect(getOrderHistory).toHaveBeenCalledTimes(2);
});

it("usa a ação e os estados reais do evento sem presumir conclusão", async () => {
  getOrderHistory.mockResolvedValue([
    {
      id: 5,
      order_id: 31,
      previous_status: "PENDENTE",
      new_status: "EM_ANDAMENTO",
      action: "REGISTRO_RESULTADO",
      notes: null,
      details: "Leitura parcial registrada.",
      actor: "operador-7",
      order_version: 2,
      created_at: "2025-02-10T10:00:00Z",
    },
  ]);
  renderHistory();

  expect(await screen.findByText("Resultado registrado")).toBeInTheDocument();
  expect(
    screen.getByText(/Estado: Pendente → Em andamento/),
  ).toBeInTheDocument();
  expect(
    screen.queryByText("Resultado registrado e ordem concluída"),
  ).toBeNull();
});
