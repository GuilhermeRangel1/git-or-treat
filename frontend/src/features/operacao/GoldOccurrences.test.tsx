import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, expect, it, vi } from "vitest";
import GoldOccurrences from "./GoldOccurrences";

const apiClient = vi.hoisted(() => vi.fn());

vi.mock("@/shared/api/client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/shared/api/client")>()),
  apiClient,
}));
vi.mock("@/shared/analytics/goldPublication", () => ({
  useGoldPublicationKey: () => "publicacao-teste",
}));

const metadata = {
  contract_version: "2.0.0",
  source: {
    kind: "gold",
    is_demo: false,
    version: "v1",
    updated_at: "2026-11-01T00:00:00Z",
  },
  schema_version: "gold-csv-v2",
  fingerprint: "a".repeat(64),
  status: "available",
  temporal_scope: "monthly",
  limitations: [],
  filters: {
    municipio: null,
    bairro: null,
    classe: null,
    alimentador: "AL-01",
  },
  period: { granularity: "month", start: "2025-01", end: "2025-03" },
};

function pageResponse(page: number) {
  return {
    metadata,
    data: [
      {
        event_id: `EV-${page}`,
        uc_id: "UC-1",
        opened_at: "2025-02-10T12:00:00Z",
        cause: null,
        duration_hours: 1.5,
      },
    ],
    pagination: { page, page_size: 20, total: 60, total_pages: 3 },
  };
}

function pageOf(url: string) {
  return Number(new URL(url, "http://localhost").searchParams.get("page"));
}

beforeEach(() => {
  apiClient.mockReset();
});

it("pagina as ocorrências por número e mantém a página atual visível enquanto carrega", async () => {
  const user = userEvent.setup();
  let release: () => void = () => {};
  apiClient.mockImplementation(async (url: string) => {
    const page = pageOf(url);
    if (page === 2) await new Promise<void>((resolve) => (release = resolve));
    return pageResponse(page);
  });

  render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <GoldOccurrences feeder="AL-01" start="2025-01" end="2025-03" />
    </QueryClientProvider>,
  );

  expect(await screen.findByText("EV-1")).toBeVisible();
  expect(screen.getByRole("button", { name: "Página 1" })).toHaveAttribute(
    "aria-current",
    "page",
  );

  await user.click(screen.getByRole("button", { name: "Página 2" }));

  // Enquanto a página 2 não chega, a 1 e a paginação continuam na tela.
  expect(screen.getByText("EV-1")).toBeVisible();
  expect(screen.getByRole("button", { name: "Página 3" })).toBeEnabled();

  release();
  expect(await screen.findByText("EV-2")).toBeVisible();
  expect(screen.getByRole("button", { name: "Página 2" })).toHaveAttribute(
    "aria-current",
    "page",
  );
  expect(apiClient).toHaveBeenCalledTimes(2);
  await user.selectOptions(screen.getByLabelText("Por página"), "50");
  await waitFor(() => expect(apiClient).toHaveBeenCalledTimes(3));
  const request = new URL(
    String(apiClient.mock.calls[2][0]),
    "http://localhost",
  );
  expect(request.searchParams.get("page_size")).toBe("50");
  expect(request.searchParams.get("page")).toBe("1");
});
