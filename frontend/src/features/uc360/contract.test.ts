import { describe, expect, it } from "vitest";
import { decodeUCSearch, decodeUCHistory, UCContractError } from "./contract";

function historyResponse(
  page: number,
  pageSize: number,
  total: number,
  totalPages: number,
  items: unknown[],
) {
  return {
    data: { items },
    pagination: {
      page,
      page_size: pageSize,
      total,
      total_pages: totalPages,
    },
    metadata: {
      contract_version: "1.1.0",
      status: "available",
      period: { start: "2025-01", end: "2025-02", granularity: "month" },
      filters: {},
      source: {
        kind: "synthetic",
        version: "dev03-v1",
        is_demo: true,
        updated_at: "2026-10-21T00:00:00Z",
      },
      limitations: [],
    },
  };
}

describe("UC API contract", () => {
  it("preserves a valid empty search as distinct from malformed data", () => {
    expect(
      decodeUCSearch({
        data: { items: [] },
        pagination: { page: 1, page_size: 20, total: 0, total_pages: 0 },
        metadata: { status: "empty" },
      }).data.items,
    ).toEqual([]);
    expect(() =>
      decodeUCSearch({
        data: { items: [] },
        pagination: {},
        metadata: { status: "empty" },
      }),
    ).toThrow(UCContractError);
  });

  it("aceita paginação válida fora do fim e mantém os totais declarados", () => {
    expect(
      decodeUCSearch({
        data: { items: [] },
        pagination: { page: 8, page_size: 20, total: 21, total_pages: 2 },
        metadata: { status: "empty" },
      }).pagination,
    ).toEqual({ page: 8, page_size: 20, total: 21, total_pages: 2 });
  });

  it.each([
    [{ page: 0, page_size: 20, total: 0, total_pages: 0 }],
    [{ page: 1.5, page_size: 20, total: 0, total_pages: 0 }],
    [{ page: 1, page_size: 0, total: 0, total_pages: 0 }],
    [{ page: 1, page_size: 101, total: 0, total_pages: 0 }],
    [{ page: 1, page_size: 20, total: 2, total_pages: 0 }],
    [{ page: 1, page_size: 20, total: 0, total_pages: 1 }],
  ])("rejeita metadados de paginação inválidos: %o", (pagination) => {
    expect(() =>
      decodeUCSearch({
        data: { items: [] },
        pagination,
        metadata: { status: "empty" },
      }),
    ).toThrow(UCContractError);
  });

  it("preserva campos desconhecidos em itens de histórico", () => {
    const history = decodeUCHistory(
      historyResponse(1, 20, 1, 1, [
        {
          competencia: "2025-01",
          measured_energy_kwh: 0,
          status: "available",
          extension: "preservada",
        },
      ]),
      "consumption",
    );

    expect(history.data.items[0]).toMatchObject({
      extension: "preservada",
      measured_energy_kwh: 0,
    });
  });

  it("aceita página além do fim no histórico sem alterar os totais", () => {
    const history = decodeUCHistory(
      historyResponse(9, 1, 1, 1, []),
      "consumption",
    );

    expect(history.data.items).toEqual([]);
    expect(history.pagination).toEqual({
      page: 9,
      page_size: 1,
      total: 1,
      total_pages: 1,
    });
  });

  it("rejeita total_pages incoerente no histórico", () => {
    expect(() =>
      decodeUCHistory(historyResponse(1, 20, 21, 1, []), "consumption"),
    ).toThrow(UCContractError);
  });
});
