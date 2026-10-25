import { beforeEach, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation, useNavigate } from "react-router-dom";
import AppProviders from "@/app/providers";
import { AppRoutes } from "@/app/router";
import type { KpisEnvelope } from "@/features/dev-contracts/contract";

const response: KpisEnvelope = {
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

function HistoryControls() {
  const location = useLocation();
  const navigate = useNavigate();
  return (
    <div>
      <output aria-label="URL atual">
        {location.pathname}
        {location.search}
      </output>
      <button type="button" onClick={() => void navigate(-1)}>
        Voltar
      </button>
      <button type="button" onClick={() => void navigate(1)}>
        Avançar
      </button>
    </div>
  );
}

function renderDiagnostic(initialEntry = "/dev/contratos") {
  return render(
    <AppProviders>
      <MemoryRouter initialEntries={[initialEntry]}>
        <HistoryControls />
        <AppRoutes />
      </MemoryRouter>
    </AppProviders>,
  );
}

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

it("mantém o rascunho local e restaura a consulta ao abrir o link aplicado", async () => {
  const fetchSpy = vi
    .fn()
    .mockImplementation(
      async () => new Response(JSON.stringify(response), { status: 200 }),
    );
  vi.stubGlobal("fetch", fetchSpy);
  const user = userEvent.setup();
  const view = renderDiagnostic();
  const municipality = await screen.findByLabelText("Município");
  await user.type(municipality, "  Porto Alegre  ");
  await user.type(screen.getByLabelText("Classe"), " Residencial ");

  expect(screen.getByLabelText("URL atual")).toHaveTextContent(
    /^\/dev\/contratos$/,
  );
  expect(fetchSpy).not.toHaveBeenCalled();
  await user.click(screen.getByRole("button", { name: "Consultar" }));
  expect(await screen.findByText("Valor faturado")).toBeVisible();
  const appliedLink = screen.getByLabelText("URL atual").textContent!;
  expect(appliedLink).toBe(
    "/dev/contratos?competencia_inicio=2025-01&competencia_fim=2025-02&municipio=Porto+Alegre&classe=Residencial",
  );

  await user.clear(screen.getByLabelText("Município"));
  await user.type(screen.getByLabelText("Município"), "Rascunho");
  expect(screen.getByLabelText("URL atual")).toHaveTextContent(appliedLink);
  expect(fetchSpy).toHaveBeenCalledTimes(1);
  view.unmount();
  renderDiagnostic(appliedLink);

  expect(await screen.findByLabelText("Município")).toHaveValue("Porto Alegre");
  expect(screen.getByLabelText("Classe")).toHaveValue("Residencial");
  expect(screen.getByLabelText("Competência inicial")).toHaveValue("2025-01");
  expect(screen.getByLabelText("Competência final")).toHaveValue("2025-02");
  expect(await screen.findByText("Valor faturado")).toBeVisible();
  expect(fetchSpy).toHaveBeenCalledTimes(2);
});

it.each(["botão Consultar", "campo Município"] as const)(
  "mantém o foco no %s ao aplicar o recorte por Enter",
  async (origin) => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response(JSON.stringify(response), { status: 200 }),
        ),
    );
    const user = userEvent.setup();
    renderDiagnostic();
    await user.type(
      await screen.findByLabelText("Município"),
      " Porto Alegre ",
    );
    if (origin === "botão Consultar") {
      await user.tab();
      await user.tab();
      expect(screen.getByRole("button", { name: "Consultar" })).toHaveFocus();
    } else {
      expect(screen.getByLabelText("Município")).toHaveFocus();
    }

    await user.keyboard("{Enter}");

    expect(await screen.findByText("Valor faturado")).toBeVisible();
    expect(screen.getByLabelText("URL atual")).toHaveTextContent(
      /^\/dev\/contratos\?competencia_inicio=2025-01&competencia_fim=2025-02&municipio=Porto\+Alegre$/,
    );
    expect(screen.getByLabelText("Município")).toHaveValue("Porto Alegre");
    if (origin === "botão Consultar") {
      expect(screen.getByRole("button", { name: "Consultar" })).toHaveFocus();
    } else {
      expect(screen.getByLabelText("Município")).toHaveFocus();
    }
  },
);

