import { render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { decodeUCHistory } from "./contract";
import { HistoryPanel } from "./UC360History";

it("apresenta a informação declarada sem afirmá-la como pagamento ou saldo", () => {
  const history = decodeUCHistory(
    {
      data: {
        items: [
          {
            invoice_id: "F-1",
            competencia: "2025-01",
            billed_amount: 20,
            paid_amount: null,
            billed_energy_kwh: null,
            due_date: null,
            payment_date: null,
            payment_status: "unknown",
            currency_unit: "BRL",
            declared_status: "EM ABERTO",
            declared_open_amount: 20,
          },
        ],
      },
      pagination: { page: 1, page_size: 20, total: 1, total_pages: 1 },
      metadata: {
        contract_version: "1.1.0",
        status: "partial",
        period: { start: "2025-01", end: "2025-01", granularity: "month" },
        filters: {},
        source: {
          kind: "gold_csv",
          version: "gold-csv-v2:teste:publicacao",
          is_demo: false,
          updated_at: "2026-10-31T00:00:00Z",
        },
        limitations: [
          "Situação declarada e valor nominal em aberto vêm da fonte; não comprovam pagamento nem saldo contábil.",
        ],
      },
    },
    "invoices",
  );
  render(
    <HistoryPanel
      section="invoices"
      history={history}
      pending={false}
      error={null}
      historyPage={1}
      onRetry={vi.fn()}
      onSelectSection={vi.fn()}
      onPageChange={vi.fn()}
    />,
  );
  expect(
    screen.getAllByText("Situação declarada na fatura").length,
  ).toBeGreaterThan(0);
  expect(screen.getAllByText("EM ABERTO").length).toBeGreaterThan(0);
  expect(
    screen.getAllByText("Valor nominal declarado em aberto").length,
  ).toBeGreaterThan(0);
  expect(
    screen.getByText(/não comprovam pagamento nem saldo contábil/),
  ).toBeVisible();
  expect(screen.getAllByText("Situação desconhecida").length).toBeGreaterThan(
    0,
  );
});
