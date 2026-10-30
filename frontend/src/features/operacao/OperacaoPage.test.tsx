import { beforeEach, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, useLocation } from "react-router-dom";
import OperacaoPage from "./OperacaoPage";
import {
  detailFixture,
  rankingFixture,
  summaryFixture,
} from "./fixtures.test-support";

function Location() {
  return <output aria-label="URL atual">{useLocation().search}</output>;
}

function mount(url = "/operacao") {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[url]}>
        <OperacaoPage />
        <Location />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return client;
}

function respond(value: unknown, status = 200) {
  return new Response(JSON.stringify(value), { status });
}

const secondPoint = {
  ...rankingFixture.data.items[0],
  feeder_id: "AL-02",
  municipalities: ["Santo Amaro"],
  dec_hours_per_uc: 1.5,
  fec_interruptions_per_uc: 0.5,
  interruption_count: 1,
  denominator_uc_count: 2,
  covered_uc_count: 2,
  coverage_ratio: 1,
  served_uc_count: 2,
  duration_hours_sum: 3,
  text_alternative: "AL-02: DEC 1,5 h/UC; FEC 0,5 interrupções/UC.",
  rank: 2,
};

const excludedPoint = {
  ...rankingFixture.data.items[0],
  feeder_id: "AL-03",
  municipalities: ["Recife"],
  dec_hours_per_uc: null,
  fec_interruptions_per_uc: null,
  denominator_uc_count: null,
  covered_uc_count: 0,
  coverage_ratio: null,
  served_uc_count: 2,
  coverage_status: "unavailable" as const,
  status: "unavailable" as const,
  limitations: ["Denominador ausente."],
  duration_hours_sum: 0,
  text_alternative: "AL-03 sem denominador disponível.",
  rank: undefined,
};

function ranking(metric: "dec" | "fec" = "dec") {
  const ordered = [rankingFixture.data.items[0], secondPoint];
  return {
    ...rankingFixture,
    data: {
      ...rankingFixture.data,
      items: ordered.map((item, index) => ({ ...item, rank: index + 1 })),
      excluded: [excludedPoint],
      metric,
    },
  };
}

function detailFor(feederId: string) {
  if (feederId === "AL-01") return detailFixture;
  const point = {
    ...excludedPoint,
    rank: undefined,
    feeder_id: feederId,
    text_alternative: `${feederId} sem base de UCs disponível no recorte.`,
  };
  return {
    ...detailFixture,
    data: {
      ...detailFixture.data,
      summary: point,
      series: [],
      occurrences: [],
    },
    metadata: {
      ...detailFixture.metadata,
      status: "unavailable" as const,
      filters: { ...detailFixture.metadata.filters, alimentador: feederId },
    },
    pagination: { page: 1, page_size: 20, total: 0, total_pages: 0 },
  };
}

function mockApi(options?: {
  summary?: (url: URL) => Response;
  ranking?: (url: URL) => Response;
  detail?: (url: URL) => Response;
}) {
  const fetch = vi.fn(async (input: RequestInfo | URL) => {
    const url = new URL(String(input), window.location.origin);
    if (url.pathname.endsWith("/options"))
      return respond({ error: { code: "unsupported_source" } }, 422);
    if (url.pathname.endsWith("/summary"))
      return options?.summary?.(url) ?? respond(summaryFixture);
    if (url.pathname.endsWith("/ranking"))
      return (
        options?.ranking?.(url) ??
        respond(
          ranking(url.searchParams.get("metric") === "fec" ? "fec" : "dec"),
        )
      );
    if (url.pathname.includes("/feeders/"))
      return (
        options?.detail?.(url) ??
        respond(
          detailFor(decodeURIComponent(url.pathname.split("/").at(-1) ?? "")),
        )
      );
    throw new Error(`Rota inesperada: ${url.pathname}`);
  });
  vi.stubGlobal("fetch", fetch);
  return fetch;
}

beforeEach(() => {
  vi.restoreAllMocks();
});

