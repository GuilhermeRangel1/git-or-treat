import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import UC360Page from "./UC360Page";

function renderPage(initial = "/uc-360") {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initial]}>
        <Routes>
          <Route path="/uc-360" element={<UC360Page />} />
          <Route path="/uc-360/:ucId" element={<UC360Page />} />
        </Routes>
        <LocationProbe />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function LocationProbe() {
  const location = useLocation();
  return (
    <output data-testid="location">
      {location.pathname + location.search}
    </output>
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("UC 360 search flow", () => {
  it("searches only after submit, then uses the canonical result ID", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/api/v1/ucs?"))
        return new Response(
          JSON.stringify({
            data: {
              items: [
                {
                  uc_id: "UC-1001",
                  municipio: "Recife",
                  bairro: "Centro",
                  classe: "Residencial",
                  alimentador: "AL-01",
                  status: "active",
                },
              ],
            },
            pagination: { page: 1, page_size: 20, total: 1, total_pages: 1 },
            metadata: { status: "available" },
          }),
          { status: 200 },
        );
      return new Response(JSON.stringify({ detail: "not found" }), {
        status: 404,
      });
    });
    vi.stubGlobal("fetch", fetchMock);
    renderPage();
    fireEvent.change(screen.getByLabelText("Número da UC"), {
      target: { value: "1001" },
    });
    expect(fetchMock).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Buscar UC" }));
    expect(await screen.findByRole("button", { name: /UC-1001/ })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /UC-1001/ }));
    expect(await screen.findByText("UC UC-1001")).toBeTruthy();
    expect(screen.queryByLabelText("Número da UC")).toBeNull();
    expect(screen.getByTestId("location").textContent).toBe("/uc-360/UC-1001");
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/UC-1001/overview"),
        expect.anything(),
      ),
    );
    expect(
      await screen.findByText("A unidade informada não foi encontrada."),
    ).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Nova busca" }));
    expect(screen.getByLabelText("Número da UC")).toBeTruthy();
    expect(screen.getByTestId("location").textContent).toBe("/uc-360");
  });

  it("blocks API calls for a duplicated URL query", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    renderPage("/uc-360?q=1001&q=1002");
    expect(screen.getByRole("alert").textContent).toContain("duplicado");
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("moves a legacy UC query to the detail route and preserves invalid parameters", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    renderPage("/uc-360?uc=UC-1001&q=one&q=two");
    expect(await screen.findByText("UC UC-1001")).toBeTruthy();
    expect(screen.getByTestId("location").textContent).toBe(
      "/uc-360/UC-1001?q=one&q=two",
    );
    expect(screen.getByRole("alert").textContent).toContain("duplicado");
    expect(screen.queryByLabelText("Número da UC")).toBeNull();
    expect(screen.queryByText(/Nenhuma UC selecionada/)).toBeNull();
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("announces an empty search beside the control without sending a request", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: "Buscar UC" }));
    expect(screen.getByRole("alert").textContent).toContain(
      "1 a 100 caracteres",
    );
    expect(
      screen.getByLabelText("Número da UC").getAttribute("aria-invalid"),
    ).toBe("true");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("shows observed comparison facts separately from causal hypotheses and opens source history", async () => {
    const period = { start: "2025-01", end: "2025-02", granularity: "month" };
    const available = (value: number | null, status = "available") => ({
      value,
      status,
      limitations: [],
    });
    const change = (
      delta: number | null,
      percent_change: number | null,
      status = "available",
    ) => ({ delta, percent_change, status, limitations: [] });
    const meta = {
      contract_version: "1.1.0",
      status: "available",
      period,
      filters: {},
      source: {
        kind: "synthetic",
        version: "dev04-v1",
        is_demo: true,
        updated_at: "2026-10-22T00:00:00Z",
      },
      limitations: ["Dados sintéticos."],
    };
    const overview = {
      data: {
        profile: {
          uc_id: "UC-1001",
          customer_reference: "CLI-DEMO-01",
          customer_name: "Pessoa Demonstração",
          municipio: "Recife",
          bairro: "Centro",
          classe: "Residencial",
          alimentador: "AL-01",
          status: "active",
        },
        period,
        comparison: {
          initial: {
            competencia: "2025-01",
            measured_energy_kwh: available(100),
            billed_energy_kwh: available(90),
            billed_amount: available(100),
            paid_amount: available(null, "unavailable"),
          },
          final: {
            competencia: "2025-02",
            measured_energy_kwh: available(0),
            billed_energy_kwh: available(95),
            billed_amount: available(105),
            paid_amount: available(null, "unavailable"),
          },
          measured_energy_kwh: change(-100, -100),
          billed_energy_kwh: change(5, 5.56),
          billed_amount: change(5, 5),
          paid_amount: change(null, null, "unavailable"),
        },
        open_invoices: { count: 1, status: "available", limitations: [] },
        current_meter: {
          item: {
            meter_id: "MED-01",
            installed_at: "2022-03-01",
            removed_at: null,
          },
          status: "available",
          limitations: [],
        },
        distributed_generation: { items: [], status: "empty", limitations: [] },
        section_status: {
          consumption: "available",
          invoices: "available",
          meters: "available",
          distributed_generation: "empty",
          interruptions: "available",
          calls: "available",
        },
      },
      metadata: meta,
    };
    const calls = {
      data: {
        items: [
          {
            call_id: "CH-01",
            opened_at: "2025-02-10T10:00:00",
            category: "fatura",
          },
        ],
      },
      pagination: { page: 1, page_size: 20, total: 1, total_pages: 1 },
      metadata: meta,
    };
    const invoices = {
      data: {
        items: [
          {
            invoice_id: "FAT-02",
            competencia: "2025-02",
            billed_amount: 82,
            paid_amount: 70,
            billed_energy_kwh: 75,
            due_date: "2025-03-20",
            payment_date: "2025-03-05",
            payment_status: "partial",
            currency_unit: "BRL",
          },
        ],
      },
      pagination: { page: 1, page_size: 20, total: 1, total_pages: 1 },
      metadata: meta,
    };
    const fetchMock = vi.fn(async (input: RequestInfo | URL) =>
      String(input).includes("/overview")
        ? new Response(JSON.stringify(overview), { status: 200 })
        : String(input).includes("/history/calls")
          ? new Response(JSON.stringify(calls), { status: 200 })
          : new Response(JSON.stringify(invoices), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const proto = HTMLDialogElement.prototype;
    Object.defineProperty(proto, "showModal", {
      configurable: true,
      value: function (this: HTMLDialogElement) {
        this.setAttribute("open", "");
      },
    });
    Object.defineProperty(proto, "close", {
      configurable: true,
      value: function (this: HTMLDialogElement) {
        this.removeAttribute("open");
        this.dispatchEvent(new Event("close"));
      },
    });
    renderPage("/uc-360?uc=UC-1001");
    expect((await screen.findAllByText("0 kWh")).length).toBeGreaterThan(0);
    expect(
      screen.getByRole("group", { name: "Selecionar período" }),
    ).toBeTruthy();
    expect(
      screen.getByRole("form", { name: "Período da consulta" }).textContent,
    ).toContain("Período aplicado: 01/2025 a 02/2025");
    const energyComparison = screen.getByRole("region", {
      name: "Comparação de energia e consumo",
    });
    const financialComparison = screen.getByRole("region", {
      name: "Comparação de valores financeiros",
    });
    expect(
      screen.getByRole("heading", { name: "Indicadores comparativos" }),
    ).toBeTruthy();
    expect(
      screen.queryByRole("heading", { name: /^Consumo medido$/ }),
    ).toBeNull();
    expect(
      screen.queryByRole("heading", { name: /^Valor faturado$/ }),
    ).toBeNull();
    expect(
      within(energyComparison).getByRole("heading", {
        name: "Energia e consumo",
      }),
    ).toBeTruthy();
    expect(
      within(energyComparison).getByRole("heading", {
        name: "Consumo medido (kWh)",
      }),
    ).toBeTruthy();
    expect(
      within(energyComparison).getByRole("heading", {
        name: "Energia faturada (kWh)",
      }),
    ).toBeTruthy();
    expect(
      within(financialComparison).getByRole("heading", {
        name: "Valores financeiros",
      }),
    ).toBeTruthy();
    expect(
      within(financialComparison).getByRole("heading", {
        name: "Valor faturado (BRL)",
      }),
    ).toBeTruthy();
    expect(
      within(financialComparison).getByRole("heading", {
        name: "Valor pago (BRL)",
      }),
    ).toBeTruthy();
    const billingSupport = screen.getByRole("region", {
      name: "Apoio ao atendimento",
    });
    expect(
      within(billingSupport).getByRole("heading", {
        name: "Faturas em aberto",
      }),
    ).toBeTruthy();
    expect(
      within(billingSupport).getByText(/contagem, sem saldo ou atraso/),
    ).toBeTruthy();
    expect(
      screen.getByRole("columnheader", { name: "Competência" }),
    ).toBeTruthy();
    const historyDisclosure = screen
      .getByText("Históricos por fonte")
      .closest("details");
    expect(historyDisclosure?.open).toBe(false);
    expect(screen.getAllByText("R$ 105,00").length).toBeGreaterThan(0);
    expect(screen.getByText("-100 kWh")).toBeTruthy();
    expect(screen.getByText("-100%")).toBeTruthy();
    expect(
      screen.getByRole("heading", { name: "Fatos observados" }),
    ).toBeTruthy();
    expect(
      screen.getByRole("heading", { name: "Hipóteses e limites" }),
    ).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Ver detalhes" }));
    expect(
      await screen.findByRole("heading", { name: "Histórico e fontes da UC" }),
    ).toBeTruthy();
    fireEvent.click(
      screen.getAllByRole("button", { name: "Abrir histórico" })[5],
    );
    expect(historyDisclosure?.open).toBe(true);
    expect((await screen.findAllByText("CH-01")).length).toBeGreaterThan(0);
    expect(screen.getAllByText("Chamado").length).toBeGreaterThan(0);
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/history/calls"),
      expect.anything(),
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Faturas e pagamentos" }),
    );
    expect((await screen.findAllByText("R$ 82,00")).length).toBeGreaterThan(0);
    expect(screen.getAllByText("R$ 70,00").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Data do pagamento").length).toBeGreaterThan(0);
    expect(screen.getAllByText("75 kWh").length).toBeGreaterThan(0);
    expect(screen.getAllByText("20/03/2025").length).toBeGreaterThan(0);
    expect(screen.getAllByText("05/03/2025").length).toBeGreaterThan(0);
  });

  it("states meter and comparison gaps in plain language when the final reading is missing", async () => {
    const period = { start: "2025-01", end: "2025-02", granularity: "month" };
    const available = (value: number) => ({
      value,
      status: "available",
      limitations: [],
    });
    const missing = (
      status: "empty" | "unavailable",
      limitations: string[] = [],
    ) => ({
      value: null,
      status,
      limitations,
    });
    const unavailableChange = (
      status: "empty" | "unavailable",
      limitations: string[] = [],
    ) => ({
      delta: null,
      percent_change: null,
      status,
      limitations,
    });
    const metadata = {
      contract_version: "1.1.0",
      status: "partial",
      period,
      filters: {},
      source: {
        kind: "synthetic",
        version: "dev04-v1",
        is_demo: true,
        updated_at: "2026-10-22T00:00:00Z",
      },
      limitations: [],
    };
    const overview = {
      data: {
        profile: {
          uc_id: "UC-1004",
          customer_reference: null,
          customer_name: null,
          municipio: "Recife",
          bairro: "Centro",
          classe: "Residencial",
          alimentador: "AL-04",
          status: "active",
        },
        period,
        comparison: {
          initial: {
            competencia: "2025-01",
            measured_energy_kwh: available(45),
            billed_energy_kwh: missing("empty"),
            billed_amount: missing("empty"),
            paid_amount: missing("unavailable"),
          },
          final: {
            competencia: "2025-02",
            measured_energy_kwh: missing("unavailable"),
            billed_energy_kwh: missing("empty"),
            billed_amount: missing("empty"),
            paid_amount: missing("unavailable"),
          },
          measured_energy_kwh: unavailableChange("unavailable", [
            "comparison.final.measured_energy_kwh sem leitura final.",
          ]),
          billed_energy_kwh: unavailableChange("empty"),
          billed_amount: unavailableChange("empty"),
          paid_amount: unavailableChange("unavailable"),
        },
        open_invoices: { count: 0, status: "available", limitations: [] },
        current_meter: { item: null, status: "empty", limitations: [] },
        distributed_generation: { items: [], status: "empty", limitations: [] },
        section_status: {
          consumption: "partial",
          invoices: "empty",
          meters: "available",
          distributed_generation: "empty",
          interruptions: "empty",
          calls: "empty",
        },
      },
      metadata,
    };
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      if (String(input).includes("/overview"))
        return new Response(JSON.stringify(overview), { status: 200 });
      if (String(input).includes("/history/meters"))
        return new Response(
          JSON.stringify({
            data: {
              items: [
                {
                  meter_id: "MED-004",
                  installed_at: "2020-01-01",
                  removed_at: "2025-01-31",
                },
              ],
            },
            pagination: { page: 1, page_size: 20, total: 1, total_pages: 1 },
            metadata: { ...metadata, status: "available" },
          }),
          { status: 200 },
        );
      return new Response(
        JSON.stringify({
          data: { items: [] },
          pagination: { page: 1, page_size: 20, total: 0, total_pages: 0 },
          metadata,
        }),
        { status: 200 },
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    renderPage("/uc-360?uc=UC-1004");

    expect(
      await screen.findByText(
        "Nenhum medidor vigente no snapshot; consulte o histórico de medidores.",
      ),
    ).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Medidores" }));
    expect((await screen.findAllByText("MED-004")).length).toBeGreaterThan(0);
    expect(screen.getByText(/1 registro · fonte dev04-v1/)).toBeTruthy();
    expect(
      fetchMock.mock.calls.some(([url]) =>
        String(url).includes("/history/meters"),
      ),
    ).toBe(true);
    expect(screen.getByText("Sem faturas nos meses comparados.")).toBeTruthy();
    expect(screen.queryByText(/Valor faturado: Sem dado.*Sem dado/)).toBeNull();
    expect(
      screen.getByText(
        /Não há dois valores disponíveis para comparar consumo medido/,
      ),
    ).toBeTruthy();
    const limitation = screen.getAllByText(
      /período atual: consumo medido sem leitura final/,
    )[0];
    expect(limitation.textContent).not.toContain("measured_energy_kwh");
    expect(limitation.textContent).toContain("sem leitura final");
  });
});
