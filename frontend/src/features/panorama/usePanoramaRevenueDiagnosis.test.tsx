import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import TestProviders from "@/shared/test/TestProviders";
import {
  acceptGoldIdentity,
  resetGoldPublication,
} from "@/shared/analytics/goldPublication";
import { usePanoramaRevenueDiagnosis } from "./usePanoramaRevenueDiagnosis";
import {
  PUBLICATION,
  revenueDiagnosis,
  revenueResponse,
  revenueWindow,
  WINDOWS,
} from "./revenue-diagnosis.test-support";

const fetchMock = vi.fn();
const wrapper = ({ children }: { children: ReactNode }) => (
  <TestProviders>{children}</TestProviders>
);
const requests = () =>
  fetchMock.mock.calls.map(
    ([input]) => new URL(String(input), "http://localhost:5173"),
  );
const scope = {
  municipio: "todos",
  classe: "todas",
  latestPeriod: "2026-06",
};

beforeEach(() => {
  resetGoldPublication();
  acceptGoldIdentity(PUBLICATION);
  fetchMock.mockReset();
  fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
    const url = new URL(String(input), "http://localhost:5173");
    return new Response(JSON.stringify(revenueResponse(url)));
  });
  vi.stubGlobal("fetch", fetchMock);
});

it("pede o diagnóstico com a última competência como início e fim, sem filtros de todos", async () => {
  const { result } = renderHook(() => usePanoramaRevenueDiagnosis(scope), {
    wrapper,
  });
  await waitFor(() => expect(result.current.isSuccess).toBe(true));

  const [request] = requests();
  expect(request.pathname).toBe("/api/v1/revenue");
  expect(Object.fromEntries(request.searchParams)).toEqual({
    competencia_inicio: "2026-06",
    competencia_fim: "2026-06",
    group_by: "municipio",
    include_diagnosis: "true",
    expected_lote: PUBLICATION.lote,
    expected_fingerprint: PUBLICATION.fingerprint,
  });
});

it("devolve o diagnóstico e as janelas da mesma resposta", async () => {
  const { result } = renderHook(() => usePanoramaRevenueDiagnosis(scope), {
    wrapper,
  });
  await waitFor(() => expect(result.current.isSuccess).toBe(true));

  expect(fetchMock).toHaveBeenCalledTimes(1);
  expect(result.current.data?.diagnosis).toMatchObject(revenueDiagnosis());
  expect(result.current.data?.window).toMatchObject(revenueWindow());
  expect(result.current.data?.window?.windows).toEqual(WINDOWS);
});

it("não refaz a consulta quando só a competência muda", async () => {
  const { result, rerender } = renderHook(
    (props) => usePanoramaRevenueDiagnosis(props),
    { wrapper, initialProps: scope },
  );
  await waitFor(() => expect(result.current.isSuccess).toBe(true));

  rerender({ ...scope, latestPeriod: "2026-05" });
  await new Promise((resolve) => setTimeout(resolve, 0));

  expect(fetchMock).toHaveBeenCalledTimes(1);
  expect(result.current.data?.window?.windows).toEqual(WINDOWS);
});

it("refaz a consulta com os filtros quando município ou classe mudam", async () => {
  const { result, rerender } = renderHook(
    (props) => usePanoramaRevenueDiagnosis(props),
    { wrapper, initialProps: scope },
  );
  await waitFor(() => expect(result.current.isSuccess).toBe(true));

  rerender({ ...scope, municipio: "Recife" });
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
  expect(requests()[1].searchParams.get("municipio")).toBe("Recife");
  expect(requests()[1].searchParams.has("classe")).toBe(false);

  rerender({ ...scope, municipio: "Recife", classe: "Residencial" });
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
  expect(requests()[2].searchParams.get("classe")).toBe("Residencial");
});

it("refaz a consulta quando a publicação muda", async () => {
  const { result } = renderHook(() => usePanoramaRevenueDiagnosis(scope), {
    wrapper,
  });
  await waitFor(() => expect(result.current.isSuccess).toBe(true));

  act(() => resetGoldPublication());
  await waitFor(() =>
    expect(fetchMock.mock.calls.length).toBeGreaterThanOrEqual(2),
  );
});

it("expõe erro quando a API responde com falha", async () => {
  fetchMock.mockResolvedValue(new Response("{}", { status: 500 }));
  const { result } = renderHook(() => usePanoramaRevenueDiagnosis(scope), {
    wrapper,
  });
  await waitFor(() => expect(result.current.isError).toBe(true));
  expect(result.current.data).toBeUndefined();
});

it("recusa uma resposta de outro recorte", async () => {
  fetchMock.mockImplementation(async () => {
    const other = new URL(
      "http://localhost:5173/?competencia_inicio=2026-06&competencia_fim=2026-06&municipio=Olinda",
    );
    return new Response(JSON.stringify(revenueResponse(other)));
  });
  const { result } = renderHook(() => usePanoramaRevenueDiagnosis(scope), {
    wrapper,
  });
  await waitFor(() => expect(result.current.isError).toBe(true));
});