it("mostra consolidado parcial e distingue base incluída da população do recorte", async () => {
  mockApi();
  const user = userEvent.setup();
  mount();

  const summaryRegion = screen.getByRole("region", {
    name: "Resumo de continuidade",
  });
  expect(await within(summaryRegion).findByText("1,5 h/UC")).toBeVisible();
  expect(await within(summaryRegion).findByText("0,75 int./UC")).toBeVisible();
  expect(screen.getByText("4 UCs")).toBeVisible();
  expect(screen.getByText("Parcial")).toBeVisible();
  await user.click(screen.getByRole("button", { name: "Ver fundamentos" }));
  expect(
    screen.getByRole("region", { name: "Fundamentos do consolidado" }),
  ).toHaveTextContent("População do recorte: 10 UCs");
  expect(
    screen.getByRole("region", { name: "Fundamentos do consolidado" }),
  ).toHaveTextContent("Base incluída: 4 UCs");
  const foundations = screen.getByRole("region", {
    name: "Fundamentos do consolidado",
  });
  expect(foundations).toHaveTextContent("AL-03");
  expect(foundations).toHaveTextContent("Numerador DEC: 6 h");
  expect(foundations).toHaveTextContent(
    "Numerador FEC: 3 registros UC–interrupção",
  );
  expect(foundations).toHaveTextContent(
    "Período observado: Jan/2025 – Fev/2025",
  );
  expect(foundations).toHaveTextContent(
    "Fonte: synthetic · versão dev03-v1 · demonstrativa",
  );
  expect(foundations).toHaveTextContent("Atualizado em:");
  expect(
    screen.getAllByRole("link", { name: "Investigar AL-03" }),
  ).toHaveLength(2);
  expect(
    screen.getByText(/sem comparação com limites regulatórios/i),
  ).toBeVisible();
});

it("ordena pelo FEC sob demanda e deixa alimentador excluído investigável", async () => {
  const fetch = mockApi();
  const user = userEvent.setup();
  mount();

  const table = await screen.findByRole("table", {
    name: "Ranking de alimentadores",
  });
  expect(within(table).getAllByRole("row")[1]).toHaveTextContent("AL-01");
  await user.click(screen.getByRole("button", { name: "Ordenar por FEC" }));
  await waitFor(() =>
    expect(screen.getByLabelText("URL atual")).toHaveTextContent("metric=fec"),
  );
  expect(within(table).getAllByRole("row")[1]).toHaveTextContent("AL-01");
  expect(
    fetch.mock.calls.some(([input]) => String(input).includes("metric=fec")),
  ).toBe(true);
  const excludedCard = screen.getByRole("article", {
    name: "Alimentador AL-03",
  });
  expect(
    within(excludedCard).getByRole("link", { name: "Investigar AL-03" }),
  ).toBeVisible();
  expect(within(excludedCard).getByText("Sem denominador")).toBeVisible();
});

it("distingue cobertura desconhecida de denominador ausente no ranking", async () => {
  const unknownWindow = {
    ...rankingFixture.data.items[0],
    feeder_id: "AL-04",
    dec_hours_per_uc: null,
    fec_interruptions_per_uc: null,
    denominator_uc_count: 2,
    coverage_ratio: null,
    coverage_status: "unavailable" as const,
    status: "unavailable" as const,
    limitations: ["Janela de cobertura desconhecida."],
    text_alternative: "Base conhecida, janela de cobertura desconhecida.",
  };
  mockApi({
    ranking: () =>
      respond({
        ...rankingFixture,
        data: { ...rankingFixture.data, items: [], excluded: [unknownWindow] },
      }),
  });
  mount();
  const card = await screen.findByRole("article", {
    name: "Alimentador AL-04",
  });
  expect(within(card).getByText("Cobertura indisponível")).toBeVisible();
  expect(
    within(card).getByText("Janela de cobertura desconhecida."),
  ).toBeVisible();
  expect(within(card).queryByText("Sem denominador")).not.toBeInTheDocument();
});

