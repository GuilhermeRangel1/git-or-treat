import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/shared/api/client";
import type { OrderDetail } from "@/shared/api/orders";
import OrderActionsDialog from "./OrderActionsDialog";

const api = vi.hoisted(() => ({
  getOrderDetail: vi.fn(),
  updateOrder: vi.fn(),
}));

vi.mock("@/shared/api/orders", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/shared/api/orders")>();
  return {
    ...actual,
    getOrderDetail: api.getOrderDetail,
    updateOrder: api.updateOrder,
  };
});

const order: OrderDetail = {
  id: 9,
  uc_id: "UC-1004",
  reason: "Lacuna de leitura e variação de consumo",
  priority: "MEDIA",
  status: "PENDENTE",
  notes: null,
  result: null,
  created_at: "2025-01-10T10:00:00Z",
  updated_at: "2025-01-10T10:00:00Z",
  suspicion_reference: "sha256:reference",
  suspicion_snapshot: null,
};

function renderDialog(initial = order, onSaved = vi.fn(), onClose = vi.fn()) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const triggerRef = { current: document.createElement("button") };
  const view = render(
    <QueryClientProvider client={client}>
      <OrderActionsDialog
        order={initial}
        open
        onClose={onClose}
        triggerRef={triggerRef}
        onSaved={onSaved}
      />
    </QueryClientProvider>,
  );
  return { ...view, client, onSaved, onClose };
}

beforeEach(() => {
  vi.clearAllMocks();
  api.getOrderDetail.mockResolvedValue(order);
  api.updateOrder.mockImplementation(async (_id, payload) => ({
    ...order,
    ...payload,
    status: payload.status ?? order.status,
    suspicion_snapshot: null,
  }));
});

afterEach(() => vi.restoreAllMocks());

