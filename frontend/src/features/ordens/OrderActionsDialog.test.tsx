import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/shared/api/client";
import type { OrderDetail } from "@/shared/api/orders";
import OrderActionsDialog from "./OrderActionsDialog";

const api = vi.hoisted(() => ({
  getOrderDetail: vi.fn(),
  getOrderHistory: vi.fn(),
  updateOrder: vi.fn(),
  registerOrderResult: vi.fn(),
  cancelOrder: vi.fn(),
}));

vi.mock("@/shared/api/orders", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/shared/api/orders")>();
  return {
    ...actual,
    getOrderDetail: api.getOrderDetail,
    getOrderHistory: api.getOrderHistory,
    updateOrder: api.updateOrder,
    registerOrderResult: api.registerOrderResult,
    cancelOrder: api.cancelOrder,
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
  version: 1,
  cancellation_reason: null,
  suspicion_snapshot: null,
};

const history = [
  {
    id: 1,
    order_id: 9,
    previous_status: null,
    new_status: "PENDENTE" as const,
    action: "CRIACAO" as const,
    notes: null,
    details: "Ordem criada pela fila.",
    actor: null,
    order_version: null,
    created_at: "2025-01-10T10:00:00Z",
  },
];

function renderDialog(
  initial = order,
  onSaved = vi.fn(),
  onClose = vi.fn(),
  canEdit = true,
) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const triggerRef = { current: document.createElement("button") };
  const view = render(
    <QueryClientProvider client={client}>
      <OrderActionsDialog
        key={initial.id}
        order={initial}
        canEdit={canEdit}
        open
        onClose={onClose}
        triggerRef={triggerRef}
        onSaved={onSaved}
      />
    </QueryClientProvider>,
  );
  return {
    ...view,
    client,
    onSaved,
    onClose,
    setOpen: (open: boolean) =>
      view.rerender(
        <QueryClientProvider client={client}>
          <OrderActionsDialog
            key={initial.id}
            order={initial}
            canEdit={canEdit}
            open={open}
            onClose={onClose}
            triggerRef={triggerRef}
            onSaved={onSaved}
          />
        </QueryClientProvider>,
      ),
    setOrder: (next: OrderDetail, open = true) =>
      view.rerender(
        <QueryClientProvider client={client}>
          <OrderActionsDialog
            key={next.id}
            order={next}
            canEdit={canEdit}
            open={open}
            onClose={onClose}
            triggerRef={triggerRef}
            onSaved={onSaved}
          />
        </QueryClientProvider>,
      ),
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  api.getOrderDetail.mockResolvedValue(order);
  api.getOrderHistory.mockResolvedValue(history);
  api.updateOrder.mockImplementation(async (_id, payload) => ({
    ...order,
    ...payload,
    status: payload.status ?? order.status,
    suspicion_snapshot: null,
  }));
  api.registerOrderResult.mockImplementation(async (_id, payload) => ({
    ...order,
    status: "CONCLUIDA",
    result: payload.result,
    suspicion_snapshot: null,
  }));
  api.cancelOrder.mockImplementation(async (_id, payload) => ({
    ...order,
    status: "CANCELADA",
    cancellation_reason: payload.reason ?? null,
    suspicion_snapshot: null,
  }));
});