it("mantém o rascunho de filtros local até aplicar e fecha com Escape devolvendo foco", async () => {
  mockApi();
  const user = userEvent.setup();
  mount("/operacao?competencia_inicio=2025-01&competencia_fim=2025-02");
  const trigger = await screen.findByRole("button", {
    name: "Ajustar filtros",
  });
  await user.click(trigger);
  const dialog = screen.getByRole("dialog", {
    name: "Ajustar filtros de operação",
  });
  await user.selectOptions(
    within(dialog).getByLabelText("Mês de início"),
    "12",
  );
  await user.clear(within(dialog).getByLabelText("Ano de início"));
  await user.type(within(dialog).getByLabelText("Ano de início"), "2024");
  await user.keyboard("{Escape}");
  await waitFor(() => expect(dialog).not.toBeVisible());
  expect(trigger).toHaveFocus();
  expect(screen.getByLabelText("URL atual")).toHaveTextContent(
    "competencia_inicio=2025-01",
  );

  await user.click(trigger);
  await user.selectOptions(
    within(dialog).getByLabelText("Mês de início"),
    "12",
  );
  await user.clear(within(dialog).getByLabelText("Ano de início"));
  await user.type(within(dialog).getByLabelText("Ano de início"), "2024");
  await user.click(
    within(dialog).getByRole("button", { name: "Aplicar filtros" }),
  );
  await waitFor(() =>
    expect(screen.getByLabelText("URL atual")).toHaveTextContent(
      "competencia_inicio=2024-12",
    ),
  );
});

it("mantém o diálogo aberto e foca campo inválido para janela acima de 120 meses", async () => {
  mockApi();
  const user = userEvent.setup();
  mount();
  await user.click(
    await screen.findByRole("button", { name: "Ajustar filtros" }),
  );
  const dialog = screen.getByRole("dialog", {
    name: "Ajustar filtros de operação",
  });
  const start = within(dialog).getByLabelText("Ano de início");
  const end = within(dialog).getByLabelText("Ano do fim");
  await user.clear(start);
  await user.type(start, "2010");
  await user.selectOptions(within(dialog).getByLabelText("Mês do fim"), "01");
  await user.clear(end);
  await user.type(end, "2020");
  await user.click(
    within(dialog).getByRole("button", { name: "Aplicar filtros" }),
  );
  expect(dialog).toBeVisible();
  expect(within(dialog).getByRole("alert")).toHaveTextContent("120 meses");
  expect(end).toHaveAttribute("aria-invalid", "true");
  expect(end).toHaveFocus();
  expect(screen.getByLabelText("URL atual")).toHaveTextContent("");
});

it("valida limite de caracteres Unicode do alimentador pelo parser aprovado", async () => {
  mockApi();
  const user = userEvent.setup();
  mount();
  await user.click(
    await screen.findByRole("button", { name: "Ajustar filtros" }),
  );
  const dialog = screen.getByRole("dialog", {
    name: "Ajustar filtros de operação",
  });
  const feeder = within(dialog).getByLabelText("Alimentador");
  await user.type(feeder, "😀".repeat(101));
  await user.click(
    within(dialog).getByRole("button", { name: "Aplicar filtros" }),
  );
  expect(dialog).toBeVisible();
  expect(within(dialog).getByRole("alert")).toHaveTextContent(
    "1 a 100 caracteres",
  );
  expect(feeder).toHaveAttribute("aria-invalid", "true");
  expect(feeder).toHaveFocus();
}, 10000);