describe("OrderActionsDialog", () => {
  it("usa o estado atual do servidor e oferece somente transições válidas", async () => {
    const user = userEvent.setup();
    renderDialog();

    const status = await screen.findByRole("combobox", {
      name: "Estado da ordem",
    });
    expect(
      within(status)
        .getAllByRole("option")
        .map((option) => option.textContent),
    ).toEqual(["Pendente", "Em andamento"]);
    expect(
      within(status).queryByRole("option", { name: "Cancelada" }),
    ).toBeNull();

    await user.selectOptions(status, "EM_ANDAMENTO");
    await user.click(screen.getByRole("button", { name: "Atualizar estado" }));
    await waitFor(() =>
      expect(api.updateOrder).toHaveBeenCalledWith(9, {
        status: "EM_ANDAMENTO",
      }),
    );
  });

  it("exige resultado e move o foco para o campo quando o registro está vazio", async () => {
    const user = userEvent.setup();
    renderDialog();
    const result = await screen.findByRole("textbox", {
      name: "Resultado de campo",
    });
    await user.click(
      screen.getByRole("button", { name: "Registrar resultado" }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Resultado não informado",
    );
    expect(result).toHaveAttribute("aria-invalid", "true");
    expect(result).toHaveFocus();
    expect(api.updateOrder).not.toHaveBeenCalled();
  });

  it("salva resultado sem concluir automaticamente e só notifica após JSON validado", async () => {
    const user = userEvent.setup();
    let finishRequest: ((saved: OrderDetail) => void) | undefined;
    api.updateOrder.mockImplementation(
      () =>
        new Promise((resolve) => {
          finishRequest = resolve;
        }),
    );
    const saved = vi.fn();
    const closed = vi.fn();
    renderDialog(order, saved, closed);
    const result = await screen.findByRole("textbox", {
      name: "Resultado de campo",
    });
    await user.type(result, "Sem irregularidade encontrada");
    await user.click(
      screen.getByRole("button", { name: "Registrar resultado" }),
    );

    await waitFor(() =>
      expect(api.updateOrder).toHaveBeenCalledWith(9, {
        result: "Sem irregularidade encontrada",
      }),
    );
    expect(saved).not.toHaveBeenCalled();
    finishRequest?.({
      ...order,
      result: "Sem irregularidade encontrada",
      suspicion_snapshot: null,
    });
    await waitFor(() =>
      expect(saved).toHaveBeenCalledWith(
        expect.objectContaining({
          status: "PENDENTE",
          result: "Sem irregularidade encontrada",
        }),
        "Resultado de campo registrado.",
      ),
    );
    expect(closed).toHaveBeenCalledOnce();
  });

  it("mantém o rascunho ao voltar da confirmação e não grava até confirmar", async () => {
    const user = userEvent.setup();
    const saved = vi.fn();
    const closed = vi.fn();
    renderDialog(order, saved, closed);
    const result = await screen.findByRole("textbox", {
      name: "Resultado de campo",
    });
    await user.type(result, "Verificar vedação do medidor");
    await user.click(screen.getByRole("button", { name: "Cancelar ordem…" }));

    expect(
      await screen.findByRole("heading", { name: "Cancelar a ordem #9?" }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Manter ordem" }));
    expect(
      screen.getByRole("textbox", { name: "Resultado de campo" }),
    ).toHaveValue("Verificar vedação do medidor");
    expect(api.updateOrder).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "Cancelar ordem…" }));
    await user.click(screen.getByRole("button", { name: "Cancelar ordem" }));
    await waitFor(() =>
      expect(api.updateOrder).toHaveBeenCalledWith(9, { status: "CANCELADA" }),
    );
    await waitFor(() =>
      expect(saved).toHaveBeenCalledWith(
        expect.objectContaining({ status: "CANCELADA" }),
        "Ordem cancelada.",
      ),
    );
    expect(closed).toHaveBeenCalledOnce();
  });

  it("conclui somente com resultado preenchido e inclui resultado no mesmo PATCH", async () => {
    const user = userEvent.setup();
    const running = { ...order, status: "EM_ANDAMENTO" as const };
    api.getOrderDetail.mockResolvedValue(running);
    renderDialog(running);
    const status = await screen.findByRole("combobox", {
      name: "Estado da ordem",
    });
    await user.selectOptions(status, "CONCLUIDA");
    await user.click(screen.getByRole("button", { name: "Atualizar estado" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Resultado não informado",
    );
    expect(api.updateOrder).not.toHaveBeenCalled();

    await user.type(
      screen.getByRole("textbox", { name: "Resultado de campo" }),
      "Sem irregularidade",
    );
    await user.click(screen.getByRole("button", { name: "Atualizar estado" }));
    await waitFor(() =>
      expect(api.updateOrder).toHaveBeenLastCalledWith(9, {
        status: "CONCLUIDA",
        result: "Sem irregularidade",
      }),
    );
  });

  it.each(["CONCLUIDA", "CANCELADA"] as const)(
    "não permite mutar ou reabrir estado final %s",
    async (statusValue) => {
      const finalOrder = { ...order, status: statusValue };
      api.getOrderDetail.mockResolvedValue(finalOrder);
      renderDialog(finalOrder);
      const status = await screen.findByRole("combobox", {
        name: "Estado da ordem",
      });
      expect(within(status).getAllByRole("option")).toHaveLength(1);
      expect(
        screen.getByRole("button", { name: "Atualizar estado" }),
      ).toBeDisabled();
      expect(
        screen.queryByRole("button", { name: "Cancelar ordem…" }),
      ).toBeNull();
      expect(screen.getByRole("status")).toHaveTextContent(
        "não pode ser reaberta",
      );
      expect(api.updateOrder).not.toHaveBeenCalled();
    },
  );

  it("mostra conflito e reconcilia o estado final sem perder o rascunho", async () => {
    const user = userEvent.setup();
    const running = { ...order, status: "EM_ANDAMENTO" as const };
    const finished = {
      ...running,
      status: "CONCLUIDA" as const,
      result: "Já finalizada",
    };
    api.getOrderDetail
      .mockResolvedValueOnce(running)
      .mockResolvedValueOnce(finished);
    api.updateOrder.mockRejectedValue(
      new ApiError("Conflito", 409, {
        detail: "A ordem já foi encerrada.",
        error: {
          code: "order_conflict",
          message: "A ordem já foi encerrada.",
          order_id: 9,
        },
      }),
    );
    renderDialog(running);
    const status = await screen.findByRole("combobox", {
      name: "Estado da ordem",
    });
    const result = screen.getByRole("textbox", { name: "Resultado de campo" });
    await user.type(result, "Rascunho de campo ainda não salvo");
    await user.selectOptions(status, "CONCLUIDA");
    await user.click(screen.getByRole("button", { name: "Atualizar estado" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "A ordem já foi encerrada.",
    );
    await waitFor(() => expect(api.getOrderDetail).toHaveBeenCalledTimes(2));
    expect(
      screen.getByRole("combobox", { name: "Estado da ordem" }),
    ).toHaveValue("CONCLUIDA");
    expect(
      screen.getByRole("textbox", { name: "Resultado de campo" }),
    ).toHaveValue("Rascunho de campo ainda não salvo");
    expect(
      screen.queryByRole("button", { name: "Cancelar ordem…" }),
    ).toBeNull();
  });

  it("sai da confirmação ao receber conflito de cancelamento e reconcilia ordem encerrada", async () => {
    const user = userEvent.setup();
    const running = { ...order, status: "EM_ANDAMENTO" as const };
    const cancelled = { ...running, status: "CANCELADA" as const };
    api.getOrderDetail
      .mockResolvedValueOnce(running)
      .mockResolvedValueOnce(cancelled);
    api.updateOrder.mockRejectedValue(
      new ApiError("Conflito", 409, {
        detail: "A ordem já foi cancelada.",
        error: {
          code: "order_conflict",
          message: "A ordem já foi cancelada.",
          order_id: 9,
        },
      }),
    );
    renderDialog(running);
    const result = await screen.findByRole("textbox", {
      name: "Resultado de campo",
    });
    await user.type(result, "Observação ainda não salva");
    await user.click(screen.getByRole("button", { name: "Cancelar ordem…" }));
    await user.click(screen.getByRole("button", { name: "Cancelar ordem" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "A ordem já foi cancelada.",
    );
    await waitFor(() => expect(api.getOrderDetail).toHaveBeenCalledTimes(2));
    expect(
      screen.getByRole("heading", { name: "Ações da ordem #9" }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Cancelar ordem" })).toBeNull();
    expect(
      screen.getByRole("textbox", { name: "Resultado de campo" }),
    ).toHaveValue("Observação ainda não salva");
  });

  it("não afirma rollback após uma falha de rede e preserva o resultado digitado", async () => {
    const user = userEvent.setup();
    api.updateOrder.mockRejectedValue(new Error("Rede indisponível"));
    renderDialog();
    const result = await screen.findByRole("textbox", {
      name: "Resultado de campo",
    });
    await user.type(result, "Ponto de lacre íntegro");
    await user.click(
      screen.getByRole("button", { name: "Registrar resultado" }),
    );

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Rede indisponível");
    expect(alert).toHaveTextContent("A alteração não foi confirmada");
    expect(alert).not.toHaveTextContent("permanece como estava");
    expect(
      screen.getByRole("textbox", { name: "Resultado de campo" }),
    ).toHaveValue("Ponto de lacre íntegro");
  });

  it("mostra erro de consulta e permite repetir o GET", async () => {
    const user = userEvent.setup();
    api.getOrderDetail.mockRejectedValueOnce(
      new Error("Falha ao consultar ordem"),
    );
    renderDialog();
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Falha ao consultar ordem",
    );
    await user.click(screen.getByRole("button", { name: "Tentar novamente" }));
    expect(
      await screen.findByRole("combobox", { name: "Estado da ordem" }),
    ).toBeInTheDocument();
  });
});
