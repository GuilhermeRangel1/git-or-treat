import { beforeEach, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import type { Order } from "@/shared/api/orders";
import TestProviders from "@/shared/test/TestProviders";
import OrdensPage from "./OrdensPage";

vi.mock("./OrderActionsDialog", () => ({
  default: ({ order, open }: { order: Order | null; open: boolean }) =>
    open && order ? (
      <div role="dialog" aria-label={`Ações ${order.id}`}>
        <p>{order.uc_id}</p>
      </div>
    ) : null,
}));

vi.mock("./OrderFoundationsDialog", () => ({
  default: ({ order, open }: { order: Order | null; open: boolean }) =>
    open && order ? (
      <div role="dialog" aria-label={`Fundamentos ${order.id}`}>
        <p>{order.reason}</p>
      </div>
    ) : null,
}));

function order(overrides: Partial<Order> = {}): Order {
  return {
    id: 41,
    uc_id: "UC-1041",
    reason: "Consumo incompatível com o histórico.",
    priority: "ALTA",
    status: "PENDENTE",
    notes: null,
    result: null,
    created_at: "2026-10-23T12:00:00Z",
    updated_at: "2026-10-24T01:30:00Z",
    suspicion_reference: "snapshot-1",
    ...overrides,
  };
}

function response(
  items: Order[],
  page = 1,
  total = items.length,
  pageSize = 20,
) {
  return new Response(
    JSON.stringify({
      items,
      pagination: {
        page,
        page_size: pageSize,
        total,
        total_pages: total === 0 ? 0 : Math.ceil(total / pageSize),
      },
    }),
    { status: 200, headers: { "Content-Type": "application/json" } },
  );
}

function renderPage(entry = "/ordens", client?: QueryClient) {
  const page = (
    <MemoryRouter initialEntries={[entry]}>
      <OrdensPage />
    </MemoryRouter>
  );
  if (client) {
    return render(
      <QueryClientProvider client={client}>{page}</QueryClientProvider>,
    );
  }
  return render(<TestProviders>{page}</TestProviders>);
}

async function firstOrderAction() {
  return (
    await screen.findAllByRole("button", {
      name: "Ações da ordem OS-000041 da UC UC-1041",
    })
  )[0];
}

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation(() => Promise.resolve(response([order()]))),
  );
});

it("apresenta a ordem retornada pela API e abre ações para a UC selecionada", async () => {
  const user = userEvent.setup();
  renderPage();

  const rowAction = await firstOrderAction();
  expect(
    within(screen.getByRole("table")).getByText("OS-000041"),
  ).toBeInTheDocument();
  expect(screen.getByText(/Ambiente demonstrativo/)).toHaveTextContent(
    "23/10/2026, 22:30 (Recife)",
  );
  expect(screen.queryByText(/16\/10\/2026/)).not.toBeInTheDocument();

  await user.click(rowAction);
  expect(screen.getByRole("dialog", { name: "Ações 41" })).toHaveTextContent(
    "UC-1041",
  );
});

it("recusa parâmetros repetidos antes do fetch e permite limpar a URL inválida", async () => {
  const user = userEvent.setup();
  const fetchMock = vi.mocked(fetch);
  renderPage("/ordens?status=PENDENTE&status=CANCELADA");

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "inválidos ou estão repetidos",
  );
  expect(fetchMock).not.toHaveBeenCalled();

  await user.click(screen.getByRole("button", { name: "Limpar filtros" }));
  await firstOrderAction();
  expect(fetchMock).toHaveBeenCalledTimes(1);
  const requestedUrl = new URL(
    String(fetchMock.mock.calls[0][0]),
    location.origin,
  );
  expect(requestedUrl.pathname).toBe("/api/v1/inspections/orders/search");
  expect(requestedUrl.searchParams.get("page")).toBe("1");
  expect(requestedUrl.searchParams.get("page_size")).toBe("20");
});

it.each([
  ["status=EM_ANALISE", "O estado informado não é válido."],
  ["priority=CRITICA", "A prioridade informada não é válida."],
])(
  "recusa valor fora do contrato na URL sem consultar a API: %s",
  async (query, errorMessage) => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    renderPage(`/ordens?${query}`);

    expect(await screen.findByRole("alert")).toHaveTextContent(errorMessage);
    expect(fetchMock).not.toHaveBeenCalled();
  },
);

it("identifica o carregamento inicial enquanto a API ainda não respondeu", async () => {
  let release: ((value: Response) => void) | undefined;
  const fetchMock = vi.fn().mockImplementation(
    () =>
      new Promise<Response>((resolve) => {
        release = resolve;
      }),
  );
  vi.stubGlobal("fetch", fetchMock);
  renderPage();

  expect(await screen.findByRole("status")).toHaveTextContent(
    "Consultando ordens",
  );
  await waitFor(() => expect(release).toBeDefined());
  release!(response([order()]));
  await firstOrderAction();
});