it("abre detalhe mensal, mostra alternativa textual e pagina ocorrências sem perder o resumo", async () => {
  const fetch = mockApi({
    detail: () =>
      respond({
        ...detailFixture,
        pagination: { page: 1, page_size: 20, total: 21, total_pages: 2 },
      }),
  });
  const user = userEvent.setup();
  mount(
    "/operacao?competencia_inicio=2025-01&competencia_fim=2025-02&metric=fec",
  );
  await user.click(
    (await screen.findAllByRole("link", { name: "Investigar AL-01" }))[0],
  );

  expect(
    await screen.findByRole("heading", {
      name: "AL-01 / visão do alimentador",
    }),
  ).toBeVisible();
  expect(
    screen.getByRole("region", { name: "Série mensal de DEC" }),
  ).toHaveTextContent("Jan/2025");
  expect(
    screen.getByRole("table", { name: "Dados mensais de continuidade" }),
  ).toHaveTextContent("Fev/2025");
  expect(
    screen.getByRole("table", { name: "Ocorrências de interrupção" }),
  ).toHaveTextContent("EV-01");
  await user.click(
    screen.getByRole("button", { name: "Próxima página de ocorrências" }),
  );
  await waitFor(() =>
    expect(screen.getByLabelText("URL atual")).toHaveTextContent("page=2"),
  );
  expect(screen.getByLabelText("URL atual")).toHaveTextContent("metric=fec");
  expect(screen.getByLabelText("URL atual")).toHaveTextContent(
    "feeder_id=AL-01",
  );
  expect(
    screen.queryByRole("region", { name: "Resumo de continuidade" }),
  ).not.toBeInTheDocument();
  expect(
    screen.queryByRole("region", { name: "Fundamentos do consolidado" }),
  ).not.toBeInTheDocument();
  const summaryCall = fetch.mock.calls.find(([input]) =>
    String(input).includes("/summary"),
  );
  expect(String(summaryCall?.[0])).not.toContain("feeder_id");
  expect(String(summaryCall?.[0])).not.toContain("page=");
});

it("permite investigar AL-03 sem denominador e apresenta indisponibilidade, não zero", async () => {
  mockApi();
  const user = userEvent.setup();
  mount();
  await user.click(
    (await screen.findAllByRole("link", { name: "Investigar AL-03" }))[0],
  );

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "sem base de UCs disponível",
  );
  const detail = screen.getByRole("region", {
    name: "Detalhe do alimentador AL-03",
  });
  expect(
    within(detail).getByText("DEC e FEC indisponíveis neste alimentador"),
  ).toBeVisible();
  expect(
    within(detail).getAllByText("Indisponível").length,
  ).toBeGreaterThanOrEqual(2);
  expect(screen.queryByText("0 h/UC")).not.toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: "← Voltar ao ranking" }),
  ).toBeVisible();
});

it("mantém ocorrências observadas quando o denominador do alimentador é inválido", async () => {
  const unavailableWithEvents = {
    ...detailFixture,
    data: {
      ...detailFixture.data,
      summary: {
        ...detailFixture.data.summary,
        dec_hours_per_uc: null,
        fec_interruptions_per_uc: null,
        denominator_uc_count: null,
        status: "unavailable" as const,
        coverage_status: "unavailable" as const,
        text_alternative:
          "AL-01 tem registros observados, mas o denominador não é válido.",
        limitations: ["Denominador ausente."],
      },
    },
    metadata: { ...detailFixture.metadata, status: "unavailable" as const },
  };
  mockApi({ detail: () => respond(unavailableWithEvents) });
  const user = userEvent.setup();
  mount("/operacao?feeder_id=AL-01");
  await screen.findByRole("heading", { name: "AL-01 / visão do alimentador" });
  expect(await screen.findByRole("alert")).toHaveTextContent(
    /Registros e ocorrências observados continuam disponíveis/,
  );
  expect(
    screen.getByRole("table", { name: "Ocorrências de interrupção" }),
  ).toHaveTextContent("EV-01");
  expect(
    screen.getByRole("table", { name: "Dados mensais de continuidade" }),
  ).toHaveTextContent("0,5");
  expect(screen.getByText("Denominador informado")).toBeVisible();
  expect(
    screen.queryByRole("region", { name: "Resumo de continuidade" }),
  ).not.toBeInTheDocument();
  await user.click(
    screen.getByRole("button", { name: "Ver fórmula e base do alimentador" }),
  );
  const foundations = screen.getByRole("region", {
    name: "Fundamentos do alimentador",
  });
  expect(foundations).toHaveTextContent("Denominador informado: indisponível");
  expect(foundations).toHaveTextContent("Numerador DEC: 3 h");
  expect(foundations).toHaveTextContent(
    "Numerador FEC: 2 registros UC–interrupção",
  );
  expect(foundations).toHaveTextContent(
    "Período solicitado: Jan/2025 – Fev/2025",
  );
  expect(foundations).toHaveTextContent(
    "Período observado: Jan/2025 – Fev/2025",
  );
  expect(foundations).toHaveTextContent(
    "Fonte: synthetic · versão dev03-v1 · demonstrativa",
  );
  expect(foundations).not.toHaveTextContent("População do recorte: 10 UCs");
});

