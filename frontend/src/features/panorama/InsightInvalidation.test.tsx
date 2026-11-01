import { act, renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import { calculateSyntheticPanorama } from "../../shared/analytics/syntheticData";
import { resetGoldPublication } from "../../shared/analytics/goldPublication";
import { usePanoramaInsight } from "./usePanoramaInsight";
import { requestPanoramaInsight } from "./insightApi";
import type { PanoramaInsightEnvelope } from "./insightContract";
vi.mock("./insightApi", () => ({ requestPanoramaInsight: vi.fn() }));
afterEach(() => {
  vi.resetAllMocks();
  resetGoldPublication();
});
const filters = {
  periodo: "2024-04",
  comparacao: "anterior" as const,
  municipio: "todos",
  classe: "todas",
};
function wrapper({ children }: { children: ReactNode }) {
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
let client: QueryClient;
function result(label: string) {
  return { label } as unknown as PanoramaInsightEnvelope;
}
it("discards an older A response after A-B-A even when transport ignores cancellation", async () => {
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const finish: ((value: PanoramaInsightEnvelope) => void)[] = [];
  vi.mocked(requestPanoramaInsight).mockImplementation(
    () => new Promise((resolve) => finish.push(resolve)),
  );
  const {
    result: query,
    rerender,
    unmount,
  } = renderHook(
    ({ municipio }) => {
      const f = { ...filters, municipio };
      return usePanoramaInsight(f, calculateSyntheticPanorama(f), true);
    },
    { initialProps: { municipio: "todos" }, wrapper },
  );
  await waitFor(() => expect(finish).toHaveLength(1));
  rerender({ municipio: "Recife" });
  await waitFor(() => expect(finish).toHaveLength(2));
  rerender({ municipio: "todos" });
  await waitFor(() => expect(finish).toHaveLength(3));
  await act(async () => {
    finish[0](result("old-a"));
    finish[1](result("b"));
  });
  expect(query.current.data).toBeUndefined();
  await act(async () => finish[2](result("current-a")));
  await waitFor(() => expect(query.current.data).toEqual(result("current-a")));
  unmount();
  client.clear();
});
it("uses a new query after the same lot gets another fingerprint or authorization generation", async () => {
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  vi.mocked(requestPanoramaInsight).mockResolvedValue(result("old"));
  const {
    result: query,
    rerender,
    unmount,
  } = renderHook(
    ({ fingerprint }) => {
      const d = calculateSyntheticPanorama(filters);
      d.origem = {
        kind: "gold",
        isDemo: false,
        version: d.loteVersao,
        contractVersion: "v1",
        fingerprint,
        limitations: [],
      };
      return usePanoramaInsight(filters, d, true);
    },
    { initialProps: { fingerprint: "a".repeat(64) }, wrapper },
  );
  await waitFor(() => expect(query.current.data).toEqual(result("old")));
  vi.mocked(requestPanoramaInsight).mockResolvedValue(result("new"));
  rerender({ fingerprint: "b".repeat(64) });
  await waitFor(() => expect(query.current.data).toEqual(result("new")));
  expect(requestPanoramaInsight).toHaveBeenCalledTimes(2);
  act(() => resetGoldPublication());
  await waitFor(() => expect(requestPanoramaInsight).toHaveBeenCalledTimes(3));
  unmount();
  client.clear();
});