it("permite repetir uma consulta que falhou sem expor detalhes internos", async () => {
  const user = userEvent.setup();
  const fetchMock = vi
    .fn()
    .mockImplementationOnce(() =>
      Promise.resolve(
        new Response(JSON.stringify({ detail: "diagnóstico interno" }), {
          status: 503,
        }),
      ),
    )
    .mockImplementationOnce(() => Promise.resolve(response([order()])));
  vi.stubGlobal("fetch", fetchMock);
  renderPage();

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Não foi possível consultar as ordens",
  );
  expect(screen.getByRole("alert")).not.toHaveTextContent(
    "diagnóstico interno",
  );

  await user.click(screen.getByRole("button", { name: "Tentar novamente" }));
  await firstOrderAction();
  expect(fetchMock).toHaveBeenCalledTimes(2);
});

it("normaliza UC e consulta os filtros recebidos na URL", async () => {
  const fetchMock = vi
    .fn()
    .mockImplementation(() =>
      Promise.resolve(response([order({ status: "EM_ANDAMENTO" })], 2, 6, 5)),
    );
  vi.stubGlobal("fetch", fetchMock);
  renderPage(
    "/ordens?uc_id=%20UC-1041%20&status=EM_ANDAMENTO&priority=ALTA&page=2&page_size=5",
  );

  await firstOrderAction();
  expect(screen.getByText(/Recorte aplicado/)).toHaveTextContent(
    "UC UC-1041 · Estado Em andamento · Prioridade Alta · 5 por página",
  );
  const requestedUrl = new URL(
    String(fetchMock.mock.calls[0][0]),
    location.origin,
  );
  expect(requestedUrl.searchParams.get("uc_id")).toBe("UC-1041");
  expect(requestedUrl.searchParams.get("status")).toBe("EM_ANDAMENTO");
  expect(requestedUrl.searchParams.get("priority")).toBe("ALTA");
  expect(requestedUrl.searchParams.get("page")).toBe("2");
  expect(requestedUrl.searchParams.get("page_size")).toBe("5");
});

it("preserva os filtros da URL ao avançar a página", async () => {
  const user = userEvent.setup();
  const fetchMock = vi.fn().mockImplementation((input: string) => {
    const url = new URL(input, location.origin);
    const page = Number(url.searchParams.get("page"));
    return Promise.resolve(response([order()], page, 6, 5));
  });
  vi.stubGlobal("fetch", fetchMock);
  renderPage("/ordens?uc_id=UC-1041&status=PENDENTE&priority=ALTA&page_size=5");

  await screen.findByRole("button", { name: "Próxima" });
  await user.click(screen.getByRole("button", { name: "Próxima" }));
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
  const requestedUrl = new URL(
    String(fetchMock.mock.calls[1][0]),
    location.origin,
  );
  expect(requestedUrl.searchParams.get("uc_id")).toBe("UC-1041");
  expect(requestedUrl.searchParams.get("status")).toBe("PENDENTE");
  expect(requestedUrl.searchParams.get("priority")).toBe("ALTA");
  expect(requestedUrl.searchParams.get("page")).toBe("2");
  expect(requestedUrl.searchParams.get("page_size")).toBe("5");
});

it("trata página acima do total como recorte vazio válido", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response([], 9, 2)));
  renderPage("/ordens?page=9");

  expect(
    await screen.findByText(/Esta página não contém ordens/),
  ).toHaveTextContent("total do recorte é 2");
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

it("mantém a lista identificada como desatualizada se uma atualização falha", async () => {
  let release: ((value: Response) => void) | undefined;
  const fetchMock = vi
    .fn()
    .mockImplementationOnce(() => Promise.resolve(response([order()])))
    .mockImplementationOnce(
      () =>
        new Promise<Response>((resolve) => {
          release = resolve;
        }),
    );
  vi.stubGlobal("fetch", fetchMock);
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  renderPage("/ordens", client);
  await firstOrderAction();

  void client.invalidateQueries({ queryKey: ["orders", "list"] });
  expect(await screen.findByRole("status")).toHaveTextContent(
    "Atualizando ordens",
  );
  await waitFor(() => expect(release).toBeDefined());
  release!(
    new Response(JSON.stringify({ detail: "diagnóstico interno" }), {
      status: 503,
    }),
  );

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "última consulta válida continua exibida",
  );
  expect(screen.getByRole("alert")).not.toHaveTextContent(
    "diagnóstico interno",
  );
  expect(await firstOrderAction()).toBeInTheDocument();
});
