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
  version: number;
  cancellation_reason: string | null;
};

/** Snapshot operacional: pode conter campos legados/adicionais e ser incompleto. */
export type OrderDetail = Order & {
  suspicion_snapshot: Record<string, unknown> | null;
};

export type UpdateOrderPayload = {
  version: number;
  status?: Exclude<OrderStatus, "CANCELADA">;
  result?: string | null;
  notes?: string | null;
};

export type RegisterOrderResultPayload = {
  version: number;
  result: string;
  notes?: string | null;
};

export type CancelOrderPayload = {
  version: number;
  confirmed_order_id: number;
  reason?: string | null;
};

export const orderHistoryActions = [
  "CRIACAO",
  "ATUALIZACAO_STATUS",
  "REGISTRO_RESULTADO",
  "CANCELAMENTO",
] as const;
export type OrderHistoryAction = (typeof orderHistoryActions)[number];

export type OrderHistoryEvent = {
  id: number;
  order_id: number;
  previous_status: OrderStatus | null;
  new_status: OrderStatus;
  action: OrderHistoryAction;
  notes: string | null;
  details: string | null;
  actor: string | null;
  order_version: number | null;
  created_at: string;
};

const isRecord = (value: unknown): value is Record<string, unknown> =>
  value !== null && typeof value === "object" && !Array.isArray(value);

const isCancelledStatus = (value: unknown): value is "CANCELADA" =>
  value === "CANCELADA";

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
    !Number.isSafeInteger(row.version) ||
    Number(row.version) < 1 ||
    !(
      row.cancellation_reason === null ||
      typeof row.cancellation_reason === "string"
    ) ||
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
    version: row.version as number,
    cancellation_reason: row.cancellation_reason as string | null,
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

export function decodeOrderHistory(value: unknown): OrderHistoryEvent[] {
  if (!Array.isArray(value)) throw new Error("Histórico de ordens inválido.");
  return value.map((item) => {
    if (!isRecord(item)) throw new Error("Evento do histórico inválido.");
    const createdAt = normalizeTimestamp(item.created_at);
    if (
      !Number.isSafeInteger(item.id) ||
      Number(item.id) < 1 ||
      !Number.isSafeInteger(item.order_id) ||
      Number(item.order_id) < 1 ||
      !(
        item.previous_status === null ||
        orderStatuses.some((status) => status === item.previous_status)
      ) ||
      !orderStatuses.some((status) => status === item.new_status) ||
      !orderHistoryActions.some((action) => action === item.action) ||
      !["notes", "details", "actor"].every(
        (key) => item[key] === null || typeof item[key] === "string",
      ) ||
      !(
        item.order_version === null ||
        (Number.isSafeInteger(item.order_version) &&
          Number(item.order_version) >= 1)
      ) ||
      !createdAt
    )
      throw new Error("Evento do histórico inválido.");
    return {
      id: item.id as number,
      order_id: item.order_id as number,
      previous_status: item.previous_status as OrderStatus | null,
      new_status: item.new_status as OrderStatus,
      action: item.action as OrderHistoryAction,
      notes: item.notes as string | null,
      details: item.details as string | null,
      actor: item.actor as string | null,
      order_version: item.order_version as number | null,
      created_at: createdAt,
    };
  });
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

export async function updateOrder(id: number, payload: UpdateOrderPayload) {
  if (!Number.isSafeInteger(id) || id < 1)
    throw new Error("Identificador de ordem inválido.");
  if (!Number.isSafeInteger(payload.version) || payload.version < 1)
    throw new Error("Versão da ordem inválida.");
  if (isCancelledStatus(payload.status))
    throw new Error("Use a rota dedicada para cancelar a ordem.");
  if (Object.keys(payload).length === 1)
    throw new Error("Informe uma alteração para a ordem.");
  return decodeOrderDetail(
    await apiClient<unknown>(`/api/v1/inspections/orders/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  );
}

export async function registerOrderResult(
  id: number,
  payload: RegisterOrderResultPayload,
) {
  if (!Number.isSafeInteger(id) || id < 1)
    throw new Error("Identificador de ordem inválido.");
  if (!Number.isSafeInteger(payload.version) || payload.version < 1)
    throw new Error("Versão da ordem inválida.");
  return decodeOrderDetail(
    await apiClient<unknown>(`/api/v1/inspections/orders/${id}/result`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  );
}

export async function cancelOrder(id: number, payload: CancelOrderPayload) {
  if (!Number.isSafeInteger(id) || id < 1)
    throw new Error("Identificador de ordem inválido.");
  if (!Number.isSafeInteger(payload.version) || payload.version < 1)
    throw new Error("Versão da ordem inválida.");
  if (
    !Number.isSafeInteger(payload.confirmed_order_id) ||
    payload.confirmed_order_id < 1
  )
    throw new Error("Identificador confirmado inválido.");
  return decodeOrderDetail(
    await apiClient<unknown>(`/api/v1/inspections/orders/${id}/cancel`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  );
}

export async function getOrderHistory(id: number, signal?: AbortSignal) {
  if (!Number.isSafeInteger(id) || id < 1)
    throw new Error("Identificador de ordem inválido.");
  return decodeOrderHistory(
    await apiClient<unknown>(`/api/v1/inspections/orders/${id}/history`, {
      signal,
    }),
  );
}