describe("OrderActionsDialog", () => {
  it("mostra detalhes e oculta acoes de escrita sem orders:write", async () => {
    api.getOrderDetail.mockResolvedValue(order);
    api.getOrderHistory.mockResolvedValue(history);
    renderDialog(order, vi.fn(), vi.fn(), false);

    expect(
      await screen.findByText(/acesso somente para consulta/i),
    ).toBeVisible();
    expect(screen.queryByRole("button", { name: "Iniciar ordem" })).toBeNull();
    expect(
      screen.queryByRole("button", { name: /cancelar ordem/i }),
    ).toBeNull();
    expect(
      screen.getByRole("heading", { name: "Histórico da ordem" }),
    ).toBeVisible();
  });
  it("inicia uma ordem pendente usando a versão atual do servidor", async () => {
    const user = userEvent.setup();
    renderDialog();

    await user.click(
      await screen.findByRole("button", { name: "Iniciar ordem" }),
    );
    await waitFor(() =>
      expect(api.updateOrder).toHaveBeenCalledWith(9, {
        status: "EM_ANDAMENTO",
        version: 1,
      }),
    );
    expect(api.registerOrderResult).not.toHaveBeenCalled();
  });

  it("exige resultado não vazio e registra resultado concluindo em uma ação", async () => {
    const user = userEvent.setup();
    const running = { ...order, status: "EM_ANDAMENTO" as const, version: 3 };
    api.getOrderDetail.mockResolvedValue(running);
    renderDialog(running);
    const result = await screen.findByRole("textbox", {
      name: "Resultado de campo",
    });

    await user.click(
      screen.getByRole("button", { name: "Registrar resultado e concluir" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Resultado não informado",
    );
    expect(result).toHaveFocus();
    expect(api.registerOrderResult).not.toHaveBeenCalled();

    await user.type(result, "Sem irregularidade encontrada");
    await user.click(
      screen.getByRole("button", { name: "Registrar resultado e concluir" }),
    );
    await waitFor(() =>
      expect(api.registerOrderResult).toHaveBeenCalledWith(9, {
        result: "Sem irregularidade encontrada",
        version: 3,
      }),
    );
    expect(api.updateOrder).not.toHaveBeenCalled();
  });

  it("impede duplo envio enquanto a escrita está pendente", async () => {
    const user = userEvent.setup();
    const running = { ...order, status: "EM_ANDAMENTO" as const };
    api.getOrderDetail.mockResolvedValue(running);
    let release: ((value: OrderDetail) => void) | undefined;
    api.registerOrderResult.mockImplementation(
      () => new Promise((resolve) => (release = resolve)),
    );
    renderDialog(running);
    await user.type(
      await screen.findByRole("textbox", { name: "Resultado de campo" }),
      "Conferido",
    );
    const submit = screen.getByRole("button", {
      name: "Registrar resultado e concluir",
    });
    await user.click(submit);
    await user.click(submit);
    expect(api.registerOrderResult).toHaveBeenCalledTimes(1);
    release?.({ ...running, status: "CONCLUIDA", result: "Conferido" });
  });

  it("preserva detalhe de versão mais nova quando uma resposta antiga chega depois", async () => {
    const user = userEvent.setup();
    let release: ((value: OrderDetail) => void) | undefined;
    api.updateOrder.mockImplementation(
      () => new Promise((resolve) => (release = resolve)),
    );
    const saved = vi.fn();
    const closed = vi.fn();
    const dialog = renderDialog(order, saved, closed);
    await user.click(
      await screen.findByRole("button", { name: "Iniciar ordem" }),
    );
    expect(api.updateOrder).toHaveBeenCalledWith(9, {
      status: "EM_ANDAMENTO",
      version: 1,
    });

    const latest = {
      ...order,
      status: "CANCELADA" as const,
      cancellation_reason: "Cancelada em outra sessão",
      version: 3,
    };
    dialog.client.setQueryData(["orders", "detail", 9], latest);
    release?.({ ...order, status: "EM_ANDAMENTO", version: 2 });

    await waitFor(() =>
      expect(
        dialog.client
          .getMutationCache()
          .getAll()
          .some((mutation) => mutation.state.status === "success"),
      ).toBe(true),
    );
    await waitFor(() =>
      expect(
        dialog.client.getQueryData<OrderDetail>(["orders", "detail", 9]),
      ).toEqual(expect.objectContaining({ status: "CANCELADA", version: 3 })),
    );
    await waitFor(() => {
      expect(
        screen.queryByRole("button", { name: "Iniciar ordem" }),
      ).toBeNull();
      expect(
        screen.queryByRole("button", { name: "Cancelar ordem…" }),
      ).toBeNull();
    });
    expect(saved).not.toHaveBeenCalled();
    expect(closed).not.toHaveBeenCalled();
  });

  it("não deixa uma escrita antiga fechar a sessão de outra OS", async () => {
    const user = userEvent.setup();
    const running = { ...order, status: "EM_ANDAMENTO" as const };
    const other = { ...order, id: 10, uc_id: "UC-1010" };
    api.getOrderDetail.mockImplementation(async (id) =>
      id === 9 ? running : other,
    );
    let release: ((value: OrderDetail) => void) | undefined;
    api.registerOrderResult.mockImplementation(
      () => new Promise((resolve) => (release = resolve)),
    );
    const saved = vi.fn();
    const closed = vi.fn();
    const dialog = renderDialog(running, saved, closed);
    await user.type(
      await screen.findByRole("textbox", { name: "Resultado de campo" }),
      "Inspeção concluída",
    );
    await user.click(
      screen.getByRole("button", { name: "Registrar resultado e concluir" }),
    );
    expect(await screen.findByRole("status")).toHaveTextContent(
      "Fechar esta janela não cancela a gravação",
    );

    await user.click(
      screen.getByRole("button", { name: "Fechar ações da ordem" }),
    );
    dialog.setOpen(false);
    dialog.setOrder(other);
    expect(
      await screen.findByRole("heading", { name: "Ações da ordem #10" }),
    ).toBeInTheDocument();
    release?.({
      ...running,
      status: "CONCLUIDA",
      result: "Inspeção concluída",
    });

    await waitFor(() =>
      expect(dialog.client.getQueryData(["orders", "detail", 9])).toEqual(
        expect.objectContaining({ status: "CONCLUIDA" }),
      ),
    );
    expect(
      screen.getByRole("heading", { name: "Ações da ordem #10" }),
    ).toBeInTheDocument();
    expect(saved).not.toHaveBeenCalled();
    expect(closed).toHaveBeenCalledTimes(1);
  });

  it("confirma cancelamento identificando OS e UC, motivo opcional e sem gravar ao voltar", async () => {
    const user = userEvent.setup();
    const running = { ...order, status: "EM_ANDAMENTO" as const, version: 4 };
    api.getOrderDetail.mockResolvedValue(running);
    renderDialog(running);
    await user.type(
      await screen.findByRole("textbox", { name: "Resultado de campo" }),
      "Rascunho preservado",
    );
    await user.click(screen.getByRole("button", { name: "Cancelar ordem…" }));

    expect(
      await screen.findByRole("heading", { name: "Cancelar OS-000009?" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/UC-1004/)).toBeInTheDocument();
    await user.type(
      screen.getByRole("textbox", {
        name: "Motivo do cancelamento (opcional)",
      }),
      "Duplicada",
    );
    await user.click(screen.getByRole("button", { name: "Manter ordem" }));
    expect(
      screen.getByRole("textbox", { name: "Resultado de campo" }),
    ).toHaveValue("Rascunho preservado");
    expect(api.cancelOrder).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "Cancelar ordem…" }));
    expect(
      screen.getByRole("textbox", {
        name: "Motivo do cancelamento (opcional)",
      }),
    ).toHaveValue("Duplicada");
    await user.click(
      screen.getByRole("button", { name: "Confirmar cancelamento" }),
    );
    await waitFor(() =>
      expect(api.cancelOrder).toHaveBeenCalledWith(9, {
        confirmed_order_id: 9,
        version: 4,
        reason: "Duplicada",
      }),
    );
  });

  it.each(["CONCLUIDA", "CANCELADA"] as const)(
    "mostra apenas consulta para estado final %s e carrega o histórico",
    async (status) => {
      const finalOrder = { ...order, status };
      api.getOrderDetail.mockResolvedValue(finalOrder);
      renderDialog(finalOrder);

      expect(
        await screen.findByText("Ordem criada pela fila."),
      ).toBeInTheDocument();
      expect(api.getOrderHistory).toHaveBeenCalledWith(9, expect.anything());
      expect(
        screen.queryByRole("button", { name: "Iniciar ordem" }),
      ).toBeNull();
      expect(
        screen.queryByRole("button", {
          name: "Registrar resultado e concluir",
        }),
      ).toBeNull();
      expect(
        screen.queryByRole("button", { name: "Cancelar ordem…" }),
      ).toBeNull();
      expect(screen.getByText(/Ator: Não informado/)).toBeInTheDocument();
      expect(screen.getByText(/Versão: Não informada/)).toBeInTheDocument();
      expect(
        screen.getByRole("textbox", { name: "Resultado de campo" }),
      ).toBeDisabled();
      expect(api.updateOrder).not.toHaveBeenCalled();
      expect(api.registerOrderResult).not.toHaveBeenCalled();
      expect(api.cancelOrder).not.toHaveBeenCalled();
    },
  );

  it("consulta novamente o detalhe ao reabrir uma ordem cancelada", async () => {
    const finalOrder = { ...order, status: "CANCELADA" as const };
    api.getOrderDetail.mockResolvedValue(finalOrder);
    const dialog = renderDialog(finalOrder);

    await screen.findByText("Ordem criada pela fila.");
    expect(api.getOrderDetail).toHaveBeenCalledTimes(1);
    dialog.setOpen(false);
    dialog.setOpen(true);
    await waitFor(() => expect(api.getOrderDetail).toHaveBeenCalledTimes(2));
    expect(api.updateOrder).not.toHaveBeenCalled();
    expect(api.registerOrderResult).not.toHaveBeenCalled();
    expect(api.cancelOrder).not.toHaveBeenCalled();
    expect(
      screen.getByRole("textbox", { name: "Resultado de campo" }),
    ).toBeDisabled();
  });

  it("conflito reconcilia a ordem sem repetir escrita e mantém o rascunho", async () => {
    const user = userEvent.setup();
    const running = { ...order, status: "EM_ANDAMENTO" as const };
    const cancelled = { ...running, status: "CANCELADA" as const };
    api.getOrderDetail
      .mockResolvedValueOnce(running)
      .mockResolvedValueOnce(cancelled);
    api.registerOrderResult.mockRejectedValue(
      new ApiError("Conflito", 409, {
        error: { code: "order_conflict", message: "A ordem já foi cancelada." },
      }),
    );
    renderDialog(running);
    const result = await screen.findByRole("textbox", {
      name: "Resultado de campo",
    });
    await user.type(result, "Rascunho ainda não salvo");
    await user.click(
      screen.getByRole("button", { name: "Registrar resultado e concluir" }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "A ordem já foi cancelada.",
    );
    await waitFor(() => expect(api.getOrderDetail).toHaveBeenCalledTimes(2));
    expect(api.registerOrderResult).toHaveBeenCalledTimes(1);
    expect(
      screen.getByRole("textbox", { name: "Resultado de campo" }),
    ).toHaveValue("Rascunho ainda não salvo");
    expect(screen.getByText(/Cancelada/)).toBeInTheDocument();
  });

  it("sai da confirmação e exige nova ação após conflito de cancelamento ainda ativo", async () => {
    const user = userEvent.setup();
    const running = { ...order, status: "EM_ANDAMENTO" as const, version: 4 };
    const refreshed = { ...running, version: 5 };
    api.getOrderDetail
      .mockResolvedValueOnce(running)
      .mockResolvedValueOnce(refreshed);
    api.cancelOrder.mockRejectedValue(
      new ApiError("Conflito", 409, {
        error: { code: "order_conflict", message: "A versão da ordem mudou." },
      }),
    );
    renderDialog(running);
    await screen.findByRole("textbox", { name: "Resultado de campo" });
    await user.click(screen.getByRole("button", { name: "Cancelar ordem…" }));
    await user.click(
      screen.getByRole("button", { name: "Confirmar cancelamento" }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "A versão da ordem mudou.",
    );
    await waitFor(() => expect(api.getOrderDetail).toHaveBeenCalledTimes(2));
    expect(
      screen.getByRole("heading", { name: "Ações da ordem #9" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Estado confirmado: Em andamento/),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Cancelar ordem…" }),
    ).toBeEnabled();
    expect(api.cancelOrder).toHaveBeenCalledTimes(1);
  });

  it("mantém rascunho e informa que uma falha de rede não foi confirmada", async () => {
    const user = userEvent.setup();
    const running = { ...order, status: "EM_ANDAMENTO" as const };
    api.getOrderDetail.mockResolvedValue(running);
    api.registerOrderResult.mockRejectedValue(new Error("Rede indisponível"));
    renderDialog(running);
    const result = await screen.findByRole("textbox", {
      name: "Resultado de campo",
    });
    await user.type(result, "Ponto de lacre íntegro");
    await user.click(
      screen.getByRole("button", { name: "Registrar resultado e concluir" }),
    );

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Rede indisponível");
    expect(alert).toHaveTextContent("A alteração não foi confirmada");
    expect(result).toHaveValue("Ponto de lacre íntegro");
    expect(api.registerOrderResult).toHaveBeenCalledTimes(1);
  });
});
