import { beforeEach, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import InspecoesPage from "./InspecoesPage";
import { decodeDetail, decodeQueue } from "./contract";

const item = {
  uc_id: "UC-1004",
  municipality: "Recife",
  neighborhood: "Centro",
  class_name: "Residencial",
  feeder_id: "AL-03",
  priority: 0.92,
  reason: "Lacuna de leitura e medidor retirado",
  potential_recoverable_energy_kwh: 45,
  indicators: ["reading_gap", "meter_removed"],
  signals: [
    { id: "reading_gap", label: "Lacuna de leitura", weight: 0.6 },
    { id: "meter_removed", label: "Medidor retirado", weight: 0.32 },
  ],
};
const second = {
  ...item,
  uc_id: "UC-1002",
  priority: 0.61,
  potential_recoverable_energy_kwh: null,
};
const metadata = {
  contract_version: "1.0.0",
  status: "partial",
  period: { start: "2025-01", end: "2025-02" },
  source: {
    kind: "synthetic",
    version: "dev03-v1",
    is_demo: true,
    updated_at: "2026-10-21T00:00:00Z",
  },
  limitations: ["Dados sintéticos."],
};
const options = {
  municipio: ["Olinda", "Recife"],
  bairro: ["Centro"],
  classe: ["Residencial"],
  alimentador: ["AL-03"],
};
function envelope(
  items = [item, second],
  page = 1,
  size = 10,
  total = items.length,
) {
  return {
    data: {
      items,
      filter_options: options,
      summary: {
        total_units: total,
        highest_priority: total ? 0.92 : null,
        estimated_units: total ? 1 : 0,
        unavailable_estimate_units: Math.max(0, total - 1),
      },
    },
    pagination: {
      page,
      page_size: size,
      total,
      total_pages: Math.ceil(total / size),
    },
    metadata,
  };
}
const detail = {
  data: {
    ...item,
    rule_version: "dev05-v1",
    signals: [
      { id: "reading_gap", label: "Lacuna de leitura", weight: 0.6 },
      { id: "meter_removed", label: "Medidor retirado", weight: 0.32 },
    ],
    estimate_evidence: {
      baseline_kwh: 90,
      observed_kwh: 45,
      horizon_months: 1,
      reference: "Cenário sintético de um mês.",
      unavailable_reason: null,
    },
    limitations: ["Suspeita não confirma irregularidade."],
  },
  metadata,
};
function Location() {
  return <span aria-label="URL atual">{useLocation().search}</span>;
}
function mount(
  url = "/inspecoes",
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } }),
) {
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[url]}>
        <InspecoesPage />
        <Location />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}
function respond(value: unknown, status = 200) {
  return new Response(JSON.stringify(value), { status });
}
beforeEach(() => {
  vi.restoreAllMocks();
});

it("abre evidências reproduzíveis e volta preservando a página e os filtros", async () => {
  const fetch = vi
    .fn()
    .mockImplementation(async (url: string) =>
      url.includes("/queue/UC-")
        ? respond(detail)
        : respond(envelope([item], 2, 1, 2)),
    );
  vi.stubGlobal("fetch", fetch);
  const user = userEvent.setup();
  mount("/inspecoes?municipio=Recife&page_size=1&page=2");
  expect(
    await screen.findByRole("link", { name: "Ver evidências de UC-1004" }),
  ).toBeVisible();
  await user.click(
    screen.getByRole("link", { name: "Ver evidências de UC-1004" }),
  );
  expect(
    await screen.findByRole("heading", {
      name: "Como a prioridade foi calculada",
    }),
  ).toBeVisible();
  expect(screen.getByText("0,92 / 1")).toBeVisible();
  expect(screen.getByText("max(0; 90 − 45) × 1 = 45 kWh")).toBeVisible();
  await user.click(screen.getByRole("link", { name: "Voltar à fila" }));
  expect(await screen.findByText("Página 2 de 2")).toBeVisible();
  expect(screen.getByLabelText("URL atual")).toHaveTextContent(
    "municipio=Recife&page_size=1&page=2",
  );
});

it("aplica filtros e ordenação na API, reiniciando a página, e trata fila vazia", async () => {
  const fetch = vi
    .fn()
    .mockImplementation(async (url: string) =>
      respond(url.includes("municipio=Olinda") ? envelope([]) : envelope()),
    );
  vi.stubGlobal("fetch", fetch);
  const user = userEvent.setup();
  mount();
  await screen.findByRole("link", { name: "Ver evidências de UC-1004" });
  await user.click(screen.getByText("Ajustar filtros"));
  await user.selectOptions(screen.getByLabelText("Município"), "Olinda");
  await user.selectOptions(
    screen.getByLabelText("Ordenar por"),
    "potential_recoverable_energy_kwh",
  );
  await user.selectOptions(screen.getByLabelText("Direção"), "asc");
  await user.click(screen.getByRole("button", { name: "Aplicar" }));
  expect(
    await screen.findByText(
      "Nenhuma suspeita neste recorte. Isso não comprova ausência de perdas.",
    ),
  ).toBeVisible();
  const url = new URL(fetch.mock.calls.at(-1)![0], window.location.origin);
  expect(url.searchParams.get("municipio")).toBe("Olinda");
  expect(url.searchParams.get("order_by")).toBe(
    "potential_recoverable_energy_kwh",
  );
  expect(url.searchParams.get("direction")).toBe("asc");
  expect(url.searchParams.get("page")).toBe("1");
});

