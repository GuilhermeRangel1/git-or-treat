type ApiErrorKind = "http" | "network" | "invalid-response" | "configuration";

export class ApiError extends Error {
  status: number;
  data: unknown;
  kind: ApiErrorKind;
  constructor(
    message: string,
    status: number,
    data: unknown = undefined,
    kind: ApiErrorKind = "http",
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
    this.kind = kind;
  }
}

function apiBaseUrl() {
  const configured = import.meta.env.VITE_API_URL?.trim();
  if (configured) return configured.replace(/\/$/, "");
  if (import.meta.env.DEV) return "http://localhost:8000";
  throw new ApiError(
    "VITE_API_URL não foi configurada.",
    0,
    undefined,
    "configuration",
  );
}

function isAborted(error: unknown, signal: AbortSignal | null | undefined) {
  return (
    signal?.aborted || (error instanceof Error && error.name === "AbortError")
  );
}

/** Transporte JSON. T informa o tipo esperado; contratos/decodificação pertencem ao domínio. */
export async function apiClient<T = unknown>(
  endpoint: string,
  options: RequestInit = {},
): Promise<T> {
  const url = `${apiBaseUrl()}${endpoint.startsWith("/") ? endpoint : `/${endpoint}`}`;
  const headers = new Headers(options.headers);
  if (!headers.has("Accept")) headers.set("Accept", "application/json");
  if (typeof options.body === "string" && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  let response: Response;
  let raw: string;
  try {
    response = await fetch(url, { ...options, headers });
    raw = await response.text();
  } catch (error) {
    if (isAborted(error, options.signal)) throw error;
    throw new ApiError(
      "Não foi possível concluir a solicitação.",
      0,
      undefined,
      "network",
    );
  }

  let data: unknown = undefined;
  if (raw) {
    try {
      data = JSON.parse(raw);
    } catch {
      if (response.ok) {
        throw new ApiError(
          "Resposta inválida do serviço.",
          response.status,
          raw,
          "invalid-response",
        );
      }
      data = raw;
    }
  }

  if (!response.ok) {
    const detail =
      data && typeof data === "object" && "detail" in data
        ? data.detail
        : undefined;
    throw new ApiError(
      typeof detail === "string" ? detail : `Falha HTTP ${response.status}`,
      response.status,
      data,
    );
  }
  return data as T;
}
