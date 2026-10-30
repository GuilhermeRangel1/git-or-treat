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
  decodeOperationOptions,
  useOperationDetail,
  useOperationRanking,
  useOperationSummary,
} from "./useOperations";
import { parseOperationParams } from "./operations-state";
import { resetGoldPublication } from "@/shared/analytics/goldPublication";

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

afterEach(() => vi.unstubAllGlobals());

it("preserva alimentadores Gold sem município cadastrado nas opções", () => {
  const options = decodeOperationOptions({
    data: {
      competencias: ["2025-01"],
      municipios: ["Recife"],
      alimentadores: [{ id: "F-SEM-MUNICIPIO", municipio: null }],
    },
    metadata: {
      contract_version: "2.0.0",
      status: "available",
      period: null,
      filters: {
        municipio: null,
        bairro: null,
        classe: null,
        alimentador: null,
      },
      source: {
        kind: "gold",
        version: "batch-options",
        is_demo: false,
        updated_at: "2026-10-29T00:00:00Z",
      },
      limitations: [],
      temporal_scope: "snapshot",
      schema_version: "gold-csv-v1",
      fingerprint: "d".repeat(64),
    },
  });
  expect(options.alimentadores).toEqual([
    { id: "F-SEM-MUNICIPIO", municipio: null },
  ]);
});

describe("consultas de Operação", () => {
  it("consulta detalhe Gold agregado sem paginação e valida identidade v2", async () => {
    const metadata = {
      contract_version: "2.0.0",
      status: "partial",
      period: { start: "2025-01", end: "2025-02", granularity: "month" },
      filters: {
        municipio: null,
        bairro: null,
        classe: null,
        alimentador: "F-1",
      },
      source: {
        kind: "gold",
        version: "batch-ui-test",
        is_demo: false,
        updated_at: "2026-10-29T00:00:00Z",
      },
      limitations: [],
      temporal_scope: "monthly",
      schema_version: "gold-csv-v1",
      fingerprint: "b".repeat(64),
    };
    const point = {
      feeder_id: "F-1",
      municipality: "Recife",
      period: metadata.period,
      observed_period: metadata.period,
      observed_competencies: ["2025-01", "2025-02"],
      missing_competencies: [],
      duration_hours_sum: 4,
      interruption_count: null,
      denominator_uc_count: 2,
      dec_hours_per_uc: 2,
      fec_interruptions_per_uc: null,
      status: "partial",
      dec_status: "partial",
      fec_status: "unavailable",
      limitations: [],
    };
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = new URL(String(input), window.location.origin);
      expect(url.searchParams.has("page")).toBe(false);
      expect(url.searchParams.has("page_size")).toBe(false);
      return new Response(
        JSON.stringify({
          metadata,
          data: {
            summary: point,
            series: [],
            occurrences: null,
            occurrences_status: "unavailable",
            definition: {
              reference: "ref",
              dec_formula: "DEC",
              fec_formula: "FEC",
              dec_unit: "h/UC",
              fec_unit: "int./UC",
              event_grain: "UC-evento",
              population: "cadastro",
              completeness: "parcial",
            },
          },
        }),
        { status: 200 },
      );
    });
    vi.stubGlobal("fetch", fetchMock);
    const detail = renderHook(
      () =>
        useOperationDetail({
          start: "2025-01",
          end: "2025-02",
          feederId: "F-1",
          page: 4,
          pageSize: 10,
          municipality: null,
          source: "gold",
        }),
      { wrapper },
    );
    await waitFor(() =>
      expect(detail.result.current.data?.data.occurrences).toBeNull(),
    );
    expect(detail.result.current.data?.metadata.contract_version).toBe("2.0.0");
    const goldDetail = detail.result.current.data;
    expect(
      goldDetail && "dec_status" in goldDetail.data.summary
        ? goldDetail.data.summary.dec_status
        : undefined,
    ).toBe("partial");
    resetGoldPublication();
  });
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
    const parsed = parseOperationParams(new URLSearchParams("bairro=Centro"));
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