it("normaliza o link recebido e consulta somente os filtros pertinentes", async () => {
  const fetchSpy = vi
    .fn()
    .mockResolvedValue(new Response(JSON.stringify(response), { status: 200 }));
  vi.stubGlobal("fetch", fetchSpy);
  renderDiagnostic(
    "/dev/contratos?classe=++&municipio=+Porto+Alegre+&competencia_fim=2025-02&ignorado=valor",
  );

  expect(await screen.findByText("Valor faturado")).toBeVisible();
  expect(screen.getByLabelText("Município")).toHaveValue("Porto Alegre");
  expect(screen.getByLabelText("Classe")).toHaveValue("");
  await waitFor(() =>
    expect(screen.getByLabelText("URL atual")).toHaveTextContent(
      /^\/dev\/contratos\?competencia_inicio=2025-01&competencia_fim=2025-02&municipio=Porto\+Alegre$/,
    ),
  );
  expect(fetchSpy).toHaveBeenCalledTimes(1);
  expect(fetchSpy.mock.calls[0]![0]).toContain(
    "/api/v1/kpis?competencia_inicio=2025-01&competencia_fim=2025-02&municipio=Porto+Alegre",
  );
});

it("bloqueia mês inválido no link e permite corrigir o formulário antes da consulta", async () => {
  const fetchSpy = vi
    .fn()
    .mockResolvedValue(new Response(JSON.stringify(response), { status: 200 }));
  vi.stubGlobal("fetch", fetchSpy);
  const user = userEvent.setup();
  renderDiagnostic(
    "/dev/contratos?competencia_inicio=2025-13&competencia_fim=2025-02&municipio=Porto+Alegre",
  );

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Competência inicial deve usar YYYY-MM com mês válido.",
  );
  expect(fetchSpy).not.toHaveBeenCalled();
  expect(
    screen.queryByRole("region", { name: "Resultado dos indicadores" }),
  ).not.toBeInTheDocument();
  expect(screen.getByLabelText("Competência inicial")).toHaveAttribute(
    "aria-invalid",
    "true",
  );
  expect(
    screen.getByLabelText("Competência inicial"),
  ).toHaveAccessibleDescription(
    "Competência inicial deve usar YYYY-MM com mês válido.",
  );
  expect(screen.getByLabelText("Município")).toHaveValue("Porto Alegre");
  fireEvent.change(screen.getByLabelText("Competência inicial"), {
    target: { value: "2025-01" },
  });
  await user.click(screen.getByRole("button", { name: "Consultar" }));

  expect(await screen.findByText("Valor faturado")).toBeVisible();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  expect(screen.getByLabelText("URL atual")).toHaveTextContent(
    /^\/dev\/contratos\?competencia_inicio=2025-01&competencia_fim=2025-02&municipio=Porto\+Alegre$/,
  );
  expect(fetchSpy).toHaveBeenCalledTimes(1);
});

it.each([
  [
    "competencia_inicio=&competencia_fim=2025-02",
    "Competência inicial deve usar YYYY-MM com mês válido.",
  ],
  [
    "competencia_inicio=0000-01",
    "Competência inicial deve usar YYYY-MM com mês válido.",
  ],
  [
    "competencia_fim=2025-00",
    "Competência final deve usar YYYY-MM com mês válido.",
  ],
  [
    "competencia_inicio=2025-03&competencia_fim=2025-02",
    "Competência final deve ser igual ou posterior à inicial.",
  ],
  [
    "municipio=Porto+Alegre&municipio=Canoas",
    "Município deve aparecer apenas uma vez no link.",
  ],
  [
    `municipio=${"m".repeat(101)}`,
    "Município deve ter no máximo 100 caracteres.",
  ],
  [`classe=${"c".repeat(101)}`, "Classe deve ter no máximo 100 caracteres."],
])("rejeita filtros inválidos da URL sem HTTP: %s", async (search, message) => {
  const fetchSpy = vi
    .fn()
    .mockImplementation(
      async () => new Response(JSON.stringify(response), { status: 200 }),
    );
  vi.stubGlobal("fetch", fetchSpy);
  renderDiagnostic(`/dev/contratos?${search}`);

  expect(await screen.findByRole("alert")).toHaveTextContent(message);
  expect(fetchSpy).not.toHaveBeenCalled();
  expect(screen.getByRole("button", { name: "Consultar" })).toBeEnabled();
});

