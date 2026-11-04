import { act, renderHook, waitFor } from "@testing-library/react";
import {
  QueryClient,
  QueryClientProvider,
  focusManager,
} from "@tanstack/react-query";
import { afterEach, expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import { calculateSyntheticPanorama } from "../../shared/analytics/syntheticData";
import { resetGoldPublication } from "../../shared/analytics/goldPublication";
import { usePanoramaInsight } from "./usePanoramaInsight";
import {
  requestPanoramaInsight,
  verifyPanoramaInsightContext,
  PanoramaInsightApiError,
} from "./insightApi";
import type { PanoramaInsightEnvelope } from "./insightContract";
vi.mock("./insightApi", async () => ({
  ...(await vi.importActual<typeof import("./insightApi")>("./insightApi")),
  requestPanoramaInsight: vi.fn(),
  verifyPanoramaInsightContext: vi.fn(),
}));
afterEach(() => {
  vi.resetAllMocks();
  focusManager.setFocused(undefined);
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

it("mantém o insight ao voltar à janela e revalida contexto sem chamar o modelo novamente", async () => {
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const ready = {
    label: "ready",
    insight: { status: "answered" },
  } as unknown as PanoramaInsightEnvelope;
  vi.mocked(requestPanoramaInsight).mockResolvedValue(ready);
  vi.mocked(verifyPanoramaInsightContext).mockResolvedValue(undefined);
  const data = calculateSyntheticPanorama(filters);
  data.origem = {
    kind: "gold",
    isDemo: false,
    version: data.loteVersao,
    contractVersion: "v1",
    fingerprint: "a".repeat(64),
    limitations: [],
  };
  const view = renderHook(() => usePanoramaInsight(filters, data, true), {
    wrapper,
  });
  await waitFor(() => expect(view.result.current.data).toEqual(ready));
  act(() => focusManager.setFocused(false));
  act(() => focusManager.setFocused(true));
  await waitFor(() =>
    expect(verifyPanoramaInsightContext).toHaveBeenCalledTimes(1),
  );
  await waitFor(() => expect(view.result.current.isFetching).toBe(false));
  expect(requestPanoramaInsight).toHaveBeenCalledTimes(1);
  expect(view.result.current.data).toEqual(ready);
  vi.mocked(verifyPanoramaInsightContext).mockRejectedValue(
    new PanoramaInsightApiError("Atualização pendente", true, 503),
  );
  await act(async () => {
    await view.result.current.refetch();
  });
  expect(view.result.current.data).toEqual(ready);
  await waitFor(() => expect(view.result.current.isError).toBe(true));
  expect(requestPanoramaInsight).toHaveBeenCalledTimes(1);
  view.unmount();
  client.clear();
});
