import { beforeEach, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import AppProviders from "@/app/providers";
import { AppRoutes } from "@/app/router";

const response = {
  data: {
    metrics: [
      {
        id: "billed_amount",
        label: "Valor faturado",
        value: 0,
        unit: "BRL",
        status: "available",
        limitations: [],
      },
    ],
  },
  metadata: {
    contract_version: "1.0.0",
    status: "available",
    period: { start: "2025-01", end: "2025-02", granularity: "month" },
    filters: {
      municipio: null,
      bairro: null,
      classe: null,
      alimentador: null,
    },
    source: {
      kind: "synthetic",
      version: "dev01-v1",
      is_demo: true,
      updated_at: "2026-10-20T00:00:00Z",
    },
    limitations: ["Dados sintéticos; não constituem diagnóstico da V-Energy."],
  },
};

beforeEach(() => {
  localStorage.clear();
  vi.stubGlobal(
    "matchMedia",
    vi.fn().mockReturnValue({
      matches: false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }),
  );
});

it("consulta os filtros aplicados e apresenta zero válido com proveniência", async () => {
  const fetchSpy = vi
    .fn()
    .mockResolvedValue(new Response(JSON.stringify(response), { status: 200 }));
  vi.stubGlobal("fetch", fetchSpy);
  const user = userEvent.setup();
  render(
    <AppProviders>
      <MemoryRouter initialEntries={["/dev/contratos"]}>
        <AppRoutes />
      </MemoryRouter>
    </AppProviders>,
  );

  expect(
    await screen.findByRole("heading", { name: "Diagnóstico de contratos" }),
  ).toBeVisible();
  expect(screen.getByText(/dados sintéticos de demonstração/i)).toBeVisible();
  await user.type(screen.getByLabelText("Município"), "Porto Alegre");
  await user.type(screen.getByLabelText("Classe"), "Residencial");
  await user.click(screen.getByRole("button", { name: "Consultar" }));

  expect(await screen.findByText("Valor faturado")).toBeVisible();
  expect(screen.getByText(/R\$\s0,00/)).toBeVisible();
  expect(
    screen.getByText(
      "Dados sintéticos; não constituem diagnóstico da V-Energy.",
    ),
  ).toBeVisible();
  await waitFor(() => expect(fetchSpy).toHaveBeenCalledTimes(1));
  const [url, options] = fetchSpy.mock.calls[0] as [string, RequestInit];
  expect(url).toContain("/api/v1/kpis?");
  expect(url).toContain("competencia_inicio=2025-01");
  expect(url).toContain("competencia_fim=2025-02");
  expect(url).toContain("municipio=Porto+Alegre");
  expect(url).toContain("classe=Residencial");
  expect(options.signal).toBeInstanceOf(AbortSignal);
});

it.each(["empty", "partial", "unavailable"] as const)(
  "explica o estado %s devolvido pela API",
  async (status) => {
    const body = structuredClone(response);
    body.metadata.status = status;
    body.data.metrics =
      status === "empty" || status === "unavailable" ? [] : body.data.metrics;
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(new Response(JSON.stringify(body), { status: 200 })),
    );
    const user = userEvent.setup();
    render(
      <AppProviders>
        <MemoryRouter initialEntries={["/dev/contratos"]}>
          <AppRoutes />
        </MemoryRouter>
      </AppProviders>,
    );
    await user.click(await screen.findByRole("button", { name: "Consultar" }));

    const message = {
      empty: "Nenhum registro encontrado para os filtros aplicados.",
      partial:
        "Resultado parcial. Consulte as limitações e a cobertura informadas.",
      unavailable: "Fonte indisponível para este recorte.",
    }[status];
    expect(await screen.findByText(message)).toBeVisible();
  },
);

it("omite município e classe vazios e diferencia uma resposta fora do contrato", async () => {
  const fetchSpy = vi
    .fn()
    .mockResolvedValueOnce(
      new Response(JSON.stringify({ wrong: true }), { status: 200 }),
    );
  vi.stubGlobal("fetch", fetchSpy);
  const user = userEvent.setup();
  render(
    <AppProviders>
      <MemoryRouter initialEntries={["/dev/contratos"]}>
        <AppRoutes />
      </MemoryRouter>
    </AppProviders>,
  );
  await user.click(await screen.findByRole("button", { name: "Consultar" }));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "A resposta recebida não segue o contrato de indicadores esperado.",
  );
  const [url] = fetchSpy.mock.calls[0] as [string];
  expect(url).toContain("competencia_inicio=2025-01");
  expect(url).toContain("competencia_fim=2025-02");
  expect(url).not.toContain("municipio=");
  expect(url).not.toContain("classe=");
});