it("valida o rascunho antes de alterar o recorte aplicado e foca o campo incorreto", async () => {
  const fetchSpy = vi
    .fn()
    .mockResolvedValue(new Response(JSON.stringify(response), { status: 200 }));
  vi.stubGlobal("fetch", fetchSpy);
  const user = userEvent.setup();
  renderDiagnostic();
  fireEvent.change(await screen.findByLabelText("Competência inicial"), {
    target: { value: "2025-03" },
  });
  await user.click(screen.getByRole("button", { name: "Consultar" }));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Competência final deve ser igual ou posterior à inicial.",
  );
  expect(screen.getByLabelText("Competência final")).toHaveFocus();
  expect(fetchSpy).not.toHaveBeenCalled();
  expect(screen.getByLabelText("URL atual")).toHaveTextContent(
    /^\/dev\/contratos$/,
  );
});

it("sincroniza rascunho e resultado ao voltar e avançar e retorna ao início sem consulta", async () => {
  const first = structuredClone(response);
  first.data.metrics[0]!.label = "Indicador de Porto Alegre";
  first.metadata.filters.municipio = "Porto Alegre";
  const second = structuredClone(response);
  second.data.metrics[0]!.label = "Indicador de Canoas";
  second.metadata.filters.municipio = "Canoas";
  const fetchSpy = vi
    .fn()
    .mockResolvedValueOnce(new Response(JSON.stringify(first), { status: 200 }))
    .mockResolvedValueOnce(
      new Response(JSON.stringify(second), { status: 200 }),
    );
  vi.stubGlobal("fetch", fetchSpy);
  const user = userEvent.setup();
  renderDiagnostic();
  await user.type(await screen.findByLabelText("Município"), "Porto Alegre");
  await user.click(screen.getByRole("button", { name: "Consultar" }));
  expect(await screen.findByText("Indicador de Porto Alegre")).toBeVisible();

  await user.clear(screen.getByLabelText("Município"));
  await user.type(screen.getByLabelText("Município"), "Canoas");
  await user.click(screen.getByRole("button", { name: "Consultar" }));
  expect(await screen.findByText("Indicador de Canoas")).toBeVisible();
  await user.type(screen.getByLabelText("Classe"), "Rascunho não aplicado");
  await user.click(screen.getByRole("button", { name: "Voltar" }));

  expect(screen.getByLabelText("Município")).toHaveValue("Porto Alegre");
  expect(screen.getByLabelText("Classe")).toHaveValue("");
  expect(screen.getByText("Indicador de Porto Alegre")).toBeVisible();
  expect(screen.queryByText("Indicador de Canoas")).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Avançar" }));
  expect(screen.getByLabelText("Município")).toHaveValue("Canoas");
  expect(screen.getByText("Indicador de Canoas")).toBeVisible();
  await user.click(screen.getByRole("button", { name: "Voltar" }));
  await user.click(screen.getByRole("button", { name: "Voltar" }));

  expect(screen.getByLabelText("URL atual")).toHaveTextContent(
    /^\/dev\/contratos$/,
  );
  expect(screen.getByLabelText("Município")).toHaveValue("");
  expect(
    screen.queryByRole("region", { name: "Resultado dos indicadores" }),
  ).not.toBeInTheDocument();
  expect(screen.queryByText("Carregando indicadores…")).not.toBeInTheDocument();
  expect(fetchSpy).toHaveBeenCalledTimes(2);
});

it("descarta o rascunho ao navegar entre entradas de histórico com o mesmo recorte", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValue(
        new Response(JSON.stringify(response), { status: 200 }),
      ),
  );
  const user = userEvent.setup();
  renderDiagnostic();
  await user.click(await screen.findByRole("button", { name: "Consultar" }));
  expect(await screen.findByText("Valor faturado")).toBeVisible();
  await user.click(screen.getByRole("button", { name: "Consultar" }));
  await user.type(screen.getByLabelText("Município"), "Rascunho");
  await user.click(screen.getByRole("button", { name: "Voltar" }));

  expect(screen.getByLabelText("Município")).toHaveValue("");
  expect(screen.getByText("Valor faturado")).toBeVisible();
});

