import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import { apiClient } from "@/shared/api/client";
import { useUCOverview, useUCSeries } from "./useUC360";

vi.mock("@/shared/api/client", () => ({ apiClient: vi.fn() }));
vi.mock("./contract", () => ({
  decodeUCOverview: (value: unknown) => value,
  decodeUCHistory: (value: unknown) => value,
}));

afterEach(() => vi.resetAllMocks());

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

function response(uc: string, start: string, end: string) {
  return { data: { profile: { uc_id: uc }, period: { start, end } } };
}

it("ignora respostas tardias ao trocar a UC e o período", async () => {
  const pending: Array<(value: unknown) => void> = [];
  vi.mocked(apiClient).mockImplementation(
    () => new Promise((resolve) => pending.push(resolve)),
  );
  const { result, rerender } = renderHook(
    ({ uc, start }) => useUCOverview(uc, start, "2025-12", true),
    {
      initialProps: { uc: "UC-A", start: "2025-01" },
      wrapper,
    },
  );
  await waitFor(() => expect(pending).toHaveLength(1));
  rerender({ uc: "UC-B", start: "2025-02" });
  await waitFor(() => expect(pending).toHaveLength(2));
  await act(async () => pending[1](response("UC-B", "2025-02", "2025-12")));
  await waitFor(() =>
    expect(result.current.data?.data.profile.uc_id).toBe("UC-B"),
  );
  await act(async () => pending[0](response("UC-A", "2025-01", "2025-12")));
  expect(result.current.data?.data.profile.uc_id).toBe("UC-B");
  expect(result.current.data?.data.period.start).toBe("2025-02");
});

it("recusa um overview que retorna outra UC", async () => {
  vi.mocked(apiClient).mockResolvedValue(
    response("UC-B", "2025-01", "2025-12"),
  );
  const { result } = renderHook(
    () => useUCOverview("UC-A", "2025-01", "2025-12", true),
    { wrapper },
  );
  await waitFor(() => expect(result.current.isError).toBe(true));
  expect(result.current.data).toBeUndefined();
});

it("reúne todas as páginas da série sem misturar publicações", async () => {
  const meta = {
    period: { start: "2000-01", end: "2010-12" },
    source: { version: "v2-a" },
  };
  const rows = Array.from({ length: 100 }, (_, index) => ({
    competencia: `${2000 + Math.floor(index / 12)}-${String((index % 12) + 1).padStart(2, "0")}`,
    measured_energy_kwh: index,
  }));
  vi.mocked(apiClient)
    .mockResolvedValueOnce({
      data: { items: rows },
      pagination: { total_pages: 2 },
      metadata: meta,
    })
    .mockResolvedValueOnce({
      data: { items: [{ competencia: "2008-05", measured_energy_kwh: null }] },
      pagination: { total_pages: 2 },
      metadata: meta,
    });
  const { result } = renderHook(
    () => useUCSeries("UC-A", "2000-01", "2010-12", true),
    { wrapper },
  );
  await waitFor(() => expect(result.current.isSuccess).toBe(true));
  expect(result.current.data?.items).toHaveLength(101);
});

it("recusa série paginada quando a publicação muda entre páginas", async () => {
  const meta = {
    period: { start: "2000-01", end: "2010-12" },
    source: { version: "v2-a" },
  };
  vi.mocked(apiClient)
    .mockResolvedValueOnce({
      data: { items: [] },
      pagination: { total_pages: 2 },
      metadata: meta,
    })
    .mockResolvedValueOnce({
      data: { items: [] },
      pagination: { total_pages: 2 },
      metadata: { ...meta, source: { version: "v2-b" } },
    });
  const { result } = renderHook(
    () => useUCSeries("UC-A", "2000-01", "2010-12", true),
    { wrapper },
  );
  await waitFor(() => expect(result.current.isError).toBe(true));
  expect(result.current.data).toBeUndefined();
});
