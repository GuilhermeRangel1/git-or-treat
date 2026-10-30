import { afterEach, describe, expect, it, vi } from "vitest";
import {
  decodeOrder,
  decodeOrderDetail,
  decodeOrderPage,
  getOrderDetail,
  decodeOrderHistory,
  createQueueOrder,
  getOrderHistory,
  registerOrderResult,
  cancelOrder,
  searchOrders,
  updateOrder,
} from "./orders";

const order = {
  id: 12,
  uc_id: "UC-123",
  reason: "Consumo fora do padrão",
  priority: "MEDIA",
  status: "EM_ANDAMENTO",
  notes: null,
  result: null,
  created_at: "2025-02-01T12:00:00Z",
  updated_at: "2025-02-02T12:00:00Z",
  suspicion_reference: "sha256:abc",
  version: 2,
  cancellation_reason: null,
};

afterEach(() => vi.unstubAllGlobals());

describe("contrato de ordens", () => {
  it("valida enum de prioridade, datas e valores nulos", () => {
    expect(decodeOrder(order)).toMatchObject({
      priority: "MEDIA",
      status: "EM_ANDAMENTO",
      notes: null,
      result: null,
      version: 2,
      cancellation_reason: null,
    });
    expect(() => decodeOrder({ ...order, priority: "URGENTE" })).toThrow(
      "Resposta de ordem inválida",
    );
    expect(() => decodeOrder({ ...order, created_at: "ontem" })).toThrow(
      "Resposta de ordem inválida",
    );
  });

  it("trata timestamp legado sem fuso como UTC e preserva offsets explícitos", () => {
    const localSQLite = decodeOrder({
      ...order,
      created_at: "2026-10-25T02:15:05.853250",
      updated_at: "2026-10-25T02:15:05.853250",
    });
    const explicitUtc = decodeOrder({
      ...order,
      created_at: "2026-10-25T02:15:05.853250Z",
      updated_at: "2026-10-25T02:15:05.853250Z",
    });
    expect(localSQLite.created_at).toBe("2026-10-25T02:15:05.853250Z");
    expect(localSQLite.created_at).toBe(explicitUtc.created_at);
    expect(
      decodeOrder({
        ...order,
        created_at: "2026-10-25T05:15:05.853250+03:00",
      }).created_at,
    ).toBe("2026-10-25T05:15:05.853250+03:00");
  });

  it("exige versão positiva e cancellation_reason explícita no contrato de ordem", () => {
    for (const version of [undefined, null, 0, -1, 1.5, "2", true]) {
      expect(() => decodeOrder({ ...order, version })).toThrow();
    }
    expect(() =>
      decodeOrder({ ...order, cancellation_reason: undefined }),
    ).toThrow();
    expect(() => decodeOrder({ ...order, status: "ARQUIVADA" })).toThrow();
  });

  it("aceita snapshot legado com campos extras e sem schema_version", () => {
    expect(
      decodeOrderDetail({
        ...order,
        suspicion_snapshot: { data: { uc_id: "UC-123", extra_legacy: true } },
      }).suspicion_snapshot,
    ).toEqual({ data: { uc_id: "UC-123", extra_legacy: true } });
    expect(
      decodeOrderDetail({ ...order, suspicion_snapshot: null })
        .suspicion_snapshot,
    ).toBeNull();
    expect(() =>
      decodeOrderDetail({ ...order, suspicion_snapshot: [] }),
    ).toThrow("Fundamentos da ordem inválidos");
  });

  it("recusa paginação incompatível com o total", () => {
    expect(
      decodeOrderPage({
        items: [],
        pagination: { page: 1, page_size: 20, total: 0, total_pages: 0 },
      }).pagination.total_pages,
    ).toBe(0);
    expect(() =>
      decodeOrderPage({
        items: [],
        pagination: { page: 1, page_size: 20, total: 21, total_pages: 1 },
      }),
    ).toThrow("Paginação inválida");
  });
});

