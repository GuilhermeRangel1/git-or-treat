import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { decodeSourceOptions, useSourceOptions } from "./sourceOptions";
import { sourceOptionsFixture } from "./sourceOptions.fixture.test-support";

vi.unmock("@/shared/analytics/sourceOptions");
afterEach(() => vi.unstubAllGlobals());

it("consulta o catálogo por Fetch com cancelamento e valida a origem Gold", async () => {
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(
      JSON.stringify({
        ...sourceOptionsFixture,
        source: {
          ...sourceOptionsFixture.source,
          kind: "gold_csv",
          is_demo: false,
        },
        data: {
          ...sourceOptionsFixture.data,
          municipio: ["Município do lote"],
          competencias: ["2026-06"],
        },
      }),
    ),
  );
  vi.stubGlobal("fetch", fetchMock);
  const query = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const { result, unmount } = renderHook(() => useSourceOptions(), {
    wrapper: ({ children }) => (
      <QueryClientProvider client={query}>{children}</QueryClientProvider>
    ),
  });
  await waitFor(() => expect(result.current.isSuccess).toBe(true));
  expect(fetchMock.mock.calls[0][0]).toBe("/api/v1/analytics/options");
  expect(fetchMock.mock.calls[0][1].signal).toBeInstanceOf(AbortSignal);
  expect(result.current.data?.source.is_demo).toBe(false);
  expect(result.current.data?.data.municipio).toEqual(["Município do lote"]);
  unmount();
  query.clear();
});

it("recusa competências inválidas e dados externos sem o tipo esperado", () => {
  expect(() =>
    decodeSourceOptions({
      ...sourceOptionsFixture,
      data: { ...sourceOptionsFixture.data, competencias: ["2026-13"] },
    }),
  ).toThrow();
  expect(() =>
    decodeSourceOptions({
      ...sourceOptionsFixture,
      data: { ...sourceOptionsFixture.data, alimentador: [42] },
    }),
  ).toThrow();
});
