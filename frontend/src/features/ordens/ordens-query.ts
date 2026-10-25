import { orderStatuses } from "@/shared/api/orders";

export const orderPriorities = ["BAIXA", "MEDIA", "ALTA"] as const;

const allowedParameters = new Set([
  "uc_id",
  "status",
  "priority",
  "page",
  "page_size",
]);

export type OrdersQuery = {
  request: string;
  page: number;
  pageSize: number;
  ucId: string | null;
  status: (typeof orderStatuses)[number] | null;
  priority: (typeof orderPriorities)[number] | null;
};

function positiveInteger(value: string, max?: number): number | null {
  if (!/^[1-9]\d*$/.test(value)) return null;
  const parsed = Number(value);
  if (!Number.isSafeInteger(parsed) || (max !== undefined && parsed > max))
    return null;
  return parsed;
}

function hasControlCharacters(value: string): boolean {
  for (const character of value) {
    const codePoint = character.codePointAt(0);
    if (
      codePoint !== undefined &&
      (codePoint < 32 || (codePoint >= 127 && codePoint <= 159))
    ) {
      return true;
    }
  }
  return false;
}

export function parseOrdersQuery(params: URLSearchParams): OrdersQuery {
  for (const key of params.keys()) {
    if (!allowedParameters.has(key) || params.getAll(key).length !== 1) {
      throw new Error(
        "Os filtros da URL são inválidos ou estão repetidos. Revise-os para consultar as ordens.",
      );
    }
  }

  const rawUcId = params.get("uc_id");
  const ucId = rawUcId?.trim() ?? null;
  if (
    rawUcId !== null &&
    (!ucId || ucId.length > 50 || hasControlCharacters(ucId))
  ) {
    throw new Error("O número da UC deve ter até 50 caracteres.");
  }

  const rawStatus = params.get("status");
  if (
    rawStatus !== null &&
    !orderStatuses.some((status) => status === rawStatus)
  ) {
    throw new Error("O estado informado não é válido.");
  }

  const rawPriority = params.get("priority");
  if (
    rawPriority !== null &&
    !orderPriorities.some((priority) => priority === rawPriority)
  ) {
    throw new Error("A prioridade informada não é válida.");
  }

  const page = positiveInteger(params.get("page") ?? "1");
  if (page === null) throw new Error("A página informada não é válida.");

  const pageSize = positiveInteger(params.get("page_size") ?? "20", 100);
  if (pageSize === null)
    throw new Error("O tamanho da página deve estar entre 1 e 100.");

  const request = new URLSearchParams();
  if (ucId) request.set("uc_id", ucId);
  if (rawStatus) request.set("status", rawStatus);
  if (rawPriority) request.set("priority", rawPriority);
  request.set("page", String(page));
  request.set("page_size", String(pageSize));

  return {
    request: request.toString(),
    page,
    pageSize,
    ucId,
    status: rawStatus as OrdersQuery["status"],
    priority: rawPriority as OrdersQuery["priority"],
  };
}

export function formatOrderCode(id: number): string {
  return `OS-${String(id).padStart(6, "0")}`;
}

export function formatOrderDate(value: string | null | undefined): string {
  if (!value) return "indisponível";
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return "indisponível";
  const formatted = new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
    timeZone: "America/Recife",
  }).format(date);
  return `${formatted} (Recife)`;
}

export function orderStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    PENDENTE: "Pendente",
    EM_ANDAMENTO: "Em andamento",
    CONCLUIDA: "Concluída",
    CANCELADA: "Cancelada",
  };
  return labels[status] ?? status;
}

export function orderPriorityLabel(priority: string): string {
  const labels: Record<string, string> = {
    BAIXA: "Baixa",
    MEDIA: "Média",
    ALTA: "Alta",
  };
  return labels[priority] ?? priority;
}
