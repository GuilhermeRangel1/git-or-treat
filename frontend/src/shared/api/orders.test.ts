import { afterEach, describe, expect, it, vi } from "vitest";
import {
  decodeOrder,
  decodeOrderDetail,
  decodeOrderPage,
  getOrderDetail,
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
};

afterEach(() => vi.unstubAllGlobals());

describe("contrato de ordens", () => {
  it("valida enum de prioridade, datas e valores nulos", () => {
    expect(decodeOrder(order)).toMatchObject({
      priority: "MEDIA",
      status: "EM_ANDAMENTO",
      notes: null,
      result: null,
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
          suspicion_snapshot: null,
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const updated = await updateOrder(12, { result: "Sem irregularidade" });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/inspections/orders/12",
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({ result: "Sem irregularidade" }),
        headers: expect.any(Headers),
      }),
    );
    expect(updated.result).toBe("Sem irregularidade");
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
      updateOrder(12, { status: "CANCELADA" }),
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
