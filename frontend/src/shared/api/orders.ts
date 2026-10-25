import { apiClient } from "./client";

export const orderStatuses = [
  "PENDENTE",
  "EM_ANDAMENTO",
  "CONCLUIDA",
  "CANCELADA",
] as const;
export type OrderStatus = (typeof orderStatuses)[number];

export const orderPriorities = ["BAIXA", "MEDIA", "ALTA"] as const;
export type OrderPriority = (typeof orderPriorities)[number];

export type Order = {
  id: number;
  uc_id: string;
  reason: string;
  priority: OrderPriority;
  status: OrderStatus;
  notes: string | null;
  result: string | null;
  created_at: string;
  updated_at: string;
  suspicion_reference: string | null;
};

/** Snapshot operacional: pode conter campos legados/adicionais e ser incompleto. */
export type OrderDetail = Order & {
  suspicion_snapshot: Record<string, unknown> | null;
};

const isRecord = (value: unknown): value is Record<string, unknown> =>
  value !== null && typeof value === "object" && !Array.isArray(value);

const normalizeTimestamp = (value: unknown): string | null => {
  if (typeof value !== "string" || !value.trim()) return null;
  const raw = value.trim();
  const normalized = /^\d{4}-\d{2}-\d{2}$/.test(raw)
    ? `${raw}T00:00:00Z`
    : /[zZ]$|[+-]\d{2}:?\d{2}$/.test(raw)
      ? raw
      : /T/.test(raw)
        ? `${raw}Z`
        : raw;
  return Number.isFinite(Date.parse(normalized)) ? normalized : null;
};

export function decodeOrder(value: unknown): Order {
  if (!isRecord(value)) throw new Error("Resposta de ordem inválida.");
  const row = value;
  const createdAt = normalizeTimestamp(row.created_at);
  const updatedAt = normalizeTimestamp(row.updated_at);
  if (
    !Number.isSafeInteger(row.id) ||
    Number(row.id) < 1 ||
    typeof row.uc_id !== "string" ||
    !row.uc_id.trim() ||
    typeof row.reason !== "string" ||
    !row.reason.trim() ||
    !orderPriorities.some((priority) => priority === row.priority) ||
    !orderStatuses.some((status) => status === row.status) ||
    !createdAt ||
    !updatedAt ||
    !["notes", "result", "suspicion_reference"].every(
      (key) => row[key] === null || typeof row[key] === "string",
    )
  ) {
    throw new Error("Resposta de ordem inválida.");
  }
  return {
    id: row.id as number,
    uc_id: row.uc_id,
    reason: row.reason,
    priority: row.priority as OrderPriority,
    status: row.status as OrderStatus,
    notes: row.notes as string | null,
    result: row.result as string | null,
    created_at: createdAt,
    updated_at: updatedAt,
    suspicion_reference: row.suspicion_reference as string | null,
  };
}

export function decodeOrderDetail(value: unknown): OrderDetail {
  if (!isRecord(value)) throw new Error("Resposta de ordem inválida.");
  const order = decodeOrder(value);
  const snapshot = value.suspicion_snapshot;
  if (snapshot !== null && !isRecord(snapshot)) {
    throw new Error("Fundamentos da ordem inválidos.");
  }
  return {
    ...order,
    suspicion_snapshot: snapshot as Record<string, unknown> | null,
  };
}

export function decodeOrderPage(value: unknown) {
  if (
    !isRecord(value) ||
    !Array.isArray(value.items) ||
    !isRecord(value.pagination)
  )
    throw new Error("Lista de ordens inválida.");
  const p = value.pagination;
  if (
    !["page", "page_size", "total", "total_pages"].every(
      (key) => Number.isSafeInteger(p[key]) && Number(p[key]) >= 0,
    ) ||
    Number(p.page) < 1 ||
    Number(p.page_size) < 1 ||
    Number(p.page_size) > 100 ||
    Number(p.total_pages) !== Math.ceil(Number(p.total) / Number(p.page_size))
  ) {
    throw new Error("Paginação inválida.");
  }
  if (
    value.items.length > Number(p.page_size) ||
    value.items.length > Number(p.total)
  ) {
    throw new Error("Lista de ordens incompatível com a paginação.");
  }
  return {
    items: value.items.map(decodeOrder),
    pagination: {
      page: p.page as number,
      page_size: p.page_size as number,
      total: p.total as number,
      total_pages: p.total_pages as number,
    },
  };
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
  return decodeOrderPage(
    await apiClient<unknown>(`/api/v1/inspections/orders/search?${query}`, {
      signal,
    }),
  );
}

export async function getOrderDetail(id: number, signal?: AbortSignal) {
  if (!Number.isSafeInteger(id) || id < 1)
    throw new Error("Identificador de ordem inválido.");
  return decodeOrderDetail(
    await apiClient<unknown>(`/api/v1/inspections/orders/${id}`, { signal }),
  );
}

export type UpdateOrderPayload = {
  status?: OrderStatus;
  result?: string | null;
  notes?: string | null;
};

export async function updateOrder(id: number, payload: UpdateOrderPayload) {
  if (!Number.isSafeInteger(id) || id < 1)
    throw new Error("Identificador de ordem inválido.");
  if (Object.keys(payload).length === 0)
    throw new Error("Informe uma alteração para a ordem.");
  return decodeOrderDetail(
    await apiClient<unknown>(`/api/v1/inspections/orders/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  );
}
