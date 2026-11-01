import {
  decodeGoldMetadata,
  isGoldMetadata,
} from "@/shared/analytics/goldContract";
import {
  acceptGoldPublication,
  acceptGoldIdentity,
  getGoldGeneration,
  markGoldPublicationStale,
  withGoldPublication,
} from "@/shared/analytics/goldPublication";
import {
  captureAuthorizationGeneration,
  currentAuthorizationGeneration,
  isSessionConfigured,
  isReauthenticationRequired,
  notifyUnauthorized,
} from "@/shared/auth/authorization";

type ApiErrorKind =
  "http" | "network" | "invalid-response" | "configuration" | "session-changed";

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
  if (import.meta.env.DEV) return "";
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
  if (isReauthenticationRequired()) {
    throw new ApiError("Renove a sessão antes de continuar.", 401);
  }
  const authorizationGeneration = captureAuthorizationGeneration();
  const analytic =
    (!options.method || options.method === "GET") &&
    /^\/api\/v1\/(panorama(?:\?|$)|operations\/|inspections\/queue(?:\/|\?|$)|revenue(?:\?|$)|ucs(?:\/|\?|$)|analytics\/options(?:\?|$))/.test(
      endpoint,
    );
  const requestGeneration = getGoldGeneration();
  if (analytic) {
    const [path, search] = endpoint.split("?");
    const params = withGoldPublication(new URLSearchParams(search));
    endpoint = `${path}${params.size ? `?${params}` : ""}`;
  }
  const url = `${apiBaseUrl()}${endpoint.startsWith("/") ? endpoint : `/${endpoint}`}`;
  const headers = new Headers(options.headers);
  const authenticatedSession = isSessionConfigured();
  if (!headers.has("Accept")) headers.set("Accept", "application/json");
  if (typeof options.body === "string" && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  let response: Response;
  let raw: string;
  try {
    response = await fetch(url, {
      ...options,
      headers,
      credentials: "include",
    });
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
  if (authorizationGeneration !== currentAuthorizationGeneration()) {
    throw new ApiError(
      "A sessão mudou durante a solicitação.",
      0,
      undefined,
      "session-changed",
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
    if (response.status === 401 && authenticatedSession) {
      notifyUnauthorized();
      throw new ApiError("A sessão expirou. Entre novamente.", 401, data);
    }
    if (analytic && response.status === 409) markGoldPublicationStale();
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
  if (
    analytic &&
    data &&
    typeof data === "object" &&
    "metadata" in data &&
    isGoldMetadata(data.metadata)
  ) {
    const metadata = decodeGoldMetadata(data.metadata);
    if (
      requestGeneration !== getGoldGeneration() ||
      !acceptGoldPublication(metadata)
    ) {
      throw new ApiError(
        "A publicação Gold mudou. Atualize os dados da jornada.",
        409,
        { error: { code: "stale_batch" } },
      );
    }
  }
  if (analytic && data && typeof data === "object") {
    const envelope = data as Record<string, unknown>;
    const meta = envelope.metadata;
    const source =
      meta && typeof meta === "object" && "source" in meta
        ? (meta as Record<string, unknown>).source
        : envelope.source;
    if (source && typeof source === "object") {
      const value = source as Record<string, unknown>;
      if (
        value.kind === "gold_csv" &&
        typeof value.version === "string" &&
        value.version.startsWith("gold-csv-v2:")
      ) {
        if (
          typeof value.publication_lote !== "string" ||
          !value.publication_lote.trim() ||
          typeof value.publication_fingerprint !== "string" ||
          !/^[a-f0-9]{64}$/.test(value.publication_fingerprint)
        ) {
          throw new ApiError(
            "Identidade da publicação Gold inválida.",
            200,
            undefined,
            "invalid-response",
          );
        }
        if (
          requestGeneration !== getGoldGeneration() ||
          !acceptGoldIdentity({
            lote: value.publication_lote,
            fingerprint: value.publication_fingerprint,
          })
        ) {
          throw new ApiError(
            "A publicação Gold mudou. Atualize os dados da jornada.",
            409,
            { error: { code: "stale_batch" } },
          );
        }
      }
    }
  }
  return data as T;
}
