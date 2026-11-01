import { createRef } from "react";
import { render, screen, within } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import type { UCOverview } from "./contract";
import { decodeUCSearch } from "./contract";
import UC360Detail from "./UC360Detail";
import UC360SearchPanel from "./UC360SearchPanel";
import { UC360Comparison, UC360SupportMetrics } from "./UC360Metrics";

const period = {
  start: "2022-07",
  end: "2026-06",
  granularity: "month" as const,
};
const metadata = {
  contract_version: "1.1.0" as const,
  status: "partial" as const,
  period,
  filters: {},
  source: {
    kind: "gold_csv",
    version: "GOLD-ARTIFICIAL:hash",
    is_demo: false,
    updated_at: "2026-10-29T13:00:00Z",
  },
  limitations: ["Pagamentos e medidores não exportados."],
};
const measure = {
  value: null,
  status: "unavailable" as const,
  limitations: [],
};
const change = {
  delta: null,
  percent_change: null,
  status: "unavailable" as const,
  limitations: [],
};
const point = {
  measured_energy_kwh: measure,
  billed_energy_kwh: measure,
  billed_amount: measure,
  paid_amount: measure,
};

it("distingue cadastro de GD ausente de geração comprovadamente inexistente", () => {
  const data = {
    gold_generation: null,
    gold_generation_record: false,
    distributed_generation: {
      items: [],
      status: "unavailable",
      limitations: [],
    },
    open_invoices: { count: null, status: "unavailable", limitations: [] },
    period,
  } as unknown as UCOverview["data"];
  render(<UC360SupportMetrics data={data} />);
  expect(screen.getByText("Sem registro de GD")).toBeVisible();
  expect(screen.getByText(/cobertura não certificada/)).toBeVisible();
});

it("mantém valor pago quando há um zero observado", () => {
  const comparison = {
    initial: {
      ...point,
      competencia: period.start,
      paid_amount: { ...measure, value: 0, status: "partial" },
    },
    final: { ...point, competencia: period.end },
    measured_energy_kwh: change,
    billed_energy_kwh: change,
    billed_amount: change,
    paid_amount: change,
  } as UCOverview["data"]["comparison"];
  render(<UC360Comparison comparison={comparison} />);
  expect(
    screen.getByRole("heading", { name: "Valor pago (BRL)" }),
  ).toBeVisible();
});

it("preserva e valida a proveniência recebida na busca de UC", () => {
  const response = {
    data: { items: [] },
    pagination: { page: 1, page_size: 20, total: 0, total_pages: 0 },
    metadata: { ...metadata, contract_version: "1.0.0" },
  };
  const results = decodeUCSearch(response);
  render(
    <UC360SearchPanel
      query="FAKE"
      page={1}
      results={results}
      isFetching={false}
      error={null}
      onSearch={vi.fn()}
      onPageChange={vi.fn()}
      onSelect={vi.fn()}
      onRetry={vi.fn()}
    />,
  );
  const panel = screen.getByRole("region", {
    name: "Período, unidades e fonte dos dados",
  });
  expect(within(panel).getByText("07/2022 a 06/2026")).toBeVisible();
  expect(within(panel).getByText("UCs")).toBeVisible();
  expect(within(panel).getByText("GOLD-ARTIFICIAL:hash")).toBeVisible();
  expect(within(panel).getByText(metadata.limitations[0])).toBeVisible();
  expect(() =>
    decodeUCSearch({
      ...response,
      metadata: {
        ...metadata,
        source: { ...metadata.source, updated_at: "invalid" },
      },
    }),
  ).toThrow();
});

it("expõe período, unidade, lote e ausências no detalhe UC sem fabricar dados", () => {
  const overview: UCOverview = {
    metadata,
    data: {
      profile: {
        uc_id: "FAKE-A",
        customer_reference: null,
        customer_name: null,
        municipio: "Cidade fictícia",
        bairro: "Centro",
        classe: "Residencial",
        alimentador: "FAKE-AL",
        status: "ATIVA",
      },
      period,
      comparison: {
        initial: { ...point, competencia: period.start },
        final: { ...point, competencia: period.end },
        measured_energy_kwh: change,
        billed_energy_kwh: change,
        billed_amount: change,
        paid_amount: change,
      },
      open_invoices: { count: null, status: "unavailable", limitations: [] },
      current_meter: {
        item: {
          meter_id: "M-FAKE",
          installed_at: "2025-01-01",
          removed_at: null,
        },
        status: "partial",
        limitations: ["Indicação baseada nas datas disponíveis."],
      },
      distributed_generation: {
        items: [],
        status: "unavailable",
        limitations: [],
      },
      gold_generation: {
        capacity_kwp: 3.5,
        connection_date: null,
        modality: null,
      },
      section_status: {
        consumption: "partial",
        invoices: "unavailable",
        meters: "unavailable",
        distributed_generation: "unavailable",
        interruptions: "unavailable",
        calls: "unavailable",
      },
    },
  };
  render(
    <UC360Detail
      disclosureRef={createRef<HTMLDetailsElement>()}
      unit={{
        id: "FAKE-A",
        overview: {
          data: overview,
          pending: false,
          fetching: false,
          error: null,
        },
        history: { data: undefined, pending: false, error: null },
        series: { data: undefined, pending: false, error: null },
        filters: {
          start: period.start,
          end: period.end,
          section: "consumption",
          historyPage: 1,
          invalid: false,
          historyOpen: false,
        },
      }}
      actions={{
        onOverviewRetry: vi.fn(),
        onHistoryRetry: vi.fn(),
        onSeriesRetry: vi.fn(),
        onNewSearch: vi.fn(),
        onHistoryOpen: vi.fn(),
        onSelectHistory: vi.fn(),
        onHistorySection: vi.fn(),
        onHistoryPage: vi.fn(),
        onPeriodApply: vi.fn(),
      }}
    />,
  );
  const panel = screen.getByRole("region", {
    name: "Período, unidades e fonte dos dados",
  });
  expect(within(panel).getByText("07/2022 a 06/2026")).toBeVisible();
  expect(within(panel).getByText("R$ · kWh")).toBeVisible();
  expect(screen.getAllByText(/3,5 kWp/).length).toBeGreaterThan(0);
  expect(screen.getByText(/Possível medidor: M-FAKE/)).toBeVisible();
  expect(within(panel).getByText("GOLD-ARTIFICIAL:hash")).toBeVisible();
  expect(within(panel).getByText(metadata.limitations[0])).toBeVisible();
  expect(screen.getByText(/Gold CSV · importação local/)).toBeVisible();
  expect(screen.queryByText(/Gold CSV provisória/)).not.toBeInTheDocument();
});
