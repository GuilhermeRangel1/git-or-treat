import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { OrderDetail } from "@/shared/api/orders";
import OrderFoundationsDialog from "./OrderFoundationsDialog";

const getOrderDetail = vi.hoisted(() => vi.fn());
vi.mock("@/shared/api/orders", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/shared/api/orders")>();
  return { ...actual, getOrderDetail };
});

const baseOrder: OrderDetail = {
  id: 18,
  uc_id: "UC-1004",
  reason: "Lacuna de leitura",
  priority: "MEDIA",
  status: "PENDENTE",
  notes: null,
  result: null,
  created_at: "2025-01-10T10:00:00Z",
  updated_at: "2025-01-10T10:00:00Z",
  suspicion_reference: null,
  version: 1,
  cancellation_reason: null,
  suspicion_snapshot: null,
};

function renderFoundations(order = baseOrder) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <OrderFoundationsDialog
        order={order}
        open
        onClose={vi.fn()}
        triggerRef={{ current: null }}
      />
    </QueryClientProvider>,
  );
}

beforeEach(() => vi.clearAllMocks());

describe("OrderFoundationsDialog", () => {
  it("expõe a ausência explícita de snapshot e mantém campos da ordem", async () => {
    getOrderDetail.mockResolvedValue(baseOrder);
    renderFoundations();

    expect(await screen.findByText("UC-1004")).toBeInTheDocument();
    expect(screen.getByText("Lacuna de leitura")).toBeInTheDocument();
    expect(screen.getByText("Não preservada nesta ordem.")).toBeInTheDocument();
    expect(
      screen.getByText(
        "A ordem não possui snapshot de fundamentos disponível.",
      ),
    ).toBeInTheDocument();
  });

  it("interpreta campos válidos de snapshot legado e não transforma estimativa nula em zero", async () => {
    const legacy = {
      ...baseOrder,
      suspicion_snapshot: {
        data: {
          potential_recoverable_energy_kwh: null,
          signals: [
            { id: "reading_gap", label: "Lacuna de leitura", weight: 0.6 },
            { label: "" },
          ],
          limitations: ["Triagem sintética; não confirma irregularidade."],
          estimate_evidence: { reference: "Sem referência suficiente" },
          unexpected_legacy_field: { kept: true },
        },
        metadata: {
          status: "available",
          period: { start: "2025-01", end: "2025-02" },
          source: {
            kind: "synthetic",
            version: "dev05-v1",
            is_demo: true,
            updated_at: "2025-03-01T12:00:00Z",
          },
        },
      },
    } as OrderDetail;
    getOrderDetail.mockResolvedValue(legacy);
    renderFoundations(legacy);

    expect(
      await screen.findByText(/Snapshot legado sem versão/),
    ).toBeInTheDocument();
    expect(
      screen.getByText("synthetic · dev05-v1 · demonstração sintética"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Não disponível; ausência de estimativa não é zero."),
    ).toBeInTheDocument();
    expect(screen.getByText("jan/2025 a fev/2025")).toBeInTheDocument();
    expect(screen.getAllByText("Lacuna de leitura")).toHaveLength(2);
    expect(screen.queryByText("0 kWh")).toBeNull();
    expect(
      screen.getByText("Triagem sintética; não confirma irregularidade."),
    ).toBeInTheDocument();
  });

  it("não interpreta snapshots de versão não suportada", async () => {
    getOrderDetail.mockResolvedValue({
      ...baseOrder,
      suspicion_snapshot: {
        snapshot_schema_version: "99",
        data: { potential_recoverable_energy_kwh: 45 },
        metadata: { source: { kind: "synthetic", version: "dev05-v1" } },
      },
    });
    renderFoundations();

    expect(
      await screen.findByText(
        /formato deste snapshot ainda não pode ser interpretado/,
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText("45 kWh")).toBeNull();
  });

  it("interpreta fundamentos Gold v2 preservados sem consultar a fila atual", async () => {
    const snapshot = {
      snapshot_schema_version: "2",
      data: {
        uc_id: "UC-123",
        reason: "REVISAR",
        rule_version: "gold-fila-inspecao-v1",
        category: "REVISAR",
        potential_recoverable_energy_kwh: null,
        evidence: { inspections_performed: 0, interruptions: null },
        variation: {
          p1_start: "2022-07",
          p1_end: "2023-06",
          p1_months_observed: 0,
          p1_average_kwh_per_month: null,
          p2_start: "2025-07",
          p2_end: "2026-06",
          p2_months_observed: 12,
          p2_average_kwh_per_month: 0,
          variation_kwh: null,
          variation_pct: null,
          drop_over_30_pct: null,
        },
        limitations: ["Categoria não é prioridade de despacho."],
      },
      metadata: {
        contract_version: "2.0.0",
        temporal_scope: "snapshot",
        schema_version: "gold-csv-v1",
        fingerprint: "b".repeat(64),
        source: {
          kind: "gold",
          version: "batch-old",
          is_demo: false,
          updated_at: "2026-10-29T12:00:00Z",
        },
        limitations: ["Snapshot cadastral."],
      },
    };
    getOrderDetail.mockResolvedValue({
      ...baseOrder,
      suspicion_snapshot: snapshot,
    });
    renderFoundations();

    expect(await screen.findByText("REVISAR")).toBeInTheDocument();
    expect(screen.getByText("Gold · batch-old")).toBeInTheDocument();
    expect(screen.getByText("b".repeat(64))).toBeInTheDocument();
    expect(
      within(screen.getByText("Inspeções realizadas").parentElement!).getByText(
        "0",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Não publicada na Gold; não é calculada nesta tela."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Categoria não é prioridade de despacho."),
    ).toBeInTheDocument();
    expect(getOrderDetail).toHaveBeenCalledTimes(1);
  });
});