it("identifica denominador zero como inválido nos cards e fundamentos do alimentador", async () => {
  const zeroDenominator = {
    ...detailFixture,
    data: {
      ...detailFixture.data,
      summary: {
        ...detailFixture.data.summary,
        denominator_uc_count: 0,
        status: "unavailable" as const,
        coverage_status: "unavailable" as const,
        dec_hours_per_uc: null,
        fec_interruptions_per_uc: null,
        limitations: ["Denominador zero; base inválida."],
      },
    },
    metadata: { ...detailFixture.metadata, status: "unavailable" as const },
  };
  mockApi({ detail: () => respond(zeroDenominator) });
  const user = userEvent.setup();
  mount("/operacao?feeder_id=AL-01");

  const detail = await screen.findByRole("region", {
    name: "Detalhe do alimentador AL-01",
  });
  expect(
    await within(detail).findByText("Denominador informado"),
  ).toBeVisible();
  expect(await within(detail).findByText("0 UCs · inválido")).toBeVisible();
  await user.click(
    screen.getByRole("button", { name: "Ver fórmula e base do alimentador" }),
  );
  const foundations = screen.getByRole("region", {
    name: "Fundamentos do alimentador",
  });
  expect(foundations).toHaveTextContent(
    "Denominador informado: 0 UCs · inválido",
  );
});

it("bloqueia URLs inválidas até restaurar filtros e não mostra erros internos do contrato", async () => {
  const fetch = mockApi();
  const user = userEvent.setup();
  mount("/operacao?metric=invalid&unexpected=x");
  expect(screen.getByRole("alert")).toHaveTextContent(
    "Parâmetros de operação inválidos",
  );
  expect(fetch).not.toHaveBeenCalled();
  await user.click(screen.getByRole("button", { name: "Restaurar filtros" }));
  expect(
    await within(
      screen.getByRole("region", { name: "Resumo de continuidade" }),
    ).findByText("1,5 h/UC"),
  ).toBeVisible();
  expect(screen.getByLabelText("URL atual")).toHaveTextContent("");
});

it("mostra erro da consulta isoladamente, permite repetir e preserva respostas válidas", async () => {
  let summaryAttempts = 0;
  const fetch = mockApi({
    summary: () => {
      summaryAttempts += 1;
      return summaryAttempts === 1
        ? respond({ detail: "erro interno secreto" }, 503)
        : respond(summaryFixture);
    },
  });
  const user = userEvent.setup();
  mount();

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Não foi possível carregar o consolidado",
  );
  expect(
    screen.getByRole("table", { name: "Ranking de alimentadores" }),
  ).toBeVisible();
  expect(screen.queryByText("erro interno secreto")).not.toBeInTheDocument();
  await user.click(
    screen.getByRole("button", { name: "Tentar novamente o consolidado" }),
  );
  expect(
    await within(
      screen.getByRole("region", { name: "Resumo de continuidade" }),
    ).findByText("1,5 h/UC"),
  ).toBeVisible();
  expect(summaryAttempts).toBe(2);
  expect(
    fetch.mock.calls.some(([input]) => String(input).includes("/ranking")),
  ).toBe(true);
});