describe("transporte de ordens", () => {
  it("envia fingerprint Gold no payload da intenção de criação", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(order), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await createQueueOrder(
      "UC-123",
      {
        source_version: "gold-batch-1",
        source_fingerprint: "a".repeat(64),
        rule_version: "gold-fila-inspecao-v1",
      },
      "intent-1234567890",
    );

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/inspections/queue/UC-123/orders",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          source_version: "gold-batch-1",
          source_fingerprint: "a".repeat(64),
          rule_version: "gold-fila-inspecao-v1",
        }),
      }),
    );
  });

  it("passa AbortSignal à consulta de detalhe", async () => {
    const signal = new AbortController().signal;
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ...order, suspicion_snapshot: null }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await getOrderDetail(12, signal);

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/inspections/orders/12",
      expect.objectContaining({ signal }),
    );
  });

  it("envia PATCH JSON e valida a resposta antes de retornar", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          ...order,
          result: "Sem irregularidade",
          notes: "Inspeção realizada",
          suspicion_snapshot: null,
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const updated = await updateOrder(12, {
      version: 2,
      notes: "Inspeção realizada",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/inspections/orders/12",
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({ version: 2, notes: "Inspeção realizada" }),
        headers: expect.any(Headers),
      }),
    );
    expect(updated.notes).toBe("Inspeção realizada");
  });

  it("usa POST de resultado e POST de cancelamento com os payloads DEV-07", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            ...order,
            status: "CONCLUIDA",
            result: "Sem irregularidade",
            suspicion_snapshot: null,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            ...order,
            status: "CANCELADA",
            cancellation_reason: "Inspeção desnecessária",
            suspicion_snapshot: null,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );
    vi.stubGlobal("fetch", fetchMock);
    await registerOrderResult(12, { version: 2, result: "Sem irregularidade" });
    await cancelOrder(12, {
      version: 2,
      confirmed_order_id: 12,
      reason: "Inspeção desnecessária",
    });
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "/api/v1/inspections/orders/12/result",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ version: 2, result: "Sem irregularidade" }),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/v1/inspections/orders/12/cancel",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          version: 2,
          confirmed_order_id: 12,
          reason: "Inspeção desnecessária",
        }),
      }),
    );
  });

  it("valida o histórico e permite ator/versão legados nulos", async () => {
    const event = {
      id: 1,
      order_id: 12,
      previous_status: null,
      new_status: "PENDENTE",
      action: "CRIACAO",
      notes: null,
      details: null,
      actor: null,
      order_version: null,
      created_at: "2026-10-25T12:00:00Z",
    };
    expect(decodeOrderHistory([event])).toEqual([event]);
    expect(() => decodeOrderHistory({})).toThrow(
      "Histórico de ordens inválido",
    );
    for (const invalid of [
      { ...event, action: "REABERTURA" },
      { ...event, new_status: "ARQUIVADA" },
      { ...event, order_version: 0 },
      { ...event, created_at: "ontem" },
      { ...event, actor: 4 },
    ])
      expect(() => decodeOrderHistory([invalid])).toThrow(
        "Evento do histórico inválido",
      );
    const signal = new AbortController().signal;
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify([event]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    expect(await getOrderHistory(12, signal)).toEqual([event]);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/inspections/orders/12/history",
      expect.objectContaining({ signal }),
    );
  });

  it("recusa versão ausente ou inválida e não permite CANCELADA via PATCH", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    await expect(
      updateOrder(12, { version: 0, notes: "Ajuste" }),
    ).rejects.toThrow("Versão da ordem inválida");
    await expect(updateOrder(12, { version: 2 } as never)).rejects.toThrow(
      "Informe uma alteração",
    );
    await expect(
      updateOrder(12, { version: 2, status: "CANCELADA" } as never),
    ).rejects.toThrow("rota dedicada");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("preserva o erro HTTP 409 estruturado para reconciliação pela feature", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            detail: "Ordem já encerrada.",
            error: {
              code: "order_conflict",
              message: "Ordem já encerrada.",
              order_id: 12,
            },
          }),
          { status: 409, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );

    await expect(
      updateOrder(12, { version: 2, status: "EM_ANDAMENTO" }),
    ).rejects.toMatchObject({
      status: 409,
      data: { error: { code: "order_conflict", order_id: 12 } },
    });
  });

  it("mantém cancelamento de fetch como AbortError", async () => {
    const controller = new AbortController();
    const fetchMock = vi
      .fn()
      .mockRejectedValue(
        Object.assign(new Error("aborted"), { name: "AbortError" }),
      );
    vi.stubGlobal("fetch", fetchMock);
    const request = getOrderDetail(12, controller.signal);
    controller.abort();
    await expect(request).rejects.toMatchObject({ name: "AbortError" });
  });

  it("decodifica uma listagem do contrato sem perder o sinal de cancelamento", async () => {
    const signal = new AbortController().signal;
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          items: [order],
          pagination: { page: 1, page_size: 20, total: 1, total_pages: 1 },
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    const result = await searchOrders("page=1&page_size=20", signal);
    expect(result.items[0]?.id).toBe(12);
    expect(fetchMock.mock.calls[0]?.[1]).toEqual(
      expect.objectContaining({ signal }),
    );
  });
});
