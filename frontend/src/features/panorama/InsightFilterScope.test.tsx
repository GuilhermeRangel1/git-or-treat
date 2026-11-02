import { expect, it, vi } from "vitest";
import { renderHook } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { calculateSyntheticPanorama } from "../../shared/analytics/syntheticData";
import type { PanoramaFilters } from "../../shared/analytics/types";
import { usePanoramaInsight } from "./usePanoramaInsight";

const original: PanoramaFilters = {
  periodo: "2024-04",
  comparacao: "anterior",
  municipio: "todos",
  classe: "todas",
};
it.each<Partial<PanoramaFilters>>([
  { periodo: "2024-03" },
  { comparacao: "nenhuma" },
  { municipio: "Recife" },
  { classe: "RESIDENCIAL" },
  {
    periodo: "2024-03",
    comparacao: "ano_anterior",
    municipio: "Recife",
    classe: "RESIDENCIAL",
  },
])("não envia insight com indicadores do recorte anterior: %j", (changed) => {
  const fetcher = vi.fn();
  vi.stubGlobal("fetch", fetcher);
  const data = calculateSyntheticPanorama(original);
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const view = renderHook(
    () => usePanoramaInsight({ ...original, ...changed }, data, true),
    {
      wrapper: ({ children }) => (
        <QueryClientProvider client={client}>{children}</QueryClientProvider>
      ),
    },
  );
  expect(view.result.current.fetchStatus).toBe("idle");
  expect(fetcher).not.toHaveBeenCalled();
  view.unmount();
  client.clear();
});