it("distingue consolidado vazio e indicadores zero com base conhecida", async () => {
  const zero = {
    ...summaryFixture,
    data: {
      ...summaryFixture.data,
      summary: {
        ...summaryFixture.data.summary,
        dec_hours_per_uc: 0,
        fec_interruptions_per_uc: 0,
        duration_hours_sum: 0,
        interruption_count: 0,
        status: "available" as const,
        excluded_feeder_ids: [],
        included_feeder_ids: ["AL-01"],
        included_uc_count: 2,
        served_uc_count: 2,
      },
    },
    metadata: { ...summaryFixture.metadata, status: "available" as const },
  };
  const fetch = mockApi({ summary: () => respond(zero) });
  mount();
  expect(await screen.findByText("0 h/UC")).toBeVisible();
  expect(
    within(
      screen.getByRole("region", { name: "Resumo de continuidade" }),
    ).getByText("0 int./UC"),
  ).toBeVisible();
  expect(fetch).toHaveBeenCalled();
});

it("mostra vazio legítimo sem confundir ausência de fonte com zero", async () => {
  const empty = {
    ...summaryFixture,
    data: {
      ...summaryFixture.data,
      summary: {
        ...summaryFixture.data.summary,
        dec_hours_per_uc: null,
        fec_interruptions_per_uc: null,
        duration_hours_sum: null,
        interruption_count: null,
        denominator_uc_count: null,
        served_uc_count: 0,
        included_uc_count: 0,
        included_feeder_ids: [],
        excluded_feeder_ids: [],
        status: "empty" as const,
        limitations: [],
      },
    },
    metadata: { ...summaryFixture.metadata, status: "empty" as const },
  };
  mockApi({ summary: () => respond(empty) });
  mount();
  expect(
    await screen.findByText(
      "Nenhum alimentador foi encontrado na fonte para este recorte.",
    ),
  ).toBeVisible();
  const summaryRegion = screen.getByRole("region", {
    name: "Resumo de continuidade",
  });
  expect(within(summaryRegion).getAllByText("Indisponível")).toHaveLength(3);
  expect(screen.queryByText("0 h/UC")).not.toBeInTheDocument();
});

it("converte JSON inválido em erro amigável e mantém o ranking que carregou", async () => {
  const fetch = vi.fn(async (input: RequestInfo | URL) => {
    const url = new URL(String(input), window.location.origin);
    if (url.pathname.endsWith("/options"))
      return respond({ error: { code: "unsupported_source" } }, 422);
    if (url.pathname.endsWith("/summary"))
      return new Response("<html>segredo interno</html>");
    if (url.pathname.endsWith("/ranking")) return respond(rankingFixture);
    return respond(detailFixture);
  });
  vi.stubGlobal("fetch", fetch);
  mount();
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Não foi possível carregar o consolidado",
  );
  expect(
    screen.getByRole("table", { name: "Ranking de alimentadores" }),
  ).toBeVisible();
  expect(
    screen.queryByText(/segredo interno|resposta\.data/),
  ).not.toBeInTheDocument();
});

