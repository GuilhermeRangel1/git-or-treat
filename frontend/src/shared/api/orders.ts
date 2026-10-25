import { apiClient } from "./client";

export const orderStatuses = [
  "PENDENTE",
  "EM_ANDAMENTO",
  "CONCLUIDA",
  "CANCELADA",
] as const;
export type Order = {
  id: number;
  uc_id: string;
  reason: string;
  priority: string;
  status: (typeof orderStatuses)[number];
  notes: string | null;
  result: string | null;
  created_at: string;
  updated_at: string;
  suspicion_reference: string | null;
};

export function decodeOrder(value: unknown): Order {
  if (!value || typeof value !== "object")
    throw new Error("Resposta de ordem inválida.");
  const row = value as Record<string, unknown>;
  if (
    !Number.isSafeInteger(row.id) ||
    Number(row.id) < 1 ||
    ![
      "uc_id",
      "reason",
      "priority",
      "status",
      "created_at",
      "updated_at",
    ].every((k) => typeof row[k] === "string") ||
    !orderStatuses.some((status) => status === row.status) ||
    !["notes", "result", "suspicion_reference"].every(
      (k) => row[k] === null || typeof row[k] === "string",
    )
  ) {
    throw new Error("Resposta de ordem inválida.");
  }
  return value as Order;
}

export async function createQueueOrder(
  uc: string,
  payload: { source_version: string; rule_version: string },
  key: string,
) {
  return decodeOrder(
    await apiClient<unknown>(
      `/api/v1/inspections/queue/${encodeURIComponent(uc)}/orders`,
      {
        method: "POST",
        headers: { "Idempotency-Key": key },
        body: JSON.stringify(payload),
      },
    ),
  );
}

export async function searchOrders(query: string, signal: AbortSignal) {
  const value = await apiClient<unknown>(
    `/api/v1/inspections/orders/search?${query}`,
    { signal },
  );
  if (
    !value ||
    typeof value !== "object" ||
    !("items" in value) ||
    !Array.isArray(value.items) ||
    !("pagination" in value)
  )
    throw new Error("Lista de ordens inválida.");
  const p = value.pagination as Record<string, unknown>;
  if (
    !p ||
    !["page", "page_size", "total", "total_pages"].every(
      (k) => Number.isSafeInteger(p[k]) && Number(p[k]) >= 0,
    ) ||
    Number(p.page) < 1 ||
    Number(p.page_size) < 1
  )
    throw new Error("Paginação inválida.");
  return {
    items: value.items.map(decodeOrder),
    pagination: p as {
      page: number;
      page_size: number;
      total: number;
      total_pages: number;
    },
  };
}