it("mostra indisponibilidade HTTP 503 com explicação", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "Unavailable" }), {
        status: 503,
      }),
    ),
  );
  const user = userEvent.setup();
  render(
    <AppProviders>
      <MemoryRouter initialEntries={["/dev/contratos"]}>
        <AppRoutes />
      </MemoryRouter>
    </AppProviders>,
  );
  await user.click(await screen.findByRole("button", { name: "Consultar" }));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "A fonte de indicadores está indisponível.",
  );
});

it("permite repetir a mesma consulta depois de um erro e receber o resultado", async () => {
  const fetchSpy = vi
    .fn()
    .mockRejectedValueOnce(new Error("offline"))
    .mockResolvedValueOnce(
      new Response(JSON.stringify(response), { status: 200 }),
    );
  vi.stubGlobal("fetch", fetchSpy);
  const user = userEvent.setup();
  render(
    <AppProviders>
      <MemoryRouter initialEntries={["/dev/contratos"]}>
        <AppRoutes />
      </MemoryRouter>
    </AppProviders>,
  );
  await user.click(await screen.findByRole("button", { name: "Consultar" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Não foi possível conectar à API.",
  );

  await user.click(screen.getByRole("button", { name: "Tentar novamente" }));

  expect(await screen.findByText("Valor faturado")).toBeVisible();
  expect(fetchSpy).toHaveBeenCalledTimes(2);
});

it("mantém visível o recorte novo quando uma resposta antiga termina depois", async () => {
  const resolvers: Array<(response: Response) => void> = [];
  const fetchSpy = vi.fn().mockImplementation(
    () =>
      new Promise<Response>((resolve) => {
        resolvers.push(resolve);
      }),
  );
  vi.stubGlobal("fetch", fetchSpy);
  const user = userEvent.setup();
  render(
    <AppProviders>
      <MemoryRouter initialEntries={["/dev/contratos"]}>
        <AppRoutes />
      </MemoryRouter>
    </AppProviders>,
  );
  const municipality = await screen.findByLabelText("Município");
  await user.type(municipality, "Antigo");
  await user.click(screen.getByRole("button", { name: "Consultar" }));
  await waitFor(() => expect(fetchSpy).toHaveBeenCalledTimes(1));

  await user.clear(municipality);
  await user.type(municipality, "Novo");
  await user.click(screen.getByRole("button", { name: "Consultar" }));
  await waitFor(() => expect(fetchSpy).toHaveBeenCalledTimes(2));

  const newer = structuredClone(response);
  newer.data.metrics[0]!.label = "Métrica do recorte novo";
  resolvers[1]!(new Response(JSON.stringify(newer), { status: 200 }));
  expect(await screen.findByText("Métrica do recorte novo")).toBeVisible();

  const older = structuredClone(response);
  older.data.metrics[0]!.label = "Métrica do recorte antigo";
  resolvers[0]!(new Response(JSON.stringify(older), { status: 200 }));
  await waitFor(() =>
    expect(
      screen.queryByText("Métrica do recorte antigo"),
    ).not.toBeInTheDocument(),
  );
  expect(screen.getByText("Métrica do recorte novo")).toBeVisible();
});

it("não registra a rota de diagnóstico em produção", async () => {
  vi.stubEnv("DEV", false);
  vi.resetModules();
  const [{ AppRoutes: ProductionAppRoutes }, { default: ProductionProviders }] =
    await Promise.all([import("./router"), import("./providers")]);
  const fetchSpy = vi.fn();
  vi.stubGlobal("fetch", fetchSpy);
  render(
    <ProductionProviders>
      <MemoryRouter initialEntries={["/dev/contratos"]}>
        <ProductionAppRoutes />
      </MemoryRouter>
    </ProductionProviders>,
  );

  expect(
    await screen.findByRole("heading", {
      name: "Sua rede, em perspectiva.",
    }),
  ).toBeVisible();
  expect(fetchSpy).not.toHaveBeenCalled();
});