it("navega do ranking Gold ao detalhe agregado e retorna preservando filtros", async () => {
  const fingerprint = "c".repeat(64);
  const metadata = (
    period: { start: string; end: string; granularity: "month" } | null,
    feeder: string | null = null,
  ) => ({
    contract_version: "2.0.0",
    status: "partial",
    period,
    filters: {
      municipio: "Recife",
      bairro: null,
      classe: null,
      alimentador: feeder,
    },
    source: {
      kind: "gold",
      version: "ui-navigation-batch",
      is_demo: false,
      updated_at: "2026-10-29T00:00:00Z",
    },
    limitations: [],
    temporal_scope: period ? "monthly" : "snapshot",
    schema_version: "gold-csv-v1",
    fingerprint,
  });
  const windowPeriod = {
    start: "2025-01",
    end: "2025-02",
    granularity: "month" as const,
  };
  const definition = {
    reference: "docs/dicionario_gold.md",
    dec_formula: "Duração/base",
    fec_formula: "Frequência/base",
    dec_unit: "h/UC",
    fec_unit: "int./UC",
    event_grain: "UC-interrupção",
    population: "cadastro atual",
    completeness: "completude não comprovada",
  };
  const point = {
    feeder_id: "F-1",
    municipality: "Recife",
    period: windowPeriod,
    observed_period: windowPeriod,
    observed_competencies: ["2025-01", "2025-02"],
    missing_competencies: [],
    duration_hours_sum: 4,
    interruption_count: 2,
    denominator_uc_count: 2,
    dec_hours_per_uc: 2,
    fec_interruptions_per_uc: 1,
    status: "partial",
    dec_status: "partial",
    fec_status: "partial",
    limitations: [],
  };
  const fetch = vi.fn(async (input: RequestInfo | URL) => {
    const url = new URL(String(input), window.location.origin);
    if (url.pathname.endsWith("/options"))
      return respond({
        data: {
          competencias: ["2025-01", "2025-02"],
          municipios: ["Recife"],
          alimentadores: [{ id: "F-1", municipio: "Recife" }],
        },
        metadata: metadata(null),
      });
    if (url.pathname.endsWith("/summary"))
      return respond({
        data: {
          summary: {
            period: windowPeriod,
            observed_period: windowPeriod,
            duration_hours_sum: 4,
            interruption_count: 2,
            denominator_uc_count: 2,
            dec_hours_per_uc: 2,
            fec_interruptions_per_uc: 1,
            dec_denominator_uc_count: 2,
            fec_denominator_uc_count: 2,
            dec_included_feeder_ids: ["F-1"],
            fec_included_feeder_ids: ["F-1"],
            dec_excluded_feeder_ids: [],
            fec_excluded_feeder_ids: [],
            included_feeder_ids: ["F-1"],
            excluded_feeder_ids: [],
            dec_status: "partial",
            fec_status: "partial",
            status: "partial",
            limitations: [],
          },
        },
        definition,
        metadata: metadata(windowPeriod),
      });
    if (url.pathname.endsWith("/ranking"))
      return respond({
        data: {
          items: [{ ...point, rank: 1 }],
          excluded: [],
          metric: url.searchParams.get("metric") ?? "dec",
          order: "Decrescente pelo indicador",
          definition,
        },
        metadata: metadata(windowPeriod),
      });
    if (url.pathname.includes("/feeders/")) {
      expect(url.searchParams.has("page")).toBe(false);
      expect(url.searchParams.has("page_size")).toBe(false);
      return respond({
        data: {
          summary: point,
          series: [
            {
              ...point,
              period: {
                start: "2025-01",
                end: "2025-01",
                granularity: "month",
              },
            },
          ],
          occurrences: null,
          occurrences_status: "unavailable",
          definition,
        },
        metadata: metadata(windowPeriod, "F-1"),
      });
    }
    throw new Error(`Rota inesperada: ${url.pathname}`);
  });
  vi.stubGlobal("fetch", fetch);
  const user = userEvent.setup();
  mount(
    "/operacao?competencia_inicio=2025-01&competencia_fim=2025-02&municipio=Recife",
  );
  const investigate = await screen.findByRole("link", { name: "Investigar" });
  await user.click(investigate);
  expect(
    await screen.findByRole("heading", { level: 1, name: /F-1/ }),
  ).toBeVisible();
  expect(
    screen.getByText(/Ocorrências individuais indisponíveis/),
  ).toBeVisible();
  expect(screen.queryByText(/Página 1 de/)).not.toBeInTheDocument();
  expect(screen.getByLabelText("URL atual")).toHaveTextContent(
    "municipio=Recife",
  );
  await user.click(screen.getByRole("button", { name: /Voltar ao ranking/ }));
  expect(await screen.findByRole("link", { name: "Investigar" })).toBeVisible();
  expect(screen.getByLabelText("URL atual")).toHaveTextContent(
    "competencia_inicio=2025-01",
  );
  expect(screen.getByLabelText("URL atual")).toHaveTextContent(
    "municipio=Recife",
  );
});