it("pagina pelo servidor e mantém estimativa ausente distinta de zero", async () => {
  const fetch = vi
    .fn()
    .mockImplementation(async (url: string) =>
      respond(
        url.includes("page=2")
          ? envelope([second], 2, 1, 2)
          : envelope([item], 1, 1, 2),
      ),
    );
  vi.stubGlobal("fetch", fetch);
  const user = userEvent.setup();
  mount("/inspecoes?page_size=1");
  await screen.findByText("Página 1 de 2");
  await user.click(screen.getByRole("button", { name: "Próxima" }));
  expect(await screen.findByText("Página 2 de 2")).toBeVisible();
  expect(screen.getByText("Estimativa indisponível")).toBeVisible();
  const summary = within(
    screen.getByRole("region", { name: "Resumo do recorte da fila" }),
  );
  expect(summary.getByText("0,92 / 1")).toBeVisible();
  expect(summary.getByText("1 de 2")).toBeVisible();
  expect(screen.getByRole("button", { name: "Próxima" })).toBeDisabled();
});

it("mostra carregamento, erro e nova tentativa sem apresentar a falha como fila vazia", async () => {
  let release: ((value: Response) => void) | undefined;
  const fetch = vi
    .fn()
    .mockImplementationOnce(
      () =>
        new Promise<Response>((resolve) => {
          release = resolve;
        }),
    )
    .mockImplementationOnce(() => respond(envelope()));
  vi.stubGlobal("fetch", fetch);
  mount();
  expect(screen.getByRole("status")).toHaveTextContent("Carregando fila");
  await waitFor(() => expect(release).toBeDefined());
  release!(respond({}, 503));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Não foi possível consultar",
  );
  expect(screen.queryByText(/Nenhuma suspeita/)).not.toBeInTheDocument();
  await userEvent.click(
    screen.getByRole("button", { name: "Tentar novamente" }),
  );
  expect(
    await screen.findByRole("link", { name: "Ver evidências de UC-1004" }),
  ).toBeVisible();
});

it("avisa atualização em segundo plano e preserva a última consulta quando ela falha", async () => {
  let release: ((value: Response) => void) | undefined;
  const fetch = vi
    .fn()
    .mockResolvedValueOnce(respond(envelope()))
    .mockImplementationOnce(
      () =>
        new Promise<Response>((resolve) => {
          release = resolve;
        }),
    );
  vi.stubGlobal("fetch", fetch);
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  mount("/inspecoes", client);
  await screen.findByRole("link", { name: "Ver evidências de UC-1004" });
  void client.invalidateQueries();
  expect(
    await screen.findByText(
      "Atualizando evidências; exibindo a última consulta válida.",
    ),
  ).toBeVisible();
  expect(
    screen.getByRole("link", { name: "Ver evidências de UC-1004" }),
  ).toBeVisible();
  await waitFor(() => expect(release).toBeDefined());
  release!(respond({}, 503));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Exibindo a última consulta válida",
  );
  expect(
    screen.getByRole("link", { name: "Ver evidências de UC-1004" }),
  ).toBeVisible();
});

it("aceita link direto e informa suspeita inexistente", async () => {
  const fetch = vi.fn().mockResolvedValue(respond({}, 404));
  vi.stubGlobal("fetch", fetch);
  mount("/inspecoes?uc=UC-9999");
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Suspeita não encontrada",
  );
  expect(fetch.mock.calls[0][0]).toContain("/queue/UC-9999");
});

it("bloqueia parâmetros repetidos sem consultar a API", () => {
  const fetch = vi.fn();
  vi.stubGlobal("fetch", fetch);
  mount("/inspecoes?page=1&page=2");
  expect(screen.getByRole("alert")).toHaveTextContent(
    "Parâmetros de inspeção inválidos",
  );
  expect(fetch).not.toHaveBeenCalled();
});

it("rejeita contratos inválidos antes de apresentar métricas", () => {
  expect(() =>
    decodeQueue({
      ...envelope(),
      data: {
        ...envelope().data,
        summary: {
          total_units: 2,
          highest_priority: 0.92,
          estimated_units: 2,
          unavailable_estimate_units: 1,
        },
      },
    }),
  ).toThrow();
  expect(() =>
    decodeQueue({
      ...envelope(),
      data: { ...envelope().data, items: [{ ...item, priority: 92 }] },
    }),
  ).toThrow();
  expect(() =>
    decodeDetail({
      ...detail,
      data: {
        ...detail.data,
        estimate_evidence: {
          ...detail.data.estimate_evidence,
          horizon_months: 0,
        },
      },
    }),
  ).toThrow();
  expect(() =>
    decodeQueue({
      ...envelope(),
      pagination: { page: 1, page_size: 10, total: 2, total_pages: 9 },
    }),
  ).toThrow();
});
