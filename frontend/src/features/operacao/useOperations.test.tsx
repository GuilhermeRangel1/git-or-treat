import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  detailFixture,
  rankingFixture,
  summaryFixture,
} from "./fixtures.test-support";
import {
  useOperationDetail,
  useOperationRanking,
  useOperationSummary,
} from "./useOperations";
import { parseOperationParams } from "./operations-state";

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("consultas de Operação", () => {
  it("consulta summary/ranking e passa sinal de cancelamento", async () => {
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        expect(init?.signal).toBeInstanceOf(AbortSignal);
        return new Response(
          JSON.stringify(
            String(input).includes("/summary")
              ? summaryFixture
              : rankingFixture,
          ),
          { status: 200 },
        );
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const query = { start: "2025-01", end: "2025-02", feederId: null };
    const summary = renderHook(() => useOperationSummary(query), { wrapper });
    await waitFor(() =>
      expect(summary.result.current.data?.data.summary.dec_hours_per_uc).toBe(
        1.5,
      ),
    );
    const ranking = renderHook(
      () => useOperationRanking({ ...query, metric: "dec" }),
      { wrapper },
    );
    await waitFor(() =>
      expect(ranking.result.current.data?.data.items[0]?.feeder_id).toBe(
        "AL-01",
      ),
    );
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("desabilita query inválida e recusa metadata de outro recorte", async () => {
    const fetchMock = vi.fn(
      async () => new Response(JSON.stringify(summaryFixture), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const parsed = parseOperationParams(
      new URLSearchParams("municipio=Recife"),
    );
    expect(parsed.query).toBeNull();
    const invalid = renderHook(() => useOperationSummary(parsed.query), {
      wrapper,
    });
    expect(invalid.result.current.fetchStatus).toBe("idle");
    const wrongContext = renderHook(
      () =>
        useOperationSummary({
          start: "2025-02",
          end: "2025-02",
          feederId: "AL-02",
        }),
      { wrapper },
    );
    await waitFor(() => expect(wrongContext.result.current.isError).toBe(true));
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("valida feeder e paginação de detalhe contra o pedido", async () => {
    const fetchMock = vi.fn(
      async () => new Response(JSON.stringify(detailFixture), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const detail = renderHook(
      () =>
        useOperationDetail({
          start: "2025-01",
          end: "2025-02",
          feederId: "AL-02",
          page: 2,
          pageSize: 20,
        }),
      { wrapper },
    );
    await waitFor(() => expect(detail.result.current.isError).toBe(true));
  });

  it("aceita detalhe só quando janela, alimentador e página conferem", async () => {
    const fetchMock = vi.fn(
      async () => new Response(JSON.stringify(detailFixture), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const detail = renderHook(
      () =>
        useOperationDetail({
          start: "2025-01",
          end: "2025-02",
          feederId: "AL-01",
          page: 1,
          pageSize: 20,
        }),
      { wrapper },
    );
    await waitFor(() =>
      expect(detail.result.current.data?.data.summary.feeder_id).toBe("AL-01"),
    );
    const wrongPage = renderHook(
      () =>
        useOperationDetail({
          start: "2025-01",
          end: "2025-02",
          feederId: "AL-01",
          page: 2,
          pageSize: 20,
        }),
      { wrapper },
    );
    await waitFor(() => expect(wrongPage.result.current.isError).toBe(true));
  });
});
