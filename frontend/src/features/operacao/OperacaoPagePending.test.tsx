import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import OperacaoPage from "./OperacaoPage";
import { rankingFixture } from "./fixtures.test-support";

afterEach(() => vi.unstubAllGlobals());

function respond(value: unknown) {
  return new Response(JSON.stringify(value), { status: 200 });
}

it("não mostra texto de carregamento do consolidado Gold enquanto aguarda a resposta", async () => {
  const finishSummaries: Array<(response: Response) => void> = [];
  const fetch = vi.fn(async (input: RequestInfo | URL) => {
    const url = new URL(String(input), window.location.origin);
    if (url.pathname.endsWith("/options"))
      return respond({
        data: {
          competencias: ["2025-01"],
          municipios: [],
          alimentadores: [],
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
            version: "test",
            is_demo: false,
            updated_at: "2026-10-29T00:00:00Z",
          },
          limitations: [],
          temporal_scope: "snapshot",
          schema_version: "gold-csv-v2",
          fingerprint: "e".repeat(64),
        },
      });
    if (url.pathname.endsWith("/summary"))
      return new Promise<Response>((resolve) => {
        finishSummaries.push(resolve);
      });
    return respond(rankingFixture);
  });
  vi.stubGlobal("fetch", fetch);
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/operacao"]}>
        <OperacaoPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );

  await waitFor(() =>
    expect(
      fetch.mock.calls.some(([input]) => String(input).includes("/summary")),
    ).toBe(true),
  );
  expect(
    screen.queryByText("Carregando consolidado Gold…"),
  ).not.toBeInTheDocument();
  finishSummaries.forEach((finishSummary) => finishSummary(respond({})));
  expect(
    await screen.findByText("Não foi possível carregar o consolidado Gold."),
  ).toBeVisible();
});