it("anuncia atualização em segundo plano ao voltar a um recorte com cache e mantém os dados válidos", async () => {
  const resolvers: Array<(response: Response) => void> = [];
  const fetchSpy = vi.fn().mockImplementation(
    () =>
      new Promise<Response>((resolve) => {
        resolvers.push(resolve);
      }),
  );
  vi.stubGlobal("fetch", fetchSpy);
  const clock = vi.spyOn(Date, "now");
  const user = userEvent.setup();
  renderDiagnostic(
    "/dev/contratos?competencia_inicio=2025-01&competencia_fim=2025-02&municipio=Porto+Alegre",
  );

  expect(await screen.findByText("Carregando indicadores…")).toBeVisible();
  expect(screen.queryByText(/Atualizando indicadores/)).not.toBeInTheDocument();
  await waitFor(() => expect(fetchSpy).toHaveBeenCalledTimes(1));
  const first = structuredClone(response);
  first.metadata.filters.municipio = "Porto Alegre";
  resolvers[0]!(new Response(JSON.stringify(first), { status: 200 }));
  expect(await screen.findByText("Valor faturado")).toBeVisible();
  await user.clear(screen.getByLabelText("Município"));
  await user.type(screen.getByLabelText("Município"), "Canoas");
  await user.click(screen.getByRole("button", { name: "Consultar" }));
  await waitFor(() => expect(fetchSpy).toHaveBeenCalledTimes(2));
  expect(screen.queryByText("Valor faturado")).not.toBeInTheDocument();
  const second = structuredClone(response);
  second.data.metrics[0]!.label = "Indicador de Canoas";
  second.metadata.filters.municipio = "Canoas";
  resolvers[1]!(new Response(JSON.stringify(second), { status: 200 }));
  expect(await screen.findByText("Indicador de Canoas")).toBeVisible();
  clock.mockReturnValue(Date.now() + 31_000);
  await user.click(screen.getByRole("button", { name: "Voltar" }));
  await waitFor(() => expect(fetchSpy).toHaveBeenCalledTimes(3));

  const announcement = await screen.findByText(
    "Atualizando indicadores… Os últimos dados válidos deste recorte continuam visíveis.",
  );
  expect(announcement).toHaveAttribute("role", "status");
  expect(screen.getByText("Valor faturado")).toBeVisible();
  expect(screen.getByText(/R\$\s0,00/)).toBeVisible();
  expect(screen.getByLabelText("Município")).toHaveValue("Porto Alegre");
  expect(screen.queryByText("Carregando indicadores…")).not.toBeInTheDocument();
  expect(screen.queryByText("Indicador de Canoas")).not.toBeInTheDocument();

  const refreshed = structuredClone(first);
  refreshed.data.metrics[0]!.label = "Indicador atualizado de Porto Alegre";
  resolvers[2]!(new Response(JSON.stringify(refreshed), { status: 200 }));
  expect(
    await screen.findByText("Indicador atualizado de Porto Alegre"),
  ).toBeVisible();
  expect(screen.queryByText(/Atualizando indicadores/)).not.toBeInTheDocument();
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

  await user.clear(screen.getByLabelText("Município"));
  await user.type(screen.getByLabelText("Município"), "Novo");
  await user.click(screen.getByRole("button", { name: "Consultar" }));
  await waitFor(() => expect(fetchSpy).toHaveBeenCalledTimes(2));

  const [, previousOptions] = fetchSpy.mock.calls[0] as [string, RequestInit];
  expect(previousOptions.signal?.aborted).toBe(true);

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
  vi.stubEnv("VITE_API_URL", "/");
  vi.stubEnv("DEV", false);
  vi.resetModules();
  const [{ AppRoutes: ProductionAppRoutes }, { default: ProductionProviders }] =
    await Promise.all([import("./router"), import("./providers")]);
  const fetchSpy = vi.fn().mockRejectedValue(new Error("API indisponível"));
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
  expect(
    await screen.findByText("Erro na consulta dos indicadores"),
  ).toBeVisible();
  expect(fetchSpy).toHaveBeenCalled();
  for (const [url] of fetchSpy.mock.calls) {
    expect(url).toMatch(/^\/api\/v1\/panorama\?/);
  }
});
